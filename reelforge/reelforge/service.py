"""Installs the daemon as a real background service so it survives logout and reboot.

Detects the OS and uses whatever that platform actually uses: systemd on Linux,
launchd on macOS, Task Scheduler on Windows.
"""
import os
import platform
import subprocess
import sys
from pathlib import Path

from .config import ROOT

NAME = "reelforge"
LABEL = "com.reelforge.daemon"


def _python():
    return sys.executable or "python3"


def _system():
    return platform.system()


# ---------------------------------------------------------------- linux

def _systemd_path():
    return Path.home() / ".config" / "systemd" / "user" / f"{NAME}.service"


def _systemd_unit():
    return f"""[Unit]
Description=ReelForge — Instagram carousel daemon
After=network-online.target

[Service]
Type=simple
WorkingDirectory={ROOT}
ExecStart={_python()} -m reelforge daemon
Restart=always
RestartSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
"""


def _linux_install():
    path = _systemd_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_systemd_unit(), encoding="utf-8")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "--user", "enable", "--now", NAME], check=False)
    # Without lingering, the service stops when you log out.
    subprocess.run(["loginctl", "enable-linger", os.environ.get("USER", "")], check=False)
    return (
        f"installed systemd user service at {path}\n"
        f"  logs:  journalctl --user -u {NAME} -f\n"
        f"  stop:  systemctl --user stop {NAME}"
    )


def _linux_uninstall():
    subprocess.run(["systemctl", "--user", "disable", "--now", NAME], check=False)
    _systemd_path().unlink(missing_ok=True)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    return "systemd service removed"


def _linux_status():
    result = subprocess.run(
        ["systemctl", "--user", "is-active", NAME], capture_output=True, text=True
    )
    state = result.stdout.strip()
    if state == "active":
        return True, f"systemd service '{NAME}' is running"
    if _systemd_path().exists():
        return False, f"systemd service installed but {state or 'not running'}"
    return False, "not installed"


# ---------------------------------------------------------------- macos

def _plist_path():
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _plist():
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{_python()}</string><string>-m</string><string>reelforge</string><string>daemon</string>
  </array>
  <key>WorkingDirectory</key><string>{ROOT}</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>{ROOT}/reelforge.log</string>
  <key>StandardErrorPath</key><string>{ROOT}/reelforge.log</string>
</dict>
</plist>
"""


def _macos_install():
    path = _plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_plist(), encoding="utf-8")
    subprocess.run(["launchctl", "unload", str(path)], check=False,
                   capture_output=True)
    subprocess.run(["launchctl", "load", "-w", str(path)], check=False)
    return (
        f"installed LaunchAgent at {path}\n"
        f"  logs:  tail -f {ROOT}/reelforge.log\n"
        f"  stop:  launchctl unload {path}"
    )


def _macos_uninstall():
    path = _plist_path()
    subprocess.run(["launchctl", "unload", str(path)], check=False, capture_output=True)
    path.unlink(missing_ok=True)
    return "LaunchAgent removed"


def _macos_status():
    result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    if LABEL in result.stdout:
        return True, f"LaunchAgent '{LABEL}' is loaded"
    if _plist_path().exists():
        return False, "LaunchAgent installed but not loaded"
    return False, "not installed"


# ---------------------------------------------------------------- windows

def _windows_install():
    command = f'"{_python()}" -m reelforge daemon'
    subprocess.run(
        ["schtasks", "/Create", "/F", "/SC", "ONLOGON", "/TN", NAME,
         "/TR", command, "/RL", "LIMITED"],
        check=False,
    )
    subprocess.run(["schtasks", "/Run", "/TN", NAME], check=False)
    return (
        f"created scheduled task '{NAME}' (runs at logon)\n"
        f"  stop:  schtasks /End /TN {NAME}\n"
        f"  note:  run this from the reelforge folder, it is the task's working directory"
    )


def _windows_uninstall():
    subprocess.run(["schtasks", "/Delete", "/F", "/TN", NAME], check=False)
    return "scheduled task removed"


def _windows_status():
    result = subprocess.run(["schtasks", "/Query", "/TN", NAME],
                            capture_output=True, text=True)
    if result.returncode == 0:
        running = "Running" in result.stdout
        return running, f"scheduled task '{NAME}' exists ({'running' if running else 'idle'})"
    return False, "not installed"


# ---------------------------------------------------------------- dispatch

HANDLERS = {
    "Linux": (_linux_install, _linux_uninstall, _linux_status),
    "Darwin": (_macos_install, _macos_uninstall, _macos_status),
    "Windows": (_windows_install, _windows_uninstall, _windows_status),
}


def _handlers():
    system = _system()
    if system not in HANDLERS:
        raise SystemExit(f"No service support for {system}. Run 'python -m reelforge daemon' by hand.")
    return HANDLERS[system]


def install():
    return _handlers()[0]()


def uninstall():
    return _handlers()[1]()


def status():
    try:
        return _handlers()[2]()
    except Exception as exc:
        return False, f"could not check: {exc}"
