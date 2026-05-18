# Sentinel Net — Endpoint Agent

Production-ready Python endpoint agent for Sentinel Net.

## Files
| File | Purpose |
|------|---------|
| `sentinel_agent.py` | Single-file consolidated agent: registration, heartbeat, policy sync, process/USB monitoring, domain blocking, screenshots, realtime commands, watchdog, autostart. |
| `sentinel_tray.py`  | System tray UI: status, recent alerts, dashboard launcher, uninstall request. |
| `installer.py`      | Installs deps, copies binaries, registers autostart, launches watchdog. |
| `build_exe.bat`     | Builds `.exe` artifacts on Windows via PyInstaller. |
| `requirements.txt`  | Runtime dependencies. |

## Run modes
```bash
python sentinel_agent.py                  # main agent loop
python sentinel_agent.py --watchdog       # supervisor (auto-restarts agent + tray)
python sentinel_agent.py --tray           # system tray only
python sentinel_agent.py --install        # register autostart
python sentinel_agent.py --uninstall      # request admin-approved uninstall
python sentinel_agent.py --login user@x.com password
```

## Install
```bash
python installer.py             # install + start watchdog
python installer.py --uninstall # remove autostart & data
```

## Build Windows executable
```cmd
build_exe.bat
```
Produces `dist\SentinelAgent.exe`, `dist\SentinelTray.exe`, `dist\SentinelInstaller.exe`.

## Violation popups
Native modal/notification popups fire automatically on:
- Blocked process termination
- USB insertion (warning or hard block per policy)
- Admin-issued lock / shutdown / kill commands
- Uninstall status

## Exit codes
- `0`  clean shutdown
- `75` restart requested — watchdog will relaunch

## Data locations
- Windows: `C:\ProgramData\SentinelNet\`
- macOS:   `/Library/Application Support/SentinelNet/`
- Linux:   `/etc/sentinelnet/`
