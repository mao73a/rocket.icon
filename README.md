# Rocket Icon
- I use Rocket.Chat app at work and sometimes I find it very disturbing when too many people wants to say too many things too often. I think this application lacks possibility to delay some notifications and to let user distinguish before less and more important messages.
- This software is created to address some of these issues. Te Rocket Icon creates alternarive Windows tray icon. It enables you to have:
	- different icons and sounds notifications for differnt channels
	- customized delay periods for notifications - you can for example define notification frequency to be lower for some public boradcast channel
	- ability to mute notifications for specified amount of time, if you need to focus on some important work
	- ability to inform about unread messages after some specified amount of time (escalation)
	
# Installation
pip install -r requirements.txt
python RocketIcon.py

# Setup
After first run default files:
	- rules.json
	- config.json 
will be copied from program directory to your .rocketicon local user directory. Do not attempt to edit json files in program direcory as it will have no effect! Click on tray icon Settings or Rules menu instead. After clickng Settings menu you can edit:
	- your user id and user token. IMPORTANT: These are not the same as user name and user password! - go to your user account to generate user id and user token
	- enter your RocketChat server address

# Rules
Click on tray meny Rules and see precofigured rules. You can add your own rules to customize notifications behaviour. See documentation inside rules.json to find out more about defining rules.


