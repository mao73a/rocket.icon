import pystray
from PIL import Image
import winsound
import threading
import time

class IconManager:
    def __init__(self,  title):
        self.icon = pystray.Icon("basic")
        self.title = title
        self._current_priority = float('inf') 
        self.set_basic_image() 

    def set_basic_image(self):
        #print(f"  set_basic_image")        
        self.icon.icon = Image.open("icons/bubble2.png")

    def set_error_image(self):
        self.icon.icon = Image.open("icons/bubble2error.png")
    
    def set_reload_image(self):
        self.icon.icon = Image.open("icons/bubble2reload.png")

    def reset_priority(self):
        self._current_priority = float('inf') 

    def set_notification_image(self, icon_name, prior=0, blink=False):
        if not icon_name:
            return
        if self._current_priority > prior:
            self._current_priority = prior
            print(f"  set_notification_image {icon_name}")
            if blink:
                self._start_blinking(icon_name)
            else:
                self.icon.icon = Image.open(f"icons/{icon_name}")

    def set_delay_image(self):
        self.icon.icon = Image.open("icons/bubble2delay.png")

    def set_launch_image(self):
        self.icon.icon = Image.open("icons/bubble2launch.png")        

    def set_icon_title(self, title):
        if len(title) > 128:
            title = title[:128]
        self.icon.title = title

    def notify(self, message, title):
        self.icon.notify(message, title)


    def play_sound(self, sound_name):
        print(f"  play_sound {sound_name}")
        winsound.PlaySound(f"sounds/{sound_name}", winsound.SND_FILENAME | winsound.SND_ASYNC)

    def _start_blinking(self, icon_name):
        self._stop_blinking()
        self._blink_thread = threading.Thread(target=self._blink_icon, args=(icon_name,))
        self._blink_thread.start()

    def _stop_blinking(self):
        if hasattr(self, '_blink_thread') and self._blink_thread.is_alive():
            self._blink_stop = True
            self._blink_thread.join()

    def _blink_icon(self, icon_name):
        self._blink_stop = False
        while not self._blink_stop:
            self.icon.icon = Image.open(f"icons/{icon_name}")
            time.sleep(1)
            if self._blink_stop:
                break
            self.icon.icon = Image.open("icons/bubble2.png")
            time.sleep(1)

#icon_manager = IconManager("Better Rocket Icon")
