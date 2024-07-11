import pystray
from PIL import Image
from pystray import MenuItem as item
import time
import requests
import json
import threading
import os
from datetime import datetime, timedelta


from rocketchat_async import RocketChat
import asyncio
import random
from icon_manager import icon_manager
from rules_manager import rules_manager

TITLE = "Better Rocket Icon"
C_MAIN_LOOP_WAIT_TIME=1 #sec

rules_manager.ensure_local_files()
 
stop_event = threading.Event()
pause_event = threading.Event()  # Event to control pausing
asyncio_stop_event = None
asyncio_loop = None
g_rocketChat = None

pause_invoked = False  # Flag to check if pause_event.clear() was invoked

g_subscription_dict = {}
g_unread_messages = {}
subscription_lock = threading.Lock()

# Load configuration from config.json
def load_config():
    global config, ROCKET_USER_ID, ROCKET_TOKEN, SERVER_ADDRESS, ROCKET_PROGRAM, TITLE, HEADERS
    try:
        config = rules_manager.load_config()
        ROCKET_USER_ID = config['ROCKET_USER_ID']
        ROCKET_TOKEN = config['ROCKET_TOKEN']
        SERVER_ADDRESS = config['SERVER_ADDRESS']
        ROCKET_PROGRAM = config['ROCKET_PROGRAM']
        HEADERS = {
            'X-Auth-Token': ROCKET_TOKEN,
            'X-User-Id': ROCKET_USER_ID
        }
        icon_manager.notify("Config loaded", TITLE)     
    except Exception as e:
        print(f"Error reading config file {e}")



def convert_to_wsl_address(server_address):
    if server_address.startswith("https://"):
        wsl_address = server_address.replace("https://", "wss://") + "/websocket"
    elif server_address.startswith("http://"):
        wsl_address = server_address.replace("http://", "ws://") + "/websocket"
    else:
        raise ValueError("Invalid server address scheme. Must start with 'http://' or 'https://'.")
    return wsl_address



def get_all_subscriptions():
    try:
        response = requests.get(f'{SERVER_ADDRESS}/api/v1/subscriptions.get', headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch data. Status code: {response.status_code}")
            icon_manager.set_icon_title(f"Failed to fetch data. Status code: {response.status_code}")
            icon_manager.set_error_image()
            return None
    except Exception as e:
        print(f"Network error: {e}")
        icon_manager.set_icon_title(f"Network error: {e}")
        icon_manager.set_error_image()
        return None
    

def get_mock_subscriptions():
    with open('mock_sub.json', 'r') as file:
        data = json.load(file)
    return data
    
def get_subscription_for_channel(channel_id):
    return get_mock_subscriptions()
    try:
        response = requests.get(f'{SERVER_ADDRESS}/api/v1/subscriptions.getOne?roomId={channel_id}', headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch data. Status code: {response.status_code}")
            set_icon_title(f"Failed to fetch data. Status code: {response.status_code}")
            icon_manager.set_error_image()
            return None
    except Exception as e:
        print(f"Network error: {e}")
        set_icon_title(f"Network error: {e}")
        icon_manager.set_error_image()
        return None    
    
def get_channels_for_messages(channels):
    updates = []
    for channel_id in channels:
          json = get_subscription_for_channel(channel_id)
          updates.append(json.get('subscription'))
    return {"update":updates}
    

def get_last_message_text(rid):
    if rid not in g_unread_messages or not g_unread_messages[rid]:
        return None
    last_message = g_unread_messages[rid][-1]
    last_msg_content = next(iter(last_message.values()))
    if last_msg_content.get("qualifier") == "videoconf":
        txt = "Incoming phone call"
    else:
        txt = last_msg_content.get("text")
    return txt


def monitor_all_subscriptions():
    time.sleep(1)
    print(f"Starting loop")
    try:
        while not stop_event.is_set():
            pause_event.wait()  # Wait for the pause event to be set

            if not rules_manager.rules_are_loaded():
                icon_manager.set_error_image()
                icon_manager.set_icon_title("Error reading rules.json file. Please go to Rules and verify your JSON syntax, and try again.")
                stop_event.wait(10)
                continue

            if not rules_manager.config_is_loaded():
                icon_manager.set_error_image()
                icon_manager.set_icon_title("Error reading config.json file. Please go to Settings and verify your JSON syntax, and try again.")
                stop_event.wait(10)
                continue          

            with subscription_lock:      
                data = get_channels_for_messages(g_unread_messages)
                if data:
                    updates = data.get('update', [])
                    icon_manager.reset_priority()
                    for sub in updates:
                        rules_manager.process_subscription(sub, g_unread_messages)                
                    if rules_manager.unread_counts:
                        summary = "\n".join([f"{fname}: {unread}" for fname, unread in rules_manager.unread_counts.items()])
                    else:
                        summary = "No new messages"
                    icon_manager.set_icon_title(summary)                


                if len(rules_manager.unread_counts) == 0:
                    icon_manager.set_basic_image()
            stop_event.wait(C_MAIN_LOOP_WAIT_TIME)
    finally:
        stop_asyncio_subscriptions_websocket()



#{'motest':['msg_101':{"text":"abc"}, 'msg_102':{"text":"efg",  "qualifier":"videoconf"} ]}

def remove_message(channel_id, msg_id):
     return
     for msg_dict in g_unread_messages[channel_id]:
        if msg_id in msg_dict:
            g_unread_messages[channel_id].remove(msg_dict)
            break

def handle_message(channel_id, sender_id, msg_id, thread_id, msg, qualifier, unread, repeated):
    with subscription_lock:
        print(f"channel={channel_id} sender={sender_id} msgid={msg_id} txt={msg}  unread={unread} qualifier={qualifier}")
        #qualifier=
        if not g_unread_messages.get(channel_id):
            if not unread:
                return
            else:
                g_unread_messages[channel_id] = []
        if unread:
            g_unread_messages[channel_id].append({msg_id: {"text": msg, "qualifier":qualifier}})
            print("   -- handle_message1 dodano ")
        else:
            remove_message(channel_id, msg_id)
            if len(g_unread_messages[channel_id])==0:
                del g_unread_messages[channel_id]
            print("   -- handle_message1 usunieto ")

#asyncio.run(monitor_subscriptions_websocket()
async def monitor_subscriptions_websocket():
    global asyncio_stop_event
    global g_rocketChat
    icon_manager.set_basic_image()
    asyncio_stop_event = asyncio.Event()
    while not asyncio_stop_event.is_set():
        if not rules_manager.rules_are_loaded() or not rules_manager.config_is_loaded():
            icon_manager.set_error_image()
            await asyncio.sleep(10)
            continue

        print("#4")
        pause_event.wait()  # Wait for the pause event to be set
        try:
            print("#5")
            g_rocketChat = RocketChat()
            #await rc.start(address, username, password)
            # Alternatively, use rc.resume for token-based authentication:
            await g_rocketChat.resume(convert_to_wsl_address(SERVER_ADDRESS), ROCKET_USER_ID, ROCKET_TOKEN)
            print("#6")
            # 1. Set up the desired callbacks...
            #for channel_id, channel_type in await rc.get_channels(): //to few informations returned :-(
            data = get_all_subscriptions()
            print("#7")
            if data:
                with subscription_lock:
                    updates = data.get('update', [])
                    for sub in updates:
                        fname = sub.get('fname')
                        chtype = sub.get('t')
                        channel_id = sub.get('rid')
                        open = sub.get('open')
                        if open==True:
                            matching_rule = rules_manager.find_matching_rule(fname, chtype, [])
                            if matching_rule and matching_rule.get('ignore', "False") == "False":
                                g_subscription_dict[channel_id]=sub
                                await g_rocketChat.subscribe_to_channel_messages(channel_id,  handle_message)
                                print(f'subscribed to  {fname}  {channel_id}')
                # 2. ...and then simply wait for the registered events.
                await g_rocketChat.run_forever()
        except  (RocketChat.ConnectionClosed, RocketChat.ConnectCallFailed) as e:
                icon_manager.set_icon_title(f"Connection failed: {e}")
                icon_manager.set_error_image()
                print(f'Connection failed: {e}. Waiting a few seconds...')
                await asyncio.sleep(random.uniform(4, 8))
                print('Reconnecting...')







def on_clicked_quit(icon, item):
    if item.text == "Quit":
        print("Quit.")        
        stop_asyncio_subscriptions_websocket()
        stop_event.set()
        pause_event.set()  # Resume if paused to ensure clean exit
        time.sleep(5)        
        icon.stop()

        print("Normal exit.")

def on_clicked_show(icon, item):
    global pause_invoked
    if pause_invoked:
        icon_manager.set_delay_image()
    else:
        icon_manager.set_launch_image()
    os.startfile(ROCKET_PROGRAM)

def on_clicked_settings(icon, item):
    os.startfile(rules_manager.config_path)

def on_clicked_rules(icon, item):
    os.startfile(rules_manager.rules_path)

def pause_for_duration(duration):
    global pause_invoked
    def stop():
        global pause_invoked
        pause_event.clear()  # Clear the pause event to block monitoring
        pause_invoked = True
        resume_time = datetime.now() + timedelta(seconds=duration)
        icon_manager.set_icon_title(f"Paused until {resume_time.strftime('%H:%M')}")
        icon_manager.set_delay_image()
        for _ in range(duration):
            if stop_event.is_set():
                break
            time.sleep(1)
        pause_event.set()  # Set the pause event to resume monitoring
        pause_invoked = False
        icon_manager.set_icon_title(TITLE)

    threading.Thread(target=stop).start()

def on_clicked_stop_10(icon, item):
    pause_for_duration(600)  # 600 seconds = 10 minutes

def on_clicked_stop_30(icon, item):
    pause_for_duration(1800)  # 1800 seconds = 30 minutes

def on_clicked_stop_60(icon, item):
    pause_for_duration(3600)  # 3600 seconds = 60 minutes

def on_clicked_resume(icon, item):
    pause_event.set()  # Set the pause event to resume monitoring
    icon_manager.set_icon_title(TITLE)
    print("Resuming...")

def on_clicked_separator(icon, item):
    icon_manager.set_basic_image()
    return

def on_clicked_subscriptions(icon, item):
    json_data = json.dumps(get_all_subscriptions(), indent=4, sort_keys=True)
    file_path = "subscriptions.txt"
    with open(file_path, 'w') as file:
        file.write(json_data)
    os.startfile(file_path)


def setup(icon):
    icon.visible = True
    icon.menu = pystray.Menu(
        pystray.MenuItem("Stop for 10 minutes", on_clicked_stop_10),
        pystray.MenuItem("Stop for 30 minutes", on_clicked_stop_30),
        pystray.MenuItem("Stop for 60 minutes", on_clicked_stop_60),
        pystray.MenuItem("Resume", on_clicked_resume),
        pystray.MenuItem("_______________________", on_clicked_separator),
        pystray.MenuItem("Launch Rocket", on_clicked_show, default=True),
        pystray.MenuItem("Settings", on_clicked_settings),
        pystray.MenuItem("Rules", on_clicked_rules),
        pystray.MenuItem("Subscriptions", on_clicked_subscriptions),
        pystray.MenuItem("_______________________", on_clicked_separator),
        pystray.MenuItem("Quit", on_clicked_quit)
    )

def monitor_asyncio_subscriptions_websocket():
    global asyncio_loop
    asyncio_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(asyncio_loop)
    print("#2")
    try:
        asyncio_loop.run_until_complete(monitor_subscriptions_websocket())
    except Exception as e:
        print(f"Exception: {e}")
    finally:
        print("Finally")
        if g_rocketChat:
            g_rocketChat.cleanup_pending_task(asyncio_loop)
        print("Finally end")    

def stop_asyncio_subscriptions_websocket():
    global asyncio_loop
    asyncio_stop_event.set()
    if g_rocketChat:
        g_rocketChat.stop()
    # g_rocketChat.cancel_task(asyncio_loop)

def my_on_escalation(channel):
     icon_manager.notify(f"You have still unread messages from {channel}", "Unread messages")

def my_on_file_changed(filename):
    if filename=='config.json':
        load_config()
    else:
        icon_manager.notify(f"Rules reloaded", "Rules")  

def my_on_unread_message(matching_rule, subscription, is_new_message):
    fname = subscription.get('fname')
    rid = subscription.get('rid')    
    icon_manager.set_notification_image(matching_rule.get("icon", rules_manager.DEFAULTS.get("icon")), matching_rule.get("prior"))
    if is_new_message:
        icon_manager.play_sound(matching_rule.get("sound", rules_manager.DEFAULTS.get("sound")))
        if (matching_rule.get("preview", rules_manager.DEFAULTS.get("preview"))) == "True":
            icon_manager.notify(f"{get_last_message_text(rid)}", fname)        



if __name__ == "__main__":
    icon_manager.set_icon_title(TITLE)
    load_config()
    rules_manager.set_on_escalation(my_on_escalation)
    rules_manager.set_on_file_changed(my_on_file_changed, stop_event)  # starts a new thread   
    rules_manager.set_on_unread_message(my_on_unread_message)
    pause_event.set()  # Ensure the pause event is initially set to allow monitoring
    threading.Thread(target=monitor_all_subscriptions).start()
       
    threading.Thread(target=monitor_asyncio_subscriptions_websocket).start()
    time.sleep(1)
    # for sig in (signal.SIGINT, signal.SIGTERM):
    #     asyncio_loop.add_signal_handler(sig, stop_loop)


    icon_manager.icon.run(setup=setup)

