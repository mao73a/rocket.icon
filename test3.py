g_unread_subscription_list = {}
#{'motest': ['msg_101', 'msg_102', 'msg_103'], 'qq': ['msg_202', 'msg_203']}


def monitor(channel_id, unread, msg_id):

    if not g_unread_subscription_list.get(channel_id):
        if not unread:
            return
        else:
            g_unread_subscription_list[channel_id] = []
    if unread:
        g_unread_subscription_list[channel_id].append(msg_id)
        print("   -- handle_message1 dodano ")
    elif msg_id in g_unread_subscription_list[channel_id]:
        g_unread_subscription_list[channel_id].remove(msg_id)
        if len(g_unread_subscription_list[channel_id])==0:
            del g_unread_subscription_list[channel_id]
        print("   -- handle_message1 usunieto ")

monitor("motest", True, "msg_101")
monitor("motest", True, "msg_102")
monitor("motest", True, "msg_103")

monitor("qq", True, "msg_202")
monitor("qq", True, "msg_203")

print(g_unread_subscription_list)
print(len( g_unread_subscription_list.get("motest")))
print(len( g_unread_subscription_list))
monitor("qq", False, "msg_203")
monitor("qq", False, "msg_202")

print(g_unread_subscription_list)
print(len( g_unread_subscription_list.get("motest")))
print(len( g_unread_subscription_list))