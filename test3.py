import json
g_unread_subscription_list = {}
#{'motest': ['msg_101', 'msg_102', 'msg_103'], 'qq': ['msg_202', 'msg_203']}
#{'motest':['msg_101':{"text":"abc"}, 'msg_102':{"text":"efg"} ]}
#{'motest':['msg_101':{"text":"abc"}, 'msg_102':{"text":"efg",  "qualifier":"videoconf"} ]}

def remove_message(channel_id, msg_id):
 
    for msg_dict in g_unread_subscription_list[channel_id]:
        if msg_id in msg_dict:
            g_unread_subscription_list[channel_id].remove(msg_dict)
            break  # Exit loop after removing the message

def remove_all_historical_messages(channel_id):
    if channel_id in g_unread_subscription_list:
        g_unread_subscription_list[channel_id] = [msg for msg in g_unread_subscription_list[channel_id] if 'historical' not in msg]
        if not g_unread_subscription_list[channel_id]:
            del g_unread_subscription_list[channel_id]

def add_historical_message(channel_id):
        if not g_unread_subscription_list.get(channel_id):                    
            g_unread_subscription_list[channel_id] = []        
        g_unread_subscription_list[channel_id].append({'historical': {"text": "", "qualifier":""}})
        print("   -- add_historical_message dodano ")

def monitor(channel_id, unread, msg_id, msg, qualifier):
 
    if not g_unread_subscription_list.get(channel_id):
        if not unread:
            return
        else:
            g_unread_subscription_list[channel_id] = []
    if unread:
        g_unread_subscription_list[channel_id].append({msg_id: {"text": msg, "qualifier":qualifier}})
        print("   -- handle_message1 dodano ")
    else:
        remove_message(channel_id, msg_id)
        if len(g_unread_subscription_list[channel_id])==0:
            del g_unread_subscription_list[channel_id]
        print("   -- handle_message1 usunieto ")

monitor("motest", True, "msg_101", "Ala ma kota", "None")
monitor("motest", True, "msg_102", "Ela ma kota", "videoconf")
monitor("motest", True, "msg_103", "ula ma kota", "None")

monitor("qq", True, "msg_203", "wiadomosc 1", "None")
monitor("qq", True, "msg_202", "wiadomosc 2", "video")

def get_last_message_text(rid):
    if rid not in g_unread_subscription_list or not g_unread_subscription_list[rid]:
        return None
    last_message = g_unread_subscription_list[rid][-1]
    last_msg_content = next(iter(last_message.values()))
    if last_msg_content.get("qualifier") == "videoconf":
        txt = "Incoming phone call"
    else:
        txt = last_msg_content.get("text")
    return txt
add_historical_message("qq")
add_historical_message("qq")
add_historical_message("qq")

print(g_unread_subscription_list)
remove_all_historical_messages("qq")
print(json.dumps(g_unread_subscription_list, indent=4))


#print(len( g_unread_subscription_list))
# print(get_last_message_text("motest"))


# monitor("qq", False, "msg_203","","")
# monitor("qq", False, "msg_203","","")
# monitor("qq", False, "msg_202","","")

# print(json.dumps(g_unread_subscription_list, indent=4))
# print(len( g_unread_subscription_list.get("motest")))
# print(len( g_unread_subscription_list))
 