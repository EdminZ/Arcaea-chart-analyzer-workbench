@echo off
cd /d "%~dp0"
py -3 --version
py -3 -c "import tkinter, sqlite3, numpy, scipy; print('Tk available:', tkinter.TkVersion); print('SQLite available:', sqlite3.sqlite_version)"
py -3 -m unittest discover -s tests -q
pause
