import pystray
from PIL import Image
from pystray import MenuItem as item
import time

import json
import threading
import os
from datetime import datetime, timedelta
from  rocketchat_manager import RocketchatManager
 
from icon_manager import icon_manager
from rules_manager import rules_manager

TITLE = "Better Rocket Icon"
C_MAIN_LOOP_WAIT_TIME=1 #sec

rules_manager.ensure_local_files()
pause_invoked = False  # Flag to check if pause_event.clear() was invoked
stop_event = threading.Event()
pause_event = threading.Event()  # Event to control pausing
subscription_lock = threading.Lock()
rc_manager = RocketchatManager( subscription_lock, pause_event)


# Load configuration from config.json
def load_config():
    global ROCKET_PROGRAM, TITLE 
    try:
        config = rules_manager.load_config()
        ROCKET_PROGRAM = config['ROCKET_PROGRAM']
        with subscription_lock:
            rc_manager.parse_config(config)
        icon_manager.notify("Config loaded", TITLE)     
        
    except Exception as e:
        print(f"Error reading config file {e}")

def get_channels_for_messages(channels):
    updates = []
    for channel_id in channels:
          json = rc_manager.get_subscription_for_channel(channel_id)
          updates.append(json.get('subscription'))
    return {"update":updates}
    
def check_config_loaded():
    if not rules_manager.rules_are_loaded():
        my_on_error("Error reading rules.json file. Please go to Rules and verify your JSON syntax, and try again.")
        stop_event.wait(10)
        return False 

    if not rules_manager.config_is_loaded():
        my_on_error("Error reading config.json file. Please go to Settings and verify your JSON syntax, and try again.")
        stop_event.wait(10)
        return False
    return True             

def monitor_all_subscriptions():
    time.sleep(1)
    print(f"Starting loop")
    try:
        while not stop_event.is_set():
            pause_event.wait()  # Wait for the pause event to be set
            if not check_config_loaded():
                continue

            with subscription_lock:      
                data = get_channels_for_messages(rc_manager.unread_messages)
                if data:
                    updates = data.get('update', [])
                    icon_manager.reset_priority()
                    for sub in updates:
                        rules_manager.process_subscription(sub, rc_manager.unread_messages)                
                    if rules_manager.unread_counts:
                        summary = "\n".join([f"{fname}: {unread}" for fname, unread in rules_manager.unread_counts.items()])
                    else:
                        summary = "No new messages"
                    icon_manager.set_icon_title(summary)                


                if len(rules_manager.unread_counts) == 0:
                    icon_manager.set_basic_image()
            stop_event.wait(C_MAIN_LOOP_WAIT_TIME)
    finally:
        rc_manager.stop()


def on_clicked_quit(icon, item):
    if item.text == "Quit":
        print("Quit.")        
        rc_manager.stop()
        stop_event.set()
        pause_event.set()  # Resume if paused to ensure clean exit
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
    json_data = json.dumps(rc_manager.get_all_subscriptions(), indent=4, sort_keys=True)
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

def my_on_error(text):
    icon_manager.set_icon_title(text)
    icon_manager.set_error_image()     

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
            icon_manager.notify(f"{rc_manager.get_last_message_text(rid)}", fname)        



if __name__ == "__main__":
    icon_manager.set_icon_title(TITLE)
    load_config()
    rules_manager.set_on_escalation(my_on_escalation)
    rules_manager.set_on_file_changed(my_on_file_changed, stop_event)  # starts a new thread   
    rules_manager.set_on_unread_message(my_on_unread_message)
    pause_event.set()  # Ensure the pause event is initially set to allow monitoring
    threading.Thread(target=monitor_all_subscriptions).start()
    rc_manager.set_on_error_callback(my_on_error)
    rc_manager.start() # start a new thread

    time.sleep(1)
    # for sig in (signal.SIGINT, signal.SIGTERM):
    #     asyncio_loop.add_signal_handler(sig, stop_loop)


    icon_manager.icon.run(setup=setup)

