import logging
import asyncio
import threading
from rocketchat_async import RocketChat
import requests
import json
import time
import datetime

logger = logging.getLogger(__name__)

class RocketchatManager:
    def __init__(self, subscription_lock, rules_manager):
        self._ROCKET_USER_ID = ''
        self._ROCKET_TOKEN = ''
        self._SERVER_ADDRESS = ''
        self.HEADERS = {}
        self._on_error_callback = None
        self._subscription_lock = subscription_lock
        self._rules_manager = rules_manager

        self._stop_event = None
        self.unread_messages = {}
        self._rocketChat = None
        self._subscription_dict = {}
        self._rc_manager_thread = None
        self._rocket_async_unhandled_error = None

    @property
    def ROCKET_USER_ID(self):
        return self._ROCKET_USER_ID

    def set_ROCKET_USER_ID(self, value):
        self._ROCKET_USER_ID = value
        self._update_headers()

    @property
    def ROCKET_TOKEN(self):
        return self._ROCKET_TOKEN

    def set_ROCKET_TOKEN(self, value):
        self._ROCKET_TOKEN = value
        self._update_headers()

    @property
    def SERVER_ADDRESS(self):
        return self._SERVER_ADDRESS

    def set_SERVER_ADDRESS(self, value):
        self._SERVER_ADDRESS = value

    def _update_headers(self):
        self.HEADERS = {
            'X-Auth-Token': self._ROCKET_TOKEN,
            'X-User-Id': self._ROCKET_USER_ID
        }

    def set_on_error_callback(self, callback):
        self._on_error_callback = callback

    def set_on_reload(self, callback):
        self._set_on_reload = callback

    def get_mock_subscriptions(self):
        with open('mock_sub.json', 'r') as file:
            data = json.load(file)
        return data

    def mark_messages_as_read(self, room_id):
        try:
            response = requests.post(f'{self.SERVER_ADDRESS}/api/v1/subscriptions.read', headers=self.HEADERS, json={"rid": room_id})
            if response.status_code == 200:
                return True
            else:
                self.do_error(f"Failed to mark messages as read for room {room_id}. Status code: {response.status_code}")
                return False
        except Exception as e:
            self.do_error(f"Network error: {e}")
            return False

    def get_subscription_for_channel(self,channel_id):
        #return self.get_mock_subscriptions()
        try:
            response = requests.get(f'{self.SERVER_ADDRESS}/api/v1/subscriptions.getOne?roomId={channel_id}', headers=self.HEADERS)
            if response.status_code == 200:
                return response.json()
            else:
                self.do_error(f"Failed to fetch data. Status code: {response.status_code}")
                return None
        except Exception as e:
            self.do_error(f"Network error: {e}")
            return None

    def get_all_subscriptions(self):
        try:
            response = requests.get(f'{self.SERVER_ADDRESS}/api/v1/subscriptions.get', headers= self.HEADERS)
            if response.status_code == 200:
                return response.json()
            else:
                self.do_error(f"Failed to fetch data. Status code: {response.status_code}")
                return None
        except Exception as e:
            self.do_error(f"Network error: {e}")
            return None

    def convert_to_wsl_address(self, server_address):
        if server_address.startswith("https://"):
            wsl_address = server_address.replace("https://", "wss://") + "/websocket"
        elif server_address.startswith("http://"):
            wsl_address = server_address.replace("http://", "ws://") + "/websocket"
        else:
            raise ValueError("Invalid server address scheme. Must start with 'http://' or 'https://'.")
        return wsl_address

    def do_error(self, text):
        logger.error(text)
        if self._on_error_callback:
            self._on_error_callback(text)

    def get_last_message_text(self, rid):
        if rid not in self.unread_messages or not self.unread_messages[rid]:
            return None
        last_message = self.unread_messages[rid][-1]
        last_msg_content = next(iter(last_message.values()))
        if last_msg_content.get("qualifier") == "videoconf":
            txt = "Incoming phone call"
        else:
            txt = last_msg_content.get("text")
        return txt

    def get_unread_messages(self, channel_id, last_seen):
        try:
            response = requests.get(f'{self.SERVER_ADDRESS}/api/v1/channels.messages?roomId={channel_id}', headers= self.HEADERS)
            if response.status_code == 200:
                messages_data = response.json()
            else:
                self.do_error(f"Failed to fetch data. Status code: {response.status_code}")
                return None
        except Exception as e:
            self.do_error(f"Network error: {e}")
            return None

        unread_messages = []
        for message in messages_data['messages']:
            message_time = datetime.datetime.strptime(message['ts'], '%Y-%m-%dT%H:%M:%S.%fZ')
            if message_time > last_seen:
                unread_messages.append(message)
        return unread_messages



    def get_unread_messages_since_last_seen(self, subscription):
        channel_id = subscription['rid']
        last_seen = datetime.datetime.strptime(subscription['ls'], '%Y-%m-%dT%H:%M:%S.%fZ')
        unread_messages = self.get_unread_messages(channel_id, last_seen)
        logger.info(unread_messages)


    def handle_channel_changes(self, payload):
        logger.info("===== handle_channel_changes =====")
        logger.info(f" {payload}")

        try:
            last_message = payload[1].get('lastMessage')
            if last_message is None:
                logger.warning("No 'lastMessage' in payload")
                return

            msg = last_message.get('msg', '')
            msg_id = last_message.get('_id', '')
            channel_id = last_message.get('rid', '')
            sender_id = last_message.get('u', {}).get('_id', '')
            qualifier = last_message.get('t')
            unread = True

            with self._subscription_lock:
                logger.info(f"   channel={channel_id} sender={sender_id} msgid={msg_id} txt={msg} unread={unread} qualifier={qualifier}")

                if not self.unread_messages.get(channel_id):
                    if not unread:
                        return
                    else:
                        self.unread_messages[channel_id] = []

                if unread:
                    self.unread_messages[channel_id].append({msg_id: {"text": msg, "qualifier": qualifier}})
                    logger.info("    -- handle_channel_changes added ")
                    logger.info(json.dumps(self.unread_messages, indent=4, sort_keys=True))

        except Exception as e:
            logger.error(f"   >>> Error handling channel changes: {e}", exc_info=True)


    #{'motest':['msg_101':{"text":"abc"}, 'msg_102':{"text":"efg",  "qualifier":"videoconf"} ]}
    def add_historical_message(self, channel_id):
        if not self.unread_messages.get(channel_id):
            self.unread_messages[channel_id] = []
        self.unread_messages[channel_id].append({'historical': {"text": "", "qualifier":""}})
        logger.info("   -- add_historical_message added ")

    def remove_all_historical_messages(self, channel_id):
        if channel_id in self.unread_messages:
            self.unread_messages[channel_id] = [msg for msg in self.unread_messages[channel_id] if 'historical' not in msg]
            if not self.unread_messages[channel_id]:
                del self.unread_messages[channel_id]
            logger.info(f"   -- remove_all_historical_messages: removed for channel {channel_id}")

    async def run_forever_wrapper(self):
        try:
            await self._rocketChat.run_forever()
        except Exception as e:
                logger.info(f'run_forever_wrapper: Unexpected exception occurred: {e}')
                self._rocket_async_unhandled_error = e

    #asyncio.run(monitor_subscriptions_websocket()
    async def monitor_subscriptions_websocket(self):
        self._stop_event = asyncio.Event()
        while not self._stop_event.is_set():
            self._rocket_async_unhandled_error = None
            if not self._rules_manager.rules_are_loaded() or not self._rules_manager.config_is_loaded():
                self.do_error('')
                await asyncio.sleep(10)
                continue

            try:
                print("Createing RocketChat() object and connectiing to the server...")
                logger.info("Createing RocketChat() object and connectiing to the server...")
                self._rocketChat = RocketChat()
                #await rc.start(address, username, password)
                # Alternatively, use rc.resume for token-based authentication:
                print("  #1")
                await self._rocketChat.resume(self.convert_to_wsl_address(self.SERVER_ADDRESS), self.ROCKET_USER_ID, self.ROCKET_TOKEN)
                # 1. Set up the desired callbacks...
                #for channel_id, channel_type in await rc.get_channels(): //to few informations returned :-(
                await self.unsubscribe_all()
                await self._rocketChat.subscribe_to_channel_changes_raw(self.handle_channel_changes)
                logger.info("Geting all subscriptions...")
                data = self.get_all_subscriptions()
                print("  #5")
                if data:
                    with self._subscription_lock:
                        updates = data.get('update', [])
                        for sub in updates:
                            fname = sub.get('fname')
                            chtype = sub.get('t')
                            channel_id = sub.get('rid')
                            open = sub.get('open')
                            unread = sub.get('unread')
                            if open==True:
                                matching_rule = self._rules_manager.find_matching_rule(fname, chtype, [])
                                if matching_rule and matching_rule.get('ignore', "False") == "False":
                                    self._subscription_dict[channel_id]=sub
                                    if unread>0  :
                                          #this will cause the channel to be monitored by monitor_all_subscriptions loop
                                          #self.get_unread_messages_since_last_seen(sub)
                                          self.add_historical_message(channel_id)
                    print("  #10")
                    #await self._rocketChat.run_forever()


                    task = asyncio.create_task(self.run_forever_wrapper())
                    while not self._stop_event.is_set():
                        await asyncio.sleep(1)
                        if self._rocket_async_unhandled_error:
                            raise self._rocket_async_unhandled_error
                    logger.info('Canceling rocket_chat_async worker thread...')
                    task.cancel()
                    break

                else:
                    self.do_error("No subscirptions found")
                    await asyncio.sleep(10)
                    continue

            except Exception as e:
                self.do_error(f"monitor_subscriptions_websocket: \n {e}")
                await asyncio.sleep(10)
                logger.info('Reconnecting...')



    async def unsubscribe_all(self):
        for channel_id in self._subscription_dict.keys():
            await self._rocketChat.unsubscribe(channel_id)
        self._subscription_dict={}


    def monitor_asyncio_subscriptions_websocket(self):
        asyncio_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(asyncio_loop)
        try:
            asyncio_loop.run_until_complete(self.monitor_subscriptions_websocket())
        except Exception as e:
            logger.info(f"Exception: {e}")
        finally:
            logger.info("Asyncio cleanup begin...")
            self.cleanup_pending_task(asyncio_loop)
            logger.info("Asyncio cleanup end.")


    def cleanup_pending_task(self, asyncio_loop):
         # Cancel all pending tasks
        pending = asyncio.all_tasks(asyncio_loop)
        for task in pending:
            task.cancel()
        # Run event loop until all tasks are cancelled
        asyncio_loop.run_until_complete(
            asyncio.gather(*pending, return_exceptions=True)
        )
        # Shutdown async generators
        asyncio_loop.run_until_complete(asyncio_loop.shutdown_asyncgens())
        asyncio_loop.close()

    def stop(self):
        self._stop_event.set()

    def restart(self):
        logger.info("===== rocket_manager Restart =====")
        if self._rc_manager_thread.is_alive():
            logger.info(" Asyncio restart begin...")
            self._stop_event.set()
            logger.info(" Asyncio restart begin 2")
            time.sleep(1)
            if self._set_on_reload:
                logger.info(" Asyncio restart begin 3")
                self._set_on_reload()
            logger.info(" Asyncio restart begin 4")
            self._rc_manager_thread.join()  # Wait for the thread to finish
            logger.info(" Asyncio restart begin 5")
            self._stop_event.clear()
            logger.info(" Asyncio restart begin 6")
            self.start()
            logger.info(" Asyncio restart end.")

    def start(self):
        self._rc_manager_thread = threading.Thread(target=self.monitor_asyncio_subscriptions_websocket)
        self._rc_manager_thread.start()

    def mark_read(self):
        for room_id in self.unread_messages.keys():
            self.mark_messages_as_read(room_id)


    def send_message(self, room_id, text):
            try:
                payload = {
                    "roomId": room_id,
                    "text": text
                }
                response = requests.post(f'{self.SERVER_ADDRESS}/api/v1/chat.postMessage', headers=self.HEADERS, json=payload)
                if response.status_code == 200:
                    return True
                else:
                    self.do_error(f"Failed to send message to room {room_id}. Status code: {response.status_code}")
                    return False
            except Exception as e:
                self.do_error(f"Network error: {e}")
                return False

    def set_user_status(self, status, message=None):
        """
        Set the user's status.
        :param status: String, one of 'online', 'busy', 'away', 'offline'
        :param message: Optional string for a custom status message
        :return: Boolean indicating success or failure
        """
        valid_statuses = ['online', 'busy', 'away', 'offline']
        if status not in valid_statuses:
            self.do_error(f"Invalid status. Must be one of {', '.join(valid_statuses)}")
            return False

        data = {"status": status}
        if message:
            data["message"] = message

        try:
            response = requests.post(f'{self.SERVER_ADDRESS}/api/v1/users.setStatus',
                                     headers=self.HEADERS,
                                     json=data)
            if response.status_code == 200:
                logger.info(f"User status set to {status}")
                return True
            else:
                self.do_error(f"Failed to set user status. Status code: {response.status_code}")
                return False
        except Exception as e:
            self.do_error(f"Network error while setting user status: {e}")
            return False

    def __init__(self, subscription_lock, rules_manager):
        self._ROCKET_USER_ID = ''
        self._ROCKET_TOKEN = ''
        self._SERVER_ADDRESS = ''
        self.HEADERS = {}
        self._on_error_callback = None
        self._subscription_lock = subscription_lock
        self._rules_manager = rules_manager

        self._stop_event = None
        self.unread_messages = {}
        self._rocketChat = None
        self._subscription_dict = {}
        self._rc_manager_thread = None

        # New attributes for caching status
        self._last_status_check = 0
        self._cached_status = 'unknown'

    def get_status(self):
        current_time = time.time()
        if current_time - self._last_status_check >= 1:  # Check if 1 second has passed
            try:
                response = requests.get(f'{self.SERVER_ADDRESS}/api/v1/users.getStatus', headers=self.HEADERS)
                if response.status_code == 200:
                    data = response.json()
                    self._cached_status = data.get('status', 'unknown')
                else:
                    self.do_error(f"Failed to get user status. Status code: {response.status_code}")
                    self._cached_status = 'unknown'
            except Exception as e:
                self.do_error(f"Network error while getting user status: {e}")
                self._cached_status = 'unknown'

            self._last_status_check = current_time
        return self._cached_status

    def set_online(self):
        """Set user status to online"""
        if self.set_user_status('online'):
            self._cached_status = 'online'
            return True
        return False

    def set_busy(self, message=None):
        """Set user status to busy"""
        if self.set_user_status('busy', message):
            self._cached_status = 'busy'
            return True
        return False

    def set_away(self, message=None):
        """Set user status to away"""
        if self.set_user_status('away', message):
            self._cached_status = 'away'
            return True
        return False

    def set_offline(self):
        """Set user status to offline"""
        if self.set_user_status('offline'):
            self._cached_status = 'offline'
            return True
        return False





