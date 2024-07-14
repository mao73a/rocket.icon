import pystray
from PIL import Image
import winsound

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

    def set_notification_image(self, icon_name, prior=0):
        if not icon_name:
            return
        if self._current_priority > prior:
            self._current_priority = prior
            print(f"  set_notification_image {icon_name}")
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

#icon_manager = IconManager("Better Rocket Icon")
