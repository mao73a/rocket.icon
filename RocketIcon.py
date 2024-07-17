import pystray
from pystray import  Menu,  MenuItem as item
import time
import shutil
import json
import threading
import os
from datetime import datetime, timedelta
from RocketIcon import RocketchatManager, icon_manager, RulesManager
from RocketIcon.proxy_server import run_proxy_server, get_proxy_url
import requests
 
TITLE = "Rocket Icon"
C_MAIN_LOOP_WAIT_TIME=1 #sec
       
pause_invoked = False  # Flag to check if pause_event.clear() was invoked
stop_event = threading.Event()
pause_event = threading.Event()
subscription_lock = threading.Lock()
config_path = os.path.expanduser("~/.rocketIcon")
rules_manager = RulesManager(config_path)
rc_manager = RocketchatManager(subscription_lock, rules_manager)

# Check if .rocketIcon directory exists, if not, create it and copy files
def ensure_local_files():
    global config_path
    if not os.path.exists(os.path.join(config_path, 'config.json')):
        try:
            os.makedirs(config_path)
        finally:            
            shutil.copy('config.json', os.path.join(config_path, 'config.json'))
            shutil.copy('rules.json', os.path.join(config_path, 'rules.json'))


ensure_local_files()

# Load configuration from config.json
def load_config():
    global ROCKET_PROGRAM, TITLE 
    try:
        config = rules_manager.load_config()
        ROCKET_PROGRAM = config['ROCKET_PROGRAM']
        with subscription_lock:
            rc_manager.set_ROCKET_USER_ID(config['ROCKET_USER_ID'])
            rc_manager.set_ROCKET_TOKEN(config['ROCKET_TOKEN'])
            rc_manager.set_SERVER_ADDRESS(config['SERVER_ADDRESS'])
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
    counter = 1
    previous_time = time.time()    
    try:
        while not stop_event.is_set():
            pause_event.wait()  # Wait for the pause event to be set
            if not check_config_loaded():
                continue

            with subscription_lock:   
                current_time = time.time()
                elapsed_time = current_time - previous_time 
                previous_time = current_time                 
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
            if elapsed_time > 5:
                print("Reinitialize connections after wakeup...")
                restart() #restart after sleep
            counter += 1    
    except Exception as e:
        print(f"Fatal error {e}")
        quit()
    finally:
        rc_manager.stop()

def quit():
    rc_manager.stop()
    stop_event.set()
    pause_event.set()  # Resume if paused to ensure clean exit
    icon_manager.stop()
    if proxy_thread:
        requests.get(f"{get_proxy_url()}/shutdown")
        proxy_thread.join()        



def on_clicked_quit(icon, item):
    if item.text == "Quit":
        print("Quit.")   
        quit()
        print("Normal exit.")

def on_clicked_show(icon, item):
    global pause_invoked
    if pause_invoked:
        icon_manager.set_delay_image()
    else:
        icon_manager.set_launch_image()
    launch_program = ROCKET_PROGRAM    
    if "{ROOM}" in launch_program:
        launch_program = launch_program.replace("{ROOM}", rules_manager.get_room_to_visit(), 1)
    os.startfile(launch_program)

def on_search(icon, item):
    os.startfile(f"{get_proxy_url()}")

def on_version(icon, item):
     os.startfile(f"https://github.com/mao73a/rocket.icon/releases")

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
    pause_for_duration(600)  #10 minutes

def on_clicked_stop_25(icon, item):
    pause_for_duration(60*25)  # 25 minutes

def on_clicked_stop_60(icon, item):
    pause_for_duration(3600)  # 60 minutes

def on_clicked_stop_120(icon, item):
    pause_for_duration(7200)  # 120  minutes

def on_clicked_resume(icon, item):
    pause_event.set()  # Set the pause event to resume monitoring
    icon_manager.set_icon_title(TITLE)
    print("Resuming...")

def on_clicked_separator(icon, item):
    icon_manager.set_basic_image()
    return

def on_clicked_online(icon, item):
    rc_manager.set_online()
    update_radio_items(icon)

def on_clicked_busy(icon, item):
    rc_manager.set_busy('')
    update_radio_items(icon)

def on_clicked_away(icon, item):
    rc_manager.set_away('')    
    update_radio_items(icon)

def on_clicked_offline(icon, item):
    rc_manager.set_offline()       
    update_radio_items(icon)
    
def restart():
    pause_event.clear() 
    rules_manager.reset()    
    rc_manager.restart()
    rc_manager.mark_read()
    pause_event.set()

def on_mark_read():
    rc_manager.mark_read()    
    restart()

def update_radio_items(icon):
    for item in icon.menu:
        if isinstance(item, pystray.MenuItem) and getattr(item, 'radio', False):
            if item.checked and callable(item.checked):
                item.checked(item)

def setup(icon):
    icon.visible = True
    icon.menu = pystray.Menu(
  
        pystray.MenuItem("Version 1.0.2", on_version),
        pystray.MenuItem("Settings", on_clicked_settings),
        pystray.MenuItem("Rules", on_clicked_rules),
        pystray.MenuItem(pystray.Menu.SEPARATOR, on_clicked_separator),     
        pystray.MenuItem("Search", on_search),             
        pystray.MenuItem(pystray.Menu.SEPARATOR, on_clicked_separator),  
        pystray.MenuItem("Pause...",  
                Menu(pystray.MenuItem("Pause for 10 minutes", on_clicked_stop_10),
                     pystray.MenuItem("Pause for 25 minutes", on_clicked_stop_25),
                     pystray.MenuItem("Pause for 60 minutes", on_clicked_stop_60),
                     pystray.MenuItem("Pause for 120 minutes",on_clicked_stop_120))),
        pystray.MenuItem("Resume", on_clicked_resume),
        pystray.MenuItem(pystray.Menu.SEPARATOR, on_clicked_separator),          
        pystray.MenuItem('Online',  on_clicked_online, checked=lambda item: rc_manager.get_status()=="online", radio=True),
        pystray.MenuItem('Busy',    on_clicked_busy, checked=lambda item: rc_manager.get_status()=="busy", radio=True),
        pystray.MenuItem('Away',    on_clicked_away, checked=lambda item: rc_manager.get_status()=="away", radio=True),
        pystray.MenuItem('Offline', on_clicked_offline, checked=lambda item: rc_manager.get_status()=="offline", radio=True),             
        pystray.MenuItem(pystray.Menu.SEPARATOR, on_clicked_separator),
        pystray.MenuItem("Launch Rocket", on_clicked_show, default=True),       
        pystray.MenuItem("Mark all as read", on_mark_read),                 
        pystray.MenuItem("Quit", on_clicked_quit)
    )
    update_radio_items(icon)

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

def my_on_reload():
    icon_manager.set_reload_image()

def my_on_unread_message(matching_rule, subscription, is_new_message):
    fname = subscription.get('fname')
    rid = subscription.get('rid')    
    icon_manager.set_notification_image(matching_rule.get("icon", rules_manager.DEFAULTS.get("icon")), matching_rule.get("prior"),
                                            matching_rule.get("blink_delay", rules_manager.DEFAULTS.get("blink_delay", 0)))
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
    rc_manager.set_on_reload(my_on_reload)
    rc_manager.set_online()
    rc_manager.start() # start a new thread

    # Start the proxy server in a separate thread
    # Start the proxy server in a separate thread
    proxy_thread = threading.Thread(target=run_proxy_server, args=(rc_manager,rules_manager, ))
    proxy_thread.start()
  
    time.sleep(1)
    # for sig in (signal.SIGINT, signal.SIGTERM):
    #     asyncio_loop.add_signal_handler(sig, stop_loop)

    icon_manager.icon.run(setup=setup)

