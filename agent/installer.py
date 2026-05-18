"""
Sentinel Net - Installer
========================
Installs dependencies, places the agent files into the system data dir,
registers autostart via OS-native mechanism, and launches the watchdog.

Usage:
    python installer.py            # install
    python installer.py --uninstall # remove autostart + data
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "SentinelNet"
IS_WIN = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"

if IS_WIN:
    INSTALL_DIR = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / APP_NAME / "bin"
elif IS_MAC:
    INSTALL_DIR = Path("/Library/Application Support") / APP_NAME / "bin"
else:
    INSTALL_DIR = Path("/opt") / APP_NAME.lower() / "bin"

REQUIREMENTS = [
    "httpx>=0.27",
    "psutil>=5.9",
    "pystray>=0.19",
    "Pillow>=10.0",
    "plyer>=2.1",
    "websocket-client>=1.7",
]


def info(msg: str) -> None:
    print(f"[installer] {msg}", flush=True)


def pip_install() -> None:
    info("installing Python dependencies…")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir", *REQUIREMENTS]
    )


def copy_agent_files() -> Path:
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    here = Path(__file__).resolve().parent
    for name in ("sentinel_agent.py", "sentinel_tray.py"):
        src = here / name
        if src.exists():
            shutil.copy2(src, INSTALL_DIR / name)
            info(f"copied {name} -> {INSTALL_DIR}")
    return INSTALL_DIR / "sentinel_agent.py"


def install_autostart(agent_path: Path) -> None:
    exe = sys.executable
    if IS_WIN:
        import winreg  # type: ignore
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe}" "{agent_path}" --watchdog')
        winreg.CloseKey(key)
        info("registered HKCU\\…\\Run\\SentinelNet")
    elif IS_MAC:
        plist = Path.home() / "Library/LaunchAgents/com.sentinelnet.agent.plist"
        plist.parent.mkdir(parents=True, exist_ok=True)
        plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.sentinelnet.agent</string>
  <key>ProgramArguments</key><array>
    <string>{exe}</string><string>{agent_path}</string><string>--watchdog</string>
  </array>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
</dict></plist>""")
        subprocess.run(["launchctl", "load", str(plist)], check=False)
        info(f"installed LaunchAgent {plist}")
    else:
        unit = Path.home() / ".config/systemd/user/sentinelnet.service"
        unit.parent.mkdir(parents=True, exist_ok=True)
        unit.write_text(f"""[Unit]
Description=Sentinel Net Agent
After=network-online.target
[Service]
ExecStart={exe} {agent_path} --watchdog
Restart=always
RestartSec=5
[Install]
WantedBy=default.target
""")
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        subprocess.run(["systemctl", "--user", "enable", "--now", "sentinelnet.service"], check=False)
        info(f"installed systemd unit {unit}")


def uninstall() -> None:
    info("removing autostart…")
    if IS_WIN:
        try:
            import winreg  # type: ignore
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            )
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
        except Exception as exc:
            info(f"registry cleanup failed: {exc}")
    elif IS_MAC:
        plist = Path.home() / "Library/LaunchAgents/com.sentinelnet.agent.plist"
        if plist.exists():
            subprocess.run(["launchctl", "unload", str(plist)], check=False)
            plist.unlink()
    else:
        subprocess.run(["systemctl", "--user", "disable", "--now", "sentinelnet.service"], check=False)

    if INSTALL_DIR.exists():
        shutil.rmtree(INSTALL_DIR, ignore_errors=True)
        info(f"removed {INSTALL_DIR}")
    info("uninstall complete")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--no-autostart", action="store_true")
    parser.add_argument("--no-deps", action="store_true")
    args = parser.parse_args()

    if args.uninstall:
        uninstall()
        return 0

    info(f"installing {APP_NAME} on {platform.platform()}")
    if not args.no_deps:
        pip_install()
    agent_path = copy_agent_files()
    if not args.no_autostart:
        install_autostart(agent_path)
    info("starting watchdog…")
    subprocess.Popen([sys.executable, str(agent_path), "--watchdog"])
    info("✓ installation finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
