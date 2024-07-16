# Rocket Icon

I use the Rocket.Chat app at work, and sometimes I find it very overwhelming when too many people send too many messages too often. I think the original Rocket.Chat application lacks the ability to filter and delay some notifications and to let users distinguish between less and more important messages.

This software is created to address some of these issues. Rocket.Icon creates an alternative Windows tray icon. It enables you to have:
- Different icons and sound notifications for different channels.
- Customized delay periods for notifications. For example, you can define a lower notification frequency for some public broadcast channels.
- The ability to mute notifications for a specified amount of time, allowing you to focus on important work.
- The ability to inform you about overlooked messages after a specified amount of time (escalation).
- Tray icon can blink
- Search messages through the web page interface

![image](https://github.com/user-attachments/assets/f7570cf8-1b7c-4e88-9c71-0451b421c9c2)

# Installation

```sh
pip install -r requirements.txt
python RocketIcon.py
```

or

just [download](https://github.com/mao73a/rocket.icon/releases) precompiled windows executable:

# Setup

After the first run, two default files:
- `rules.json`
- `config.json`

will be copied from the program directory to your `.rocketicon` local user directory. Do not attempt to edit the JSON files in the program directory as it will have no effect! Click on the tray icon's Settings or Rules menu instead. After clicking the Settings menu, you can edit:
- Your Rocket.Chat server address.
- Your user ID and user token. **IMPORTANT**: These are not the same as your username and password! Go to your user account to generate your user ID and user token.


# Rules

Click on the tray menu Rules and see the preconfigured rules. You can add your own rules to customize the notification behavior. See the documentation inside `rules.json` to learn more about defining rules.
