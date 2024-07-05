import pystray
from PIL import Image
from pystray import MenuItem as item
import sys
import time
import requests
import json
import threading
import os
from datetime import datetime, timedelta
import winsound
import shutil

TITLE = "Better Rocket Icon"

# Create the icon
icon = pystray.Icon("basic")

# Get the local user directory path
local_user_dir = os.path.expanduser("~/.rocketIcon")

# Check if .rocketIcon directory exists, if not, create it and copy files
def ensure_local_files():
    if not os.path.exists(local_user_dir):
        os.makedirs(local_user_dir)
        shutil.copy('config.json', os.path.join(local_user_dir, 'config.json'))
        shutil.copy('rules.json', os.path.join(local_user_dir, 'rules.json'))

ensure_local_files()

# Paths to the local config and rules files
config_path = os.path.join(local_user_dir, 'config.json')
rules_path = os.path.join(local_user_dir, 'rules.json')

# Get initial modification times
config_mtime = os.path.getmtime(config_path)
rules_mtime = os.path.getmtime(rules_path)
stop_event = threading.Event()
pause_event = threading.Event()  # Event to control pausing
pause_invoked = False  # Flag to check if pause_event.clear() was invoked
last_fulfilled = {}
escalation_times = {}

def load_json_with_comments(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()
    lines = [line for line in lines if not line.strip().startswith(';')]
    json_content = '\n'.join(lines)
    return json.loads(json_content)

# Load configuration from config.json
def load_config():
    global config, ROCKET_USER_ID, ROCKET_TOKEN, SERVER_ADDRESS, ROCKET_PROGRAM, TITLE, HEADERS
    config = load_json_with_comments(config_path)
    ROCKET_USER_ID = config['ROCKET_USER_ID']
    ROCKET_TOKEN = config['ROCKET_TOKEN']
    SERVER_ADDRESS = config['SERVER_ADDRESS']
    ROCKET_PROGRAM = config['ROCKET_PROGRAM']
    HEADERS = {
        'X-Auth-Token': ROCKET_TOKEN,
        'X-User-Id': ROCKET_USER_ID
    }
    icon.notify("Config loaded", TITLE)

# Load rules from rules.json
def load_rules():
    global DEFAULTS, RULES
    try:
        rules_config = load_json_with_comments(rules_path)
        DEFAULTS = rules_config['defaults']
        RULES = rules_config['rules']
        icon.notify("Rules loaded", TITLE)
    except Exception as e:
        icon.notify("Error reading rules.json file. Please go to Rules and verify your JSON syntax, and try again.", "Rules error")
        set_icon_title("Error reading rules.json file. Please go to Rules and verify your JSON syntax, and try again.")
        set_error_image()
        RULES = {}

def set_basic_image():
    icon.icon = Image.open("icons/bubble2.png")

def set_error_image():
    icon.icon = Image.open("icons/bubble2error.png")

def set_notification_image(icon_name):
    print(f"  set_notification_image {icon_name}")
    icon.icon = Image.open(f"icons/{icon_name}")

def set_delay_image():
    icon.icon = Image.open("icons/bubble2delay.png")

def play_sound(sound_name):
    print(f"  play_sound {sound_name}")
    winsound.PlaySound(f"sounds/{sound_name}", winsound.SND_FILENAME | winsound.SND_ASYNC)

def get_subscriptions():
    try:
        response = requests.get(f'{SERVER_ADDRESS}/api/v1/subscriptions.get', headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch data. Status code: {response.status_code}")
            set_icon_title(f"Failed to fetch data. Status code: {response.status_code}")
            set_error_image()
            return None
    except Exception as e:
        print(f"Network error: {e}")
        set_icon_title(f"Network error: {e}")
        set_error_image()
        return None

def all_rules_fulfilled(channel_name, channel_type, output_rule, userMentions):
    global last_fulfilled

    # Find the matching rule
    matching_rule = None
    for rule in RULES:
        if (rule['name'] == channel_name or rule['name'] == "type:*" or rule['name'] == f"type:{channel_type}") and rule.get('active', "True") == "True":
            matching_rule = rule
            break

    if not matching_rule:
        print("No matching rule found")
        return False

    output_rule.update(matching_rule)

    if matching_rule.get('ignore', "False") == "True":
        return False

    delay = int(matching_rule.get('delay', DEFAULTS.get('delay', "10")))
    now = datetime.now()

    if channel_name in last_fulfilled:
        elapsed_time = (now - last_fulfilled[channel_name]).total_seconds()
        if elapsed_time >= delay or userMentions > 0:
            last_fulfilled[channel_name] = now
            return True
        else:
            return False
    else:
        last_fulfilled[channel_name] = now
        return True

def check_escalation(channel, rule):
    now = datetime.now()
    escalation_time = int(rule.get('escalation',  DEFAULTS.get('escalation', "99999999999") ))
    if escalation_time > 0:
        if channel in escalation_times:
            elapsed_time = (now - escalation_times[channel]).total_seconds()
            if elapsed_time >= escalation_time:
                icon.notify(f"You have still unread messages from {channel}", "Unread messages")
        else:
            escalation_times[channel] = now

def set_icon_title(title):
    if len(title) > 128:
        title = title[:128]
    icon.title = title

def monitor_subscriptions():
    unread_counts = {}
    time.sleep(1)
    print(f"Starting loop")
    while not stop_event.is_set():
        pause_event.wait()  # Wait for the pause event to be set

        if len(RULES) == 0:
            set_error_image()
            stop_event.wait(10)
            continue

        data = get_subscriptions()
        if data:
            if len(unread_counts)==0:
                set_basic_image()
            updates = data.get('update', [])
            for sub in updates:
                open = sub.get('open')
                if open == True:
                    unread = int(sub.get('unread'))
                    fname = sub.get('fname')
                    chtype = sub.get('t')

                    userMentions = sub.get('userMentions', 0)

                    if unread > 0:
                        matching_rule = {}
                        if all_rules_fulfilled(fname, chtype, matching_rule, userMentions):
                            print(f"New message in '{fname}' Rule: {matching_rule.get('name', 'Default')}")
                            set_notification_image(matching_rule.get("icon", DEFAULTS.get("icon")))
                            if unread_counts.get(fname, 0) < unread:
                                play_sound(matching_rule.get("sound", DEFAULTS.get("sound")))
                            unread_counts[fname] = unread
                            check_escalation(fname, matching_rule)
                    elif fname in unread_counts:
                        del unread_counts[fname]
                        del escalation_times[fname]

            # Summarize the unread messages
            if unread_counts:
                summary = "\n".join([f"{fname}: {unread}" for fname, unread in unread_counts.items()])
            else:
                summary = "No new messages"

            set_icon_title(summary)
        stop_event.wait(10)

def monitor_file_changes():
    global config_mtime, rules_mtime
    while not stop_event.is_set():
        new_config_mtime = os.path.getmtime(config_path)
        new_rules_mtime = os.path.getmtime(rules_path)

        if new_config_mtime != config_mtime:
            config_mtime = new_config_mtime
            load_config()
            print("Config reloaded.")

        if new_rules_mtime != rules_mtime:
            rules_mtime = new_rules_mtime
            load_rules()
            print("Rules reloaded.")

        time.sleep(5)

def on_clicked_quit(icon, item):
    print(f"Menu click ")
    if item.text == "Quit":
        stop_event.set()
        pause_event.set()  # Resume if paused to ensure clean exit
        icon.stop()
        print("Normal exit.")

def on_clicked_show(icon, item):
    global pause_invoked
    if pause_invoked:
        icon.icon = Image.open("icons/bubble2delay.png")
    else:
        icon.icon = Image.open("icons/bubble2launch.png")
    os.startfile(ROCKET_PROGRAM)

def on_clicked_settings(icon, item):
    os.startfile(config_path)

def on_clicked_rules(icon, item):
    os.startfile(rules_path)

def stop_for_duration(duration):
    global pause_invoked
    def stop():
        global pause_invoked
        pause_event.clear()  # Clear the pause event to block monitoring
        pause_invoked = True
        resume_time = datetime.now() + timedelta(seconds=duration)
        set_icon_title(f"Paused until {resume_time.strftime('%H:%M')}")
        set_delay_image()
        for _ in range(duration):
            if stop_event.is_set():
                break
            time.sleep(1)
        pause_event.set()  # Set the pause event to resume monitoring
        pause_invoked = False
        set_icon_title(TITLE)

    threading.Thread(target=stop).start()

def on_clicked_stop_10(icon, item):
    stop_for_duration(600)  # 600 seconds = 10 minutes

def on_clicked_stop_30(icon, item):
    stop_for_duration(1800)  # 1800 seconds = 30 minutes

def on_clicked_stop_60(icon, item):
    stop_for_duration(3600)  # 3600 seconds = 60 minutes

def on_clicked_resume(icon, item):
    pause_event.set()  # Set the pause event to resume monitoring
    set_icon_title(TITLE)
    print("Resuming...")

def on_clicked_separator(icon, item):
    set_basic_image()
    return

def on_clicked_subscriptions(icon, item):
    json_data = json.dumps(get_subscriptions(), indent=4, sort_keys=True)
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

if __name__ == "__main__":
    set_icon_title(TITLE)
    load_config()
    load_rules()
    set_basic_image()
    pause_event.set()  # Ensure the pause event is initially set to allow monitoring
    threading.Thread(target=monitor_subscriptions).start()
    threading.Thread(target=monitor_file_changes).start()
    icon.run(setup=setup)
