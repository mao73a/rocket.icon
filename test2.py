g_unread_subscription_list = {}
if not g_unread_subscription_list.get('abc'):
    g_unread_subscription_list['abc'] = []
g_unread_subscription_list['abc'].append('m1')
g_unread_subscription_list['abc'].append('m2')
g_unread_subscription_list['abc'].append('m3')

if 'm2' in g_unread_subscription_list['abc']:
    g_unread_subscription_list['abc'].remove('m2')

for message in g_unread_subscription_list['abc']:
    print(message)