import asyncio
import threading
from . import rules_manager
from rocketchat_async import RocketChat
import requests
import json
import time

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
        self._on_unread_message = None     
        self._rc_manager_thread = None   

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

    def set_on_unread_message(self, callback):
        self._on_unread_message = callback

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
        print(text)        
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


    def handle_channel_changes(self, channel_id, channel_type):
        print("===== handle_channel_changes =====")
        print(f"  channel_id={channel_id} channel_type={channel_type}")        
        self.restart()

    #{'motest':['msg_101':{"text":"abc"}, 'msg_102':{"text":"efg",  "qualifier":"videoconf"} ]}

    def remove_message(self, channel_id, msg_id):
        for msg_dict in self.unread_messages[channel_id]:
            if msg_id in msg_dict:
                self.unread_messages[channel_id].remove(msg_dict)
                break
        self.remove_all_historical_messages(channel_id)

    def handle_message(self, channel_id, sender_id, msg_id, thread_id, msg, qualifier, unread, repeated):
        with self._subscription_lock:
            print(f"channel={channel_id} sender={sender_id} msgid={msg_id} txt={msg}  unread={unread} qualifier={qualifier}")
            #qualifier=
            if not self.unread_messages.get(channel_id):
                if not unread:
                    return
                else:
                    self.unread_messages[channel_id] = []
            if unread:
                self.unread_messages[channel_id].append({msg_id: {"text": msg, "qualifier":qualifier}})
                print("   -- handle_message1 dodano ")
            else:
                self.remove_message(channel_id, msg_id)
                if len(self.unread_messages[channel_id])==0:
                    del self.unread_messages[channel_id]
                print("   -- handle_message1 usunieto ")

    def add_historical_message(self, channel_id):
        if not self.unread_messages.get(channel_id):                    
            self.unread_messages[channel_id] = []        
        self.unread_messages[channel_id].append({'historical': {"text": "", "qualifier":""}})
        print("   -- add_historical_message dodano ")

    def remove_all_historical_messages(self, channel_id):
        if channel_id in self.unread_messages:
            self.unread_messages[channel_id] = [msg for msg in self.unread_messages[channel_id] if 'historical' not in msg]
            if not self.unread_messages[channel_id]:
                del self.unread_messages[channel_id]
            print(f"   -- remove_all_historical_messages: removed for channel {channel_id}")

    #asyncio.run(monitor_subscriptions_websocket()
    async def monitor_subscriptions_websocket(self):
        self._stop_event = asyncio.Event()        
        while not self._stop_event.is_set():
            if not rules_manager.rules_are_loaded() or not rules_manager.config_is_loaded():
                self.do_error('')
                await asyncio.sleep(10)
                continue

            print("#4")
            try:
                print("#5")
                self._rocketChat = RocketChat()
                #await rc.start(address, username, password)
                # Alternatively, use rc.resume for token-based authentication:
                await self._rocketChat.resume(self.convert_to_wsl_address(self.SERVER_ADDRESS), self.ROCKET_USER_ID, self.ROCKET_TOKEN)
                print("#6")
                # 1. Set up the desired callbacks...
                #for channel_id, channel_type in await rc.get_channels(): //to few informations returned :-(
                await self.unsubscribe_all()
                await self._rocketChat.subscribe_to_channel_changes(self.handle_channel_changes)
                data = self.get_all_subscriptions()
                print("#7")
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
                                matching_rule = rules_manager.find_matching_rule(fname, chtype, [])
                                if matching_rule and matching_rule.get('ignore', "False") == "False":
                                    self._subscription_dict[channel_id]=sub
                                    await self._rocketChat.subscribe_to_channel_messages(channel_id,  self.handle_message)
                                    print(f'subscribed to  {fname}  {channel_id}')
                                    
                                    if self._on_unread_message and unread>0:
                                          self.add_historical_message(channel_id)  
                                    #     self._on_unread_message(matching_rule, sub)
                                    #     print(f'  _on_unread_message: {unread}')
                    # 2. ...and then simply wait for the registered events.
                    await self._rocketChat.run_forever()
                else:
                    self.do_error("No subscirptions found")
                    await asyncio.sleep(10)
                    continue                        
            except  (RocketChat.ConnectionClosed, RocketChat.ConnectCallFailed) as e:
                    self.do_error("Connection failed: {e}")
                    await asyncio.sleep(10)
                    print('Reconnecting...')

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
            print(f"Exception: {e}")
        finally:
            print("Finally...")
            if self._rocketChat:
                self._rocketChat.cleanup_pending_task(asyncio_loop)
            print("monitor_asyncio_subscriptions_websocket end")    

    def stop(self):
        self._stop_event.set()
        if self._rocketChat:
            self._rocketChat.stop()

    def restart(self):
        print("===== rocket_manager Restart =====")        
        if self._rc_manager_thread.is_alive():

            print("  restart begin")
            self._stop_event.set()
            if self._rocketChat:
                self._rocketChat.stop()
            time.sleep(1)
            if self._set_on_reload:
                self._set_on_reload()
            self._rc_manager_thread.join()  # Wait for the thread to finish
            self._stop_event.clear()       
            self.start()  
            print("  restart end")             

    def start(self):
        self._rc_manager_thread = threading.Thread(target=self.monitor_asyncio_subscriptions_websocket)
        self._rc_manager_thread.start()

    def mark_read(self):
        for room_id in self.unread_messages.keys():
            self.mark_messages_as_read(room_id)





