from pathlib import Path
import subprocess
import sys
import ctypes

# Start the dedicated desktop application using the workspace environment.
root=Path(__file__).resolve().parent
python=root/'.venv/Scripts/pythonw.exe'
python_console=root/'.venv/Scripts/python.exe'


def ensure_environment():
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


def launch():
    return subprocess.run([str(python), str(root / 'desktop.py')], cwd=root,
                          creationflags=subprocess.CREATE_NO_WINDOW).returncode


if python.exists() and python_console.exists():
    result = launch()
    if result != 72:  # Desktop reserves 72 for missing dependencies.
        sys.exit(result)
if ensure_environment():
    result = launch()
    if result == 72:
        ctypes.windll.user32.MessageBoxW(0, 'Dependency installation is incomplete. Run setup.ps1.', 'TRACE setup', 0x10)
    sys.exit(result)
sys.exit(1)
