import asyncio
import random
from rocketchat_async import RocketChat
from concurrent.futures import ThreadPoolExecutor

def handle_message(channel_id, sender_id, msg_id, thread_id, msg, qualifier, unread, repeated):
    """Simply print the message that arrived."""
    print(msg)

async def main(address, username, token, stop_event):
    while not stop_event.is_set():
        try:
            rc = RocketChat()
            #await rc.start(address, username, password)
            # Alternatively, use rc.resume for token-based authentication:
            await rc.resume(address, username, token)
            
            # A possible workflow consists of two steps:
            #
            # 1. Set up the desired callbacks...
            for channel_id, channel_type in await rc.get_channels():
                await rc.subscribe_to_channel_messages(channel_id, handle_message)
            # 2. ...and then simply wait for the registered events.
            await rc.run_forever()
        except (RocketChat.ConnectionClosed, RocketChat.ConnectCallFailed) as e:
            if not stop_event.is_set():  # Only reconnect if we're not shutting down
                print(f'Connection failed: {e}. Waiting a few seconds...')
                await asyncio.sleep(random.uniform(4, 8))
                print('Reconnecting...')
            else:
                break

    await rc.stop()  # Ensure that we stop the connection

def run_main_in_thread(address, username, password, stop_event):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main(address, username, password, stop_event))

if __name__ == "__main__":
    # Define your server address, username, and password
    address = 'wss://chat.czk.comarch.com/websocket'
    username = 'Yme82NmFkeZu5s9kh'
    password = 'Se9BYjNkhJRbDzvrQpCJaBN6olOUJFaqw2nE9X_o49U'

    # Create a stop event
    stop_event = asyncio.Event()

    # Create a new ThreadPoolExecutor with one thread
    executor = ThreadPoolExecutor(max_workers=1)
    
    # Submit the `run_main_in_thread` to the executor to run on a separate thread
    future = executor.submit(run_main_in_thread, address, username, password, stop_event)

    try:
        while True:
            # Main thread can do other stuff
            asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Stopping the application...")
        stop_event.set()
        # Wait for the thread to finish
        future.result()  
        print("Application has stopped.")