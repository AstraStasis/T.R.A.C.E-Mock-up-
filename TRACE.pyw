import os
from pathlib import Path
import subprocess
import sys
import ctypes

# Start the dedicated desktop application using the workspace environment.
root=Path(__file__).resolve().parent
url='http://127.0.0.1:8000'
python=root/'.venv/Scripts/pythonw.exe'
python_console=root/'.venv/Scripts/python.exe'


def ensure_environment():
    if python.exists() and python_console.exists():
        probe = subprocess.run(
            [str(python_console), '-c', 'import fastapi, uvicorn, webview'],
            cwd=root,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if probe.returncode == 0:
            return True
    answer = ctypes.windll.user32.MessageBoxW(
        0,
        'TRACE needs to install its local Python environment and dependencies. Continue?',
        'TRACE first-time setup',
        0x04 | 0x20,
    )
    if answer != 6:
        return False
    setup = root / 'setup.ps1'
    result = subprocess.run(
        ['powershell.exe', '-ExecutionPolicy', 'Bypass', '-File', str(setup), '-NoStart'],
        cwd=root,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0 or not python.exists():
        ctypes.windll.user32.MessageBoxW(
            0,
            'TRACE setup failed. Run setup.ps1 from PowerShell to view the installation error.',
            'TRACE setup error',
            0x10,
        )
        return False
    return True


if not ensure_environment():
    sys.exit(1)

desktop_python = root / '.venv/Scripts/pythonw.exe'
subprocess.Popen([str(desktop_python), str(root / 'desktop.py')], cwd=root, creationflags=subprocess.CREATE_NO_WINDOW)
