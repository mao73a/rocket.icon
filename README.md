# Rocket Icon

I use the Rocket.Chat app at work, and sometimes I find it very overwhelming when too many people send too many messages too often. I think the original Rocket.Chat application lacks the ability to filter and delay some notifications and to let users distinguish between less and more important messages.

This software is created to address some of these issues. Rocket.Icon creates an alternative Windows tray icon. It enables you to have:
- Different icons and sound notifications for different channels.
- Customized delay periods for notifications. For example, you can define a lower notification frequency for some public broadcast channels.
- The ability to mute notifications for a specified amount of time, allowing you to focus on important work.
- The ability to inform you about overlooked messages after a specified amount of time (escalation).

![image](https://github.com/user-attachments/assets/9b790f26-8f4e-4ce3-8402-8686326036ea)
# Installation

```sh
pip install -r requirements.txt
python RocketIcon.py
```

or

download precompiled windows executable:
[win-1.0.0](https://github.com/mao73a/rocket.icon/releases/download/win-1.0.0/rocketicon-win32-v1.0.0.zip)

# Setup

After the first run, two default files:
- `rules.json`
- `config.json`

will be copied from the program directory to your `.rocketicon` local user directory. Do not attempt to edit the JSON files in the program directory as it will have no effect! Click on the tray icon's Settings or Rules menu instead. After clicking the Settings menu, you can edit:
- Your Rocket.Chat server address.
- Your user ID and user token. **IMPORTANT**: These are not the same as your username and password! Go to your user account to generate your user ID and user token.


# Rules

Click on the tray menu Rules and see the preconfigured rules. You can add your own rules to customize the notification behavior. See the documentation inside `rules.json` to learn more about defining rules.
