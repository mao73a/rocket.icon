import json
g_unread_subscription_list = {}
#{'motest': ['msg_101', 'msg_102', 'msg_103'], 'qq': ['msg_202', 'msg_203']}
#{'motest':['msg_101':{"text":"abc"}, 'msg_102':{"text":"efg"} ]}

def remove_message(channel_id, msg_id):
 
    for msg_dict in g_unread_subscription_list[channel_id]:
        if msg_id in msg_dict:
            g_unread_subscription_list[channel_id].remove(msg_dict)
            break  # Exit loop after removing the message

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
monitor("motest", True, "msg_102", "Ela ma kota", "None")
monitor("motest", True, "msg_103", "ula ma kota", "None")

monitor("qq", True, "msg_203", "wiadomosc 1", "None")
monitor("qq", True, "msg_202", "wiadomosc 2", "video")

print(g_unread_subscription_list)
print(json.dumps(g_unread_subscription_list, indent=4))
print(len( g_unread_subscription_list.get("motest")))
print(len( g_unread_subscription_list))
# monitor("qq", False, "msg_203","","")
# monitor("qq", False, "msg_203","","")
# monitor("qq", False, "msg_202","","")

# print(json.dumps(g_unread_subscription_list, indent=4))
# print(len( g_unread_subscription_list.get("motest")))
# print(len( g_unread_subscription_list))

for x in g_unread_subscription_list:
    print(x)