del dist\rocketicon.exe 
xcopy icons dist\icons\ /s /y
xcopy sounds dist\sounds\ /s /y
copy rc_search.html dist\rc_search.html /y
pipenv run pyinstaller --hide-console hide-early -F --icon="favicon.ico"  app.py
rename dist\app.exe rocketicon.exe