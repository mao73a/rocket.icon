import pystray
from PIL import Image
import sys
import time
import requests
import json
import threading
import os
from datetime import datetime, timedelta
import winsound
import shutil
from rocketchat_async import RocketChat
import asyncio
import random

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
g_subscription_dict = {}
g_unread_subscription_list = []
g_unread_counts = {}
subscription_lock = threading.Lock()


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

# Load rules from rules.json
def load_rules():
    global DEFAULTS, RULES
    try:
        rules_config = load_json_with_comments(rules_path)
        DEFAULTS = rules_config['defaults']
        RULES = rules_config['rules']
    except Exception as e:
        RULES = {}

def get_subscriptions():
    try:
        response = requests.get(f'{SERVER_ADDRESS}/api/v1/subscriptions.get', headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch data. Status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"Network error: {e}")
        return None


def convert_to_wsl_address(server_address):
    if server_address.startswith("https://"):
        wsl_address = server_address.replace("https://", "wss://") + "/websocket"
    elif server_address.startswith("http://"):
        wsl_address = server_address.replace("http://", "ws://") + "/websocket"
    else:
        raise ValueError("Invalid server address scheme. Must start with 'http://' or 'https://'.")
    return wsl_address


def find_matching_rule(channel_name, channel_type):
        for rule in RULES:
            if (rule['name'] == channel_name or rule['name'] == "type:*" or rule['name'] == f"type:{channel_type}") and rule.get('active', "True") == "True":
                return rule
        return None

def handle_message1(channel_id, sender_id, msg_id, thread_id, msg, qualifier,
                   unread, repeated):
    """Simply print the message that arrived."""
    print(f"channel={channel_id} sender={sender_id} msgid={msg_id} txt={msg}  unread={unread}")

async def monitor_subscriptions_websocket():
    while True:
        print("#4")
        try:
            print("#5")
            rc = RocketChat()
            #await rc.start(address, username, password)
            # Alternatively, use rc.resume for token-based authentication:
            await rc.resume(convert_to_wsl_address(SERVER_ADDRESS), ROCKET_USER_ID, ROCKET_TOKEN)
            print("#6")
            # 1. Set up the desired callbacks...
            #for channel_id, channel_type in await rc.get_channels(): //to few informations returned :-(
            data = get_subscriptions()
            print("#7")
            if data:
                updates = data.get('update', [])
                for sub in updates:
                    fname = sub.get('fname')
                    chtype = sub.get('t')
                    channel_id = sub.get('rid')
                    open = sub.get('open')
                    if open==True:
                        matching_rule = find_matching_rule(fname, chtype)
                        #print('#8'+matching_rule.get('ignore', "False"))
                        if matching_rule and matching_rule.get('ignore', "False") == "False":
                            #print('# 9 ')
                            #print(f'subscribe: {fname} {channel_id}')
                            #g_subscription_dict[channel_id]=sub
                            await rc.subscribe_to_channel_messages(channel_id,  handle_message1)
                            print(f'subscribed to  {fname}  {channel_id}')
            # 2. ...and then simply wait for the registered events.
            await rc.run_forever()
            #stop_event.wait(10)
        except (RocketChat.ConnectionClosed,
                RocketChat.ConnectCallFailed) as e:
            print(f'Connection failed: {e}. Waiting a few seconds...')
            await asyncio.sleep(random.uniform(4, 8))
            print('Reconnecting...')
        except asyncio.CancelledError as e:              
                    print("Break it out")        
                    break                  

async def monitor_subscriptions_websocket2():
    while True:
        try:
            rc = RocketChat()
            # print(convert_to_wsl_address(SERVER_ADDRESS))
            # print(ROCKET_USER_ID)
            # print(ROCKET_TOKEN)
            await rc.resume(convert_to_wsl_address(SERVER_ADDRESS), ROCKET_USER_ID, ROCKET_TOKEN)
            for channel_id, channel_type in await rc.get_channels():
                print(f'subscribe: {channel_id}')
                await rc.subscribe_to_channel_messages(channel_id,  handle_message1)
            await rc.run_forever()
        except (RocketChat.ConnectionClosed,
                RocketChat.ConnectCallFailed) as e:
            print(f'Connection failed: {e}. Waiting a few seconds...')
            await asyncio.sleep(random.uniform(4, 8))
            print('Reconnecting...')

load_config()
load_rules()
asyncio.run(monitor_subscriptions_websocket())