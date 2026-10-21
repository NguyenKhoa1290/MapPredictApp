@echo off
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo Chua co moi truong Python. Chay: py -3.11 -m venv venv
    echo Sau do chay: venv\Scripts\python.exe -m pip install -r requirements.txt
    exit /b 1
)
"venv\Scripts\python.exe" app.py
