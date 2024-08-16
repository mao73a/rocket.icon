import logging
import pystray
from pystray import  Menu,  MenuItem as item
import time
import shutil
import sys
import threading
import os
from datetime import datetime, timedelta
from RocketIcon import RocketchatManager, icon_manager, RulesManager
from RocketIcon.proxy_server import run_proxy_server, get_proxy_url
import requests
from global_hotkeys import *
import tkinter as tk
from tkinter import simpledialog, messagebox
import pyautogui
import json

config_path = os.path.expanduser("~/.rocketIcon")
logger = logging.getLogger(__name__)

TITLE = "Rocket Icon"
C_MAIN_LOOP_WAIT_TIME=1 #sec


class CustomDialog(simpledialog._QueryString):
    def click_after_delay(self, x, y, delay):
        for i in range(3):
            time.sleep(delay)
            pyautogui.click(x, y)

    def __init__(self, title, prompt, initialvalue=None, parent=None):
        self._parent = parent
        super().__init__(title, prompt, initialvalue=initialvalue, parent=parent)

    def body(self, master):
        self.attributes('-topmost', True)
        self.after(0, self.focus_and_click)
        return super().body(master)

    def focus_and_click(self):
        self.focus_force()
        self.update_idletasks()
        self.lift()

        # Calculate the center of the dialog window
        x = self.winfo_rootx() + self.winfo_width() // 2
        y = self.winfo_rooty() + self.winfo_height() // 2

        click_thread = threading.Thread(target=self.click_after_delay, args=(x, y, 0.3))
        click_thread.start()


def display_input_message(title, text, initialvalue):
    root = tk.Tk()
    root.withdraw()  # Hide the root window

    dialog = CustomDialog(title, text, initialvalue=initialvalue, parent=root)
    answer = dialog.result

    root.destroy()
    return answer


pause_invoked = False  # Flag to check if pause_event.clear() was invoked
stop_event = threading.Event()
pause_event = threading.Event()
subscription_lock = threading.Lock()
rules_manager = RulesManager(config_path)
rc_manager = RocketchatManager(subscription_lock, rules_manager)
g_last_preview_showed = {'rid':0,'name':'some name', 'text':'some text'}

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
    global ROCKET_PROGRAM, TITLE, AUTOAWAY_TIME_SEC
    try:
        config = rules_manager.load_config()
        ROCKET_PROGRAM = config['ROCKET_PROGRAM']
        AUTOAWAY_TIME_SEC = config.get('AUTOAWAY_TIME_SEC', 5*60)
        with subscription_lock:
            rc_manager.set_ROCKET_USER_ID(config['ROCKET_USER_ID'])
            rc_manager.set_ROCKET_TOKEN(config['ROCKET_TOKEN'])
            rc_manager.set_SERVER_ADDRESS(config['SERVER_ADDRESS'])
        icon_manager.notify("Config loaded", TITLE)

    except Exception as e:
        logger.info(f"Error reading config file {e}")

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

if sys.platform == 'win32':
    from ctypes import *

    class LASTINPUTINFO(Structure):
        _fields_ = [
            ('cbSize', c_uint),
            ('dwTime', c_int),
        ]

    def get_idle_duration():
        lastInputInfo = LASTINPUTINFO()
        lastInputInfo.cbSize = sizeof(lastInputInfo)
        if windll.user32.GetLastInputInfo(byref(lastInputInfo)):
            millis = windll.kernel32.GetTickCount() - lastInputInfo.dwTime
            return millis / 1000.0
        else:
            return 0
else:
    def get_idle_duration():
        return 0


def monitor_all_subscriptions():
    time.sleep(1)
    logger.info(f"Starting loop")
    counter = 1
    prev_status="Unknown"
    need_restore_status=""
    previous_time = time.time()
    try:
        while not stop_event.is_set():
            pause_event.wait()  # Wait for the pause event to be set
            if not check_config_loaded():
                continue

            with subscription_lock:
                current_time = time.time()
                elapsed_time = current_time - previous_time

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

                # if counter % 5 == 0:
                #     status = rc_manager.get_status()
                #     idle_duration_sec = get_idle_duration()
                #     if status!=prev_status:
                #         icon_manager.icon.update_menu()
                #         prev_status=status
                #         logger.info(f"User status is now {status}. AutoAway set to {AUTOAWAY_TIME_SEC}")
                #     if status=='online' and idle_duration_sec>AUTOAWAY_TIME_SEC:
                #         rc_manager.set_away('')
                #         need_restore_status=status
                #         icon_manager.set_away_image()
                #     elif need_restore_status and idle_duration_sec<=AUTOAWAY_TIME_SEC:
                #         rc_manager.set_user_status(need_restore_status)
                #         need_restore_status=""


            if elapsed_time > 5:
                logger.info("Reinitialize connections after wakeup...")
                if rc_manager.get_status()=='away':
                    rc_manager.set_online()
                restart() #restart after sleep

            counter += 1
            previous_time = time.time()
            stop_event.wait(C_MAIN_LOOP_WAIT_TIME)
    except Exception as e:
        logger.info(json.dumps(rc_manager.unread_messages, indent=4, sort_keys=True))
        logger.info(json.dumps(rules_manager.unread_counts, indent=4, sort_keys=True))
        logger.error("An error occurred", exc_info=True)
        logger.info(f"Fatal error {e}")
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
        logger.info("Quit.")
        quit()
        logger.info("Normal exit.")

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


def on_clicked_settings(icon, item):
    os.startfile(rules_manager.config_path)

def on_clicked_rules(icon, item):
    os.startfile(rules_manager.rules_path)

def pause_for_duration(duration):
    global pause_invoked
    status = rc_manager.get_status()
    def stop():
        global pause_invoked

        pause_event.clear()  # Clear the pause event to block monitoring
        pause_invoked = True
        resume_time = datetime.now() + timedelta(seconds=duration)
        rc_manager.set_busy(f"Busy until {resume_time.strftime('%H:%M')}")
        icon_manager.set_icon_title(f"Paused until {resume_time.strftime('%H:%M')}")
        icon_manager.set_delay_image()
        for _ in range(duration):
            if stop_event.is_set():
                break
            time.sleep(1)
        pause_event.set()  # Set the pause event to resume monitoring
        pause_invoked = False
        rc_manager.set_user_status(status,"")
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
    logger.info("Resuming...")

def on_clicked_separator(icon, item):
    icon_manager.set_basic_image()
    return

def on_clicked_online(icon, item):
    rc_manager.set_online()


def on_clicked_busy(icon, item):
    rc_manager.set_busy('')


def on_clicked_away(icon, item):
    rc_manager.set_away('')


def on_clicked_offline(icon, item):
    rc_manager.set_offline()


def restart():
    pause_event.clear()
    rules_manager.reset()
    rc_manager.restart()
    rc_manager.mark_read()
    pause_event.set()

def on_mark_read():
    print("on_mark_read")
    rc_manager.mark_read()
    restart()


def on_quick_response():
    global g_last_preview_showed
    print("on_quick_response")
    #os.startfile("C:/Ustawienia/_workdir/delphi/sticky/Sticky.exe")
    if g_last_preview_showed.get('rid'):
        answer = display_input_message("Quick response...", f"To {g_last_preview_showed.get('name')} message: \"{g_last_preview_showed.get('text')[:30]}\"...", "")
        if answer:
            rc_manager.send_message(g_last_preview_showed.get('rid'), answer)
            rc_manager.mark_read()
            restart()
    else:
        messagebox.showinfo(title="Quick reposne", message="You have no message to answer.")


def on_version(icon, item):
    os.startfile(f"https://github.com/mao73a/rocket.icon/releases")


def setup(icon):
    icon.visible = True
    icon.menu = pystray.Menu(
        pystray.MenuItem("Version 1.0.4", on_version),
        pystray.MenuItem("Quit", on_clicked_quit),
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
        pystray.MenuItem("Quick response", on_quick_response),
        pystray.MenuItem("Mark all as read", on_mark_read)
    )


def my_on_api_callback(action):
    logger.info(f"API call {action}")
    if action=="markallread":
        on_mark_read()
    elif action=="quickresponse":
        on_quick_response()
    elif action=="showrocketapp":
        on_clicked_show(None, None)



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
    global g_last_preview_showed
    fname = subscription.get('fname')
    rid = subscription.get('rid')
    icon_manager.set_notification_image(matching_rule.get("icon", rules_manager.DEFAULTS.get("icon")), matching_rule.get("prior"),
                                            matching_rule.get("blink_delay", rules_manager.DEFAULTS.get("blink_delay", 0)))
    if is_new_message:
        icon_manager.play_sound(matching_rule.get("sound", rules_manager.DEFAULTS.get("sound")))
        if (matching_rule.get("preview", rules_manager.DEFAULTS.get("preview"))) == "True":
            g_last_preview_showed={'rid':rid, 'name':fname, 'text': rc_manager.get_last_message_text(rid)}
            icon_manager.notify(f"{rc_manager.get_last_message_text(rid)}", fname)


if __name__ == "__main__":
    logging.basicConfig(filename=os.path.join(config_path, 'rocketicon.log'), level=logging.INFO, format = '%(asctime)s  %(message)s')
    logger.info('Started')
    icon_manager.set_icon_title(TITLE)
    bindings = [
        ["control + m", None, on_mark_read, True],
        ["control + alt + m", None, on_quick_response, True]
    ]
    #register_hotkeys(bindings)
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
    proxy_thread = threading.Thread(target=run_proxy_server, args=(rc_manager,rules_manager,my_on_api_callback))
    proxy_thread.start()

    time.sleep(1)
    # for sig in (signal.SIGINT, signal.SIGTERM):
    #     asyncio_loop.add_signal_handler(sig, stop_loop)

    icon_manager.icon.run(setup=setup)
    #clear_hotkeys()
    logger.info('Finished')


