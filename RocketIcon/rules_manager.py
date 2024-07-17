import os
import json
import time
from datetime import datetime
import threading
from collections import OrderedDict

class SubscriptionStack:
    def __init__(self):
        self.stack = OrderedDict()

    def push(self, subscription):
        rid = subscription.get('rid')
        if rid in self.stack:
            del self.stack[rid]
        self.stack[rid] = subscription

    def pop(self):
        if self.stack:
            return self.stack.popitem()[1]
        return None

    def remove(self, rid):
        if rid in self.stack:
            del self.stack[rid]
    
    def clear_all(self):
        self.stack.clear()

import threading

class RulesManager:
    def __init__(self, local_user_dir):
        self.local_user_dir = local_user_dir
        self.config_path = os.path.join(local_user_dir, 'config.json')
        self.rules_path = os.path.join(local_user_dir, 'rules.json')
        self.config = {}
        self.DEFAULTS = {}
        self.RULES = {}
        self._last_fullfillment_time = {}
        self.unread_counts = {}        
        self._escalation_times = {}        
        self.config_mtime = os.path.getmtime(self.config_path)
        self.rules_mtime = os.path.getmtime(self.rules_path)
        self._on_escalation_callback = None
        self._on_file_changed = None
        self._on_unread_message = None
        self.subscription_stack = SubscriptionStack()
        self.load_config()
        self.load_rules()
 
    def reset(self):
        self._last_fullfillment_time = {}
        self.unread_counts = {}  
        self.subscription_stack.clear_all()  

    def load_json_with_comments(self, file_path):
        with open(file_path, 'r') as file:
            lines = file.readlines()
        lines = [line for line in lines if not line.strip().startswith(';')]
        json_content = '\n'.join(lines)
        return json.loads(json_content)

    def load_config(self):
        try:
            self.config = self.load_json_with_comments(self.config_path)
            return self.config
        except Exception as e:
            print(f"Error reading config.json file: {e}")
            self.config = {}    
        finally:
            self.reset_messages_counters()            

    def load_rules(self):
        try:
            rules_config = self.load_json_with_comments(self.rules_path)
            self.DEFAULTS = rules_config['defaults']
            self.RULES = rules_config['rules']
        except Exception as e:
            print(f"Error reading rules.json file: {e}")
            self.RULES = {}
        finally:
            self.reset_messages_counters()  

    def rules_are_loaded(self):
        if len(self.RULES) == 0:
            return False
        else:
            return True    
               
    def config_is_loaded(self):
        if len(self.config) == 0:
            return False
        else:
            return True    
                       

    def set_on_file_changed(self, callback, stop_event : threading.Event):
        self._on_file_changed = callback
        self._file_monitor_stop_event = stop_event
        threading.Thread(target=self.monitor_file_changes).start() 

    def monitor_file_changes(self):
        if not self._file_monitor_stop_event:
            raise ValueError("file_monitor_stop_event not set")

        while not self._file_monitor_stop_event.is_set():
            new_config_mtime = os.path.getmtime(self.config_path)
            new_rules_mtime = os.path.getmtime(self.rules_path)

            if new_config_mtime != self.config_mtime:
                self.config_mtime = new_config_mtime
                self.load_config()
                print("Config reloaded.")
                if self._on_file_changed:
                    self._on_file_changed("config.json")

            if new_rules_mtime != self.rules_mtime:
                self.rules_mtime = new_rules_mtime
                self.load_rules()
                print("Rules reloaded.")
                if self._on_file_changed:
                    self._on_file_changed("rules.json")                

            time.sleep(5)         


    def find_matching_rule(self, channel_name, channel_type, unread_messages):
        for i, rule in enumerate(self.RULES, start=1):
            rule["prior"] = i
            if (rule['name'] == channel_name or rule['name'] == "type:*" or rule['name'] == f"type:{channel_type}") and rule.get('active', "True") == "True":
                if rule.get('is_videoconf'):
                    if self.has_videoconf_qualifier(unread_messages, rule.get('is_videoconf')):
                        return rule
                else:
                    return rule
        return None

    def has_videoconf_qualifier(self, unread_messages, value):
        if unread_messages:
            for message in unread_messages:
                for msg_id, msg_content in message.items():
                    if value == "True" and msg_content.get("qualifier") == "videoconf":
                        return True
                    elif value == "False" and not msg_content.get("qualifier") == "videoconf":
                        return True
        return False
    
    def all_rules_fulfilled(self, channel_name, channel_type, output_rule, userMentions, unread_messages, is_historical):
            matching_rule = self.find_matching_rule(channel_name, channel_type, unread_messages)
            if not matching_rule:
                print("No matching rule found")
                return False

            output_rule.update(matching_rule)
            if matching_rule.get('ignore', "False") == "True":
                return False
            if is_historical:
                return True #no delay
            delay = int(matching_rule.get('delay', self.DEFAULTS.get('delay', "10")))
            now = datetime.now()
            if channel_name in self._last_fullfillment_time or userMentions > 0:
                elapsed_time = (now - self._last_fullfillment_time[channel_name]).total_seconds()
                if elapsed_time >= delay or userMentions > 0:
                    if self._last_fullfillment_time[channel_name]:
                        del self._last_fullfillment_time[channel_name]
                    return True
                else:
                    return False
            else:
                self._last_fullfillment_time[channel_name] = now
                return False # don't notify immediately - just wait    
            
    def set_on_escalation(self, callback):
        self._on_escalation_callback = callback

    def check_escalation(self, channel, rule):
            now = datetime.now()
            escalation_time = int(rule.get('escalation',  self.DEFAULTS.get('escalation', "99999999999") ))
            if escalation_time > 0:
                if channel in self._escalation_times:
                    elapsed_time = (now - self._escalation_times[channel]).total_seconds()
                    if elapsed_time >= escalation_time:
                        self._on_escalation_callback(channel)
                        self._escalation_times[channel] = now
                else:
                    self._escalation_times[channel] = now  

    def reset_messages_counters(self):
        print("reset_messages_counters")
        self.unread_counts = {} 
        self.subscription_stack.clear_all()      
 
    def set_on_unread_message(self, callback):
        self._on_unread_message = callback

    def set_unread_counts(self, fname, unread):
        self.unread_counts[fname] = unread

    def is_last_message_historical(self, unread_messages,  rid):
        if rid not in unread_messages or not unread_messages[rid]:
            return None
        last_message = unread_messages[rid][-1]
        try:
            last_message_key = list(last_message.keys())[0]
        except:
            return False
        return last_message_key=="historical"
    
    def process_subscription(self, subscription, unread_messages):
        open = subscription.get('open')
        if open == True:
            unread = int(subscription.get('unread'))
            fname = subscription.get('fname')
            chtype = subscription.get('t')
            rid = subscription.get('rid')
            userMentions = subscription.get('userMentions', 0)
            print( f"process_subscription {fname} unread={unread}")
            if unread > 0:
                matching_rule = {}
                is_historical = self.is_last_message_historical(unread_messages, rid)
                is_new_message = (not is_historical) and self.unread_counts.get(fname, 0) < unread
                print(f" is_new_message={is_new_message} ucount={self.unread_counts.get(fname, 0)} unread={unread}")
                if  (is_historical or is_new_message) and self.all_rules_fulfilled(fname, chtype, matching_rule, 
                                                                userMentions, unread_messages.get(rid), is_historical):
                    print(f"New message in '{fname}' Rule: {matching_rule.get('name', 'Default')} Historical={is_historical}")
                    
                    if self._on_unread_message:
                        self._on_unread_message(matching_rule, subscription, is_new_message)
                    self.unread_counts[fname] = unread
                    self.check_escalation(fname, matching_rule)
                    self.subscription_stack.push(subscription)
            else:
                if fname in self.unread_counts:
                    del self.unread_counts[fname]
                if fname in self._escalation_times:
                    del self._escalation_times[fname]
                if self.unread_counts.get(fname, 0) == 0:
                    if unread_messages.get(rid):
                        del unread_messages[rid]
                    self.subscription_stack.remove(rid)

    def get_room_to_visit(self):
        sub = self.subscription_stack.pop() 
        #https://chat.address.com/direct/Yme82NmFkeZu5s9khYme82NmFkeZu5s9kh
        #https://chat.address.com/group/group_fname  
        if sub:  
            if sub.get('t') == 'd':
                return f"direct/{sub.get('rid')}"
            else:
                return f"group/{sub.get('name')}"
        return ""



#rules_manager = RulesManager(os.path.expanduser("~/.rocketIcon"))
