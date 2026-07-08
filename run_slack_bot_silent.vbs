Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd.exe /c cd /d c:\Users\hp\Downloads\automation\daily-instagram-posts-pipeline && set PYTHONIOENCODING=utf-8 && python slack_on_demand_bot.py", 0, false
