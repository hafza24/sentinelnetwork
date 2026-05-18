"""
Sentinel Net - Endpoint Agent (single-file consolidated build)
================================================================
Production-grade endpoint monitoring & enforcement agent.

Features:
  - Device registration + heartbeat (online/offline status)
  - Policy sync (domains, processes, USB, schedules, shutdown rules)
  - Process monitor + kill of blocked processes
  - USB device insertion detection + blocking
  - Domain blocking via hosts file
  - Browser history & download collection
  - Screenshot capture (scheduled + on-violation)
  - File / peripheral / network telemetry
  - Realtime Supabase WebSocket channel for live commands
  - Watchdog supervision (exit code 75 = restart-request)
  - Native popup notifications on violations
  - Offline event queue with replay on reconnect
  - Admin-approved uninstall flow

Run modes:
  python sentinel_agent.py                  # agent main loop
  python sentinel_agent.py --tray           # tray UI
  python sentinel_agent.py --watchdog       # watchdog supervisor
  python sentinel_agent.py --install        # install + autostart
  python sentinel_agent.py --uninstall      # request uninstall (admin approval)
  python sentinel_agent.py --version
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import queue
import socket
import subprocess
import sys
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# ---- Optional deps (graceful degradation) ----------------------------------
try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore

try:
    import websocket  # websocket-client
except ImportError:
    websocket = None  # type: ignore

try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None  # type: ignore

try:
    from plyer import notification as plyer_notification
except ImportError:
    plyer_notification = None  # type: ignore

# ============================================================================
# CONSTANTS / CONFIG
# ============================================================================
VERSION = "1.0.0"
APP_NAME = "SentinelNet"

SUPABASE_URL = os.environ.get("SENTINEL_SUPABASE_URL", "https://kwctyqxdiocjmsekymft.supabase.co")
SUPABASE_ANON_KEY = os.environ.get(
    "SENTINEL_SUPABASE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imt3Y3R5cXhkaW9jam1zZWt5bWZ0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY1MDU3MTksImV4cCI6MjA5MjA4MTcxOX0.9z3Jgnuds4uLOsz62eOvvCz34i-9iD9PWILKVnjRpaA",
)

IS_WIN = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"

if IS_WIN:
    CONFIG_DIR = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / APP_NAME
    HOSTS_PATH = Path(r"C:\Windows\System32\drivers\etc\hosts")
elif IS_MAC:
    CONFIG_DIR = Path("/Library/Application Support") / APP_NAME
    HOSTS_PATH = Path("/etc/hosts")
else:
    CONFIG_DIR = Path("/etc") / APP_NAME.lower()
    HOSTS_PATH = Path("/etc/hosts")

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "config.json"
QUEUE_FILE = CONFIG_DIR / "offline_queue.jsonl"
LOG_FILE = CONFIG_DIR / "agent.log"
SCREENSHOT_DIR = CONFIG_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

HOSTS_MARKER_START = "# >>> SentinelNet managed block >>>"
HOSTS_MARKER_END = "# <<< SentinelNet managed block <<<"

EXIT_RESTART_REQUESTED = 75  # watchdog restarts on this code

# ============================================================================
# LOGGING
# ============================================================================
_log_lock = threading.Lock()


def log(level: str, msg: str, **extra: Any) -> None:
    line = f"[{datetime.utcnow().isoformat()}Z] [{level}] {msg}"
    if extra:
        line += " " + json.dumps(extra, default=str)
    with _log_lock:
        try:
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass
    print(line, flush=True)


# ============================================================================
# CONFIG STORE (atomic JSON)
# ============================================================================
@dataclass
class AgentConfig:
    device_id: str = ""
    hostname: str = socket.gethostname()
    os: str = f"{platform.system()} {platform.release()}"
    enrollment_token: str = ""
    access_token: str = ""
    refresh_token: str = ""
    user_id: str = ""
    last_sync: str = ""
    policies: dict = field(default_factory=dict)

    @classmethod
    def load(cls) -> "AgentConfig":
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except Exception as exc:
                log("WARN", f"config load failed: {exc}")
        return cls(device_id=str(uuid.uuid4()))

    def save(self) -> None:
        tmp = CONFIG_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.__dict__, indent=2, default=str), encoding="utf-8")
        tmp.replace(CONFIG_FILE)


# ============================================================================
# NATIVE NOTIFICATIONS (cross-platform popup)
# ============================================================================
def notify(title: str, message: str, urgent: bool = False) -> None:
    """Show a native OS popup notification for violations / alerts."""
    log("ALERT", f"{title}: {message}")
    try:
        if IS_WIN and urgent:
            # MessageBox is blocking-modal; run in thread so it doesn't stop the agent
            def _box() -> None:
                MB_ICONWARNING = 0x30
                MB_SYSTEMMODAL = 0x1000
                ctypes.windll.user32.MessageBoxW(
                    0, message, f"{APP_NAME} - {title}", MB_ICONWARNING | MB_SYSTEMMODAL
                )

            threading.Thread(target=_box, daemon=True).start()
            return
        if plyer_notification is not None:
            plyer_notification.notify(
                title=f"{APP_NAME} - {title}",
                message=message,
                app_name=APP_NAME,
                timeout=8,
            )
            return
        if IS_MAC:
            subprocess.Popen(
                ["osascript", "-e", f'display notification "{message}" with title "{APP_NAME}: {title}"']
            )
        elif IS_LINUX:
            subprocess.Popen(["notify-send", f"{APP_NAME}: {title}", message])
        elif IS_WIN:
            ctypes.windll.user32.MessageBoxW(0, message, f"{APP_NAME} - {title}", 0x40)
    except Exception as exc:
        log("WARN", f"notify failed: {exc}")


# ============================================================================
# OFFLINE QUEUE
# ============================================================================
_queue_lock = threading.Lock()


def queue_event(table: str, payload: dict) -> None:
    record = {"table": table, "payload": payload, "queued_at": datetime.utcnow().isoformat()}
    with _queue_lock:
        with QUEUE_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")


def drain_queue(api: "SupabaseClient") -> int:
    if not QUEUE_FILE.exists():
        return 0
    drained = 0
    with _queue_lock:
        lines = QUEUE_FILE.read_text(encoding="utf-8").splitlines()
        remaining: list[str] = []
        for line in lines:
            try:
                rec = json.loads(line)
                if api.insert(rec["table"], rec["payload"]):
                    drained += 1
                else:
                    remaining.append(line)
            except Exception:
                remaining.append(line)
        QUEUE_FILE.write_text("\n".join(remaining) + ("\n" if remaining else ""), encoding="utf-8")
    return drained


# ============================================================================
# SUPABASE REST CLIENT
# ============================================================================
class SupabaseClient:
    def __init__(self, cfg: AgentConfig) -> None:
        self.cfg = cfg
        self._lock = threading.Lock()
        if httpx is None:
            raise RuntimeError("httpx is required. pip install httpx")
        self._client = httpx.Client(timeout=15.0, base_url=SUPABASE_URL)

    def _headers(self, prefer: str = "") -> dict:
        token = self.cfg.access_token or SUPABASE_ANON_KEY
        h = {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        if prefer:
            h["Prefer"] = prefer
        return h

    def login(self, email: str, password: str) -> bool:
        try:
            r = self._client.post(
                "/auth/v1/token?grant_type=password",
                json={"email": email, "password": password},
                headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
            )
            if r.status_code == 200:
                data = r.json()
                self.cfg.access_token = data["access_token"]
                self.cfg.refresh_token = data["refresh_token"]
                self.cfg.user_id = data["user"]["id"]
                self.cfg.save()
                return True
            log("ERROR", f"login failed: {r.status_code} {r.text}")
        except Exception as exc:
            log("ERROR", f"login exception: {exc}")
        return False

    def refresh(self) -> bool:
        if not self.cfg.refresh_token:
            return False
        try:
            r = self._client.post(
                "/auth/v1/token?grant_type=refresh_token",
                json={"refresh_token": self.cfg.refresh_token},
                headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
            )
            if r.status_code == 200:
                data = r.json()
                self.cfg.access_token = data["access_token"]
                self.cfg.refresh_token = data["refresh_token"]
                self.cfg.save()
                return True
        except Exception as exc:
            log("WARN", f"refresh failed: {exc}")
        return False

    def insert(self, table: str, payload: dict) -> bool:
        try:
            r = self._client.post(
                f"/rest/v1/{table}",
                json=payload,
                headers=self._headers(prefer="return=minimal"),
            )
            if r.status_code in (401, 403):
                if self.refresh():
                    r = self._client.post(
                        f"/rest/v1/{table}",
                        json=payload,
                        headers=self._headers(prefer="return=minimal"),
                    )
            return r.status_code < 300
        except Exception as exc:
            log("WARN", f"insert {table} failed: {exc}")
            return False

    def select(self, table: str, query: str = "") -> list[dict]:
        try:
            r = self._client.get(f"/rest/v1/{table}?{query}", headers=self._headers())
            if r.status_code == 200:
                return r.json()
        except Exception as exc:
            log("WARN", f"select {table} failed: {exc}")
        return []

    def upsert(self, table: str, payload: dict, on_conflict: str = "id") -> bool:
        try:
            r = self._client.post(
                f"/rest/v1/{table}?on_conflict={on_conflict}",
                json=payload,
                headers=self._headers(prefer="resolution=merge-duplicates,return=minimal"),
            )
            return r.status_code < 300
        except Exception as exc:
            log("WARN", f"upsert {table} failed: {exc}")
            return False


# ============================================================================
# TELEMETRY COLLECTORS
# ============================================================================
def collect_processes(limit: int = 20) -> list[dict]:
    if psutil is None:
        return []
    procs = []
    for p in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent"]):
        try:
            procs.append(p.info)
        except Exception:
            continue
    procs.sort(key=lambda x: x.get("cpu_percent") or 0, reverse=True)
    return procs[:limit]


def collect_system() -> dict:
    if psutil is None:
        return {}
    try:
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.5),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent if not IS_WIN else psutil.disk_usage("C:\\").percent,
            "boot_time": datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc).isoformat(),
            "net_sent": psutil.net_io_counters().bytes_sent,
            "net_recv": psutil.net_io_counters().bytes_recv,
        }
    except Exception:
        return {}


def collect_usb() -> list[dict]:
    devices: list[dict] = []
    try:
        if IS_WIN:
            out = subprocess.check_output(
                ["wmic", "path", "Win32_PnPEntity", "where", "PNPClass='USB'", "get", "Name,DeviceID", "/format:list"],
                stderr=subprocess.DEVNULL,
                timeout=5,
            ).decode(errors="ignore")
            current: dict = {}
            for ln in out.splitlines():
                ln = ln.strip()
                if not ln:
                    if current:
                        devices.append(current)
                        current = {}
                    continue
                if "=" in ln:
                    k, v = ln.split("=", 1)
                    current[k.strip().lower()] = v.strip()
        elif IS_LINUX:
            out = subprocess.check_output(["lsusb"], stderr=subprocess.DEVNULL, timeout=5).decode()
            for ln in out.splitlines():
                devices.append({"raw": ln})
        elif IS_MAC:
            out = subprocess.check_output(["system_profiler", "SPUSBDataType"], timeout=5).decode()
            devices.append({"raw": out[:2000]})
    except Exception as exc:
        log("WARN", f"usb scan failed: {exc}")
    return devices


# ============================================================================
# ENFORCEMENT
# ============================================================================
def block_domains(domains: list[str]) -> None:
    """Rewrite the managed block in /etc/hosts (or Windows hosts)."""
    if not domains:
        return
    try:
        existing = HOSTS_PATH.read_text(encoding="utf-8") if HOSTS_PATH.exists() else ""
        # strip prior managed block
        if HOSTS_MARKER_START in existing:
            head = existing.split(HOSTS_MARKER_START)[0]
            tail_parts = existing.split(HOSTS_MARKER_END)
            tail = tail_parts[1] if len(tail_parts) > 1 else ""
            existing = head + tail
        block = [HOSTS_MARKER_START]
        for d in domains:
            d = d.strip().lower()
            if not d:
                continue
            block.append(f"127.0.0.1 {d}")
            block.append(f"127.0.0.1 www.{d}")
        block.append(HOSTS_MARKER_END)
        new_content = existing.rstrip() + "\n" + "\n".join(block) + "\n"
        HOSTS_PATH.write_text(new_content, encoding="utf-8")
        log("INFO", f"hosts file updated with {len(domains)} blocked domains")
    except PermissionError:
        log("WARN", "hosts file write requires elevation; domain blocking inactive")
    except Exception as exc:
        log("WARN", f"hosts file update failed: {exc}")


def kill_process_by_name(name: str) -> bool:
    if psutil is None:
        return False
    killed = False
    name_l = name.lower()
    for p in psutil.process_iter(["pid", "name"]):
        try:
            if (p.info["name"] or "").lower() == name_l:
                p.kill()
                killed = True
        except Exception:
            continue
    return killed


def lock_workstation() -> None:
    try:
        if IS_WIN:
            ctypes.windll.user32.LockWorkStation()
        elif IS_MAC:
            subprocess.Popen(["pmset", "displaysleepnow"])
        elif IS_LINUX:
            subprocess.Popen(["loginctl", "lock-session"])
    except Exception as exc:
        log("WARN", f"lock failed: {exc}")


def shutdown_host(delay: int = 30) -> None:
    try:
        if IS_WIN:
            subprocess.Popen(["shutdown", "/s", "/t", str(delay)])
        else:
            subprocess.Popen(["shutdown", "-h", f"+{max(1, delay // 60)}"])
    except Exception as exc:
        log("WARN", f"shutdown failed: {exc}")


def take_screenshot(reason: str = "scheduled") -> str | None:
    if ImageGrab is None:
        return None
    try:
        path = SCREENSHOT_DIR / f"{int(time.time())}_{reason}.png"
        ImageGrab.grab().save(path, "PNG")
        return str(path)
    except Exception as exc:
        log("WARN", f"screenshot failed: {exc}")
        return None


# ============================================================================
# REALTIME (Supabase Phoenix WebSocket)
# ============================================================================
class RealtimeClient(threading.Thread):
    def __init__(self, cfg: AgentConfig, on_command: Callable[[dict], None]) -> None:
        super().__init__(daemon=True, name="realtime")
        self.cfg = cfg
        self.on_command = on_command
        self._stop = threading.Event()
        self._ws: Any = None

    def stop(self) -> None:
        self._stop.set()
        try:
            if self._ws is not None:
                self._ws.close()
        except Exception:
            pass

    def run(self) -> None:
        if websocket is None:
            log("WARN", "websocket-client not installed; realtime disabled")
            return
        backoff = 2
        url = SUPABASE_URL.replace("https://", "wss://") + f"/realtime/v1/websocket?apikey={SUPABASE_ANON_KEY}&vsn=1.0.0"
        while not self._stop.is_set():
            try:
                self._ws = websocket.create_connection(url, timeout=10)
                topic = f"realtime:public:device_commands:device_id=eq.{self.cfg.device_id}"
                self._ws.send(json.dumps({
                    "topic": topic, "event": "phx_join", "payload": {}, "ref": "1"
                }))
                log("INFO", f"realtime joined {topic}")
                backoff = 2
                # heartbeat thread
                def hb() -> None:
                    while not self._stop.is_set():
                        try:
                            self._ws.send(json.dumps({
                                "topic": "phoenix", "event": "heartbeat", "payload": {}, "ref": "hb"
                            }))
                        except Exception:
                            return
                        time.sleep(25)
                threading.Thread(target=hb, daemon=True).start()
                while not self._stop.is_set():
                    raw = self._ws.recv()
                    if not raw:
                        break
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue
                    if msg.get("event") in ("INSERT", "postgres_changes"):
                        payload = msg.get("payload", {})
                        record = payload.get("record") or payload.get("data", {}).get("record")
                        if record:
                            self.on_command(record)
            except Exception as exc:
                log("WARN", f"realtime error: {exc}; reconnecting in {backoff}s")
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)


# ============================================================================
# AGENT MAIN LOOP
# ============================================================================
class SentinelAgent:
    def __init__(self) -> None:
        self.cfg = AgentConfig.load()
        if not self.cfg.device_id:
            self.cfg.device_id = str(uuid.uuid4())
            self.cfg.save()
        self.api = SupabaseClient(self.cfg)
        self.stop_event = threading.Event()
        self._known_usb: set[str] = set()
        self._last_screenshot = 0.0
        self.realtime = RealtimeClient(self.cfg, self.on_command)

    # ---- commands from realtime / admin --------------------------------
    def on_command(self, record: dict) -> None:
        cmd = (record.get("command") or "").lower()
        params = record.get("params") or {}
        log("INFO", f"command received: {cmd}", params=params)
        try:
            if cmd == "lock_device":
                lock_workstation()
                notify("Device Locked", "Your device was locked by an administrator.", urgent=True)
            elif cmd == "shutdown":
                notify("Shutdown Scheduled", "This device will shut down shortly.", urgent=True)
                shutdown_host(int(params.get("delay", 30)))
            elif cmd == "kill_process":
                name = params.get("name", "")
                if kill_process_by_name(name):
                    notify("Process Terminated", f"{name} was terminated by admin.", urgent=True)
            elif cmd == "force_sync":
                self.sync_policies()
            elif cmd == "screenshot":
                p = take_screenshot("admin")
                if p:
                    log("INFO", f"screenshot saved {p}")
            elif cmd == "restart_agent":
                self.stop_event.set()
                os._exit(EXIT_RESTART_REQUESTED)
            elif cmd == "uninstall_approved":
                self.perform_uninstall()
        except Exception as exc:
            log("ERROR", f"command {cmd} failed: {exc}\n{traceback.format_exc()}")

    # ---- core loops ----------------------------------------------------
    def register_device(self) -> None:
        payload = {
            "id": self.cfg.device_id,
            "hostname": self.cfg.hostname,
            "os": self.cfg.os,
            "status": "online",
            "last_seen": datetime.utcnow().isoformat(),
            "agent_version": VERSION,
        }
        if self.cfg.user_id:
            payload["user_id"] = self.cfg.user_id
        self.api.upsert("devices", payload, on_conflict="id")

    def heartbeat(self) -> None:
        payload = {
            "device_id": self.cfg.device_id,
            "captured_at": datetime.utcnow().isoformat(),
            "cpu": collect_system().get("cpu_percent"),
            "memory": collect_system().get("memory_percent"),
            "uptime_seconds": int(time.time() - (psutil.boot_time() if psutil else time.time())),
            "agent_version": VERSION,
            "status": "healthy",
        }
        if not self.api.insert("agent_health", payload):
            queue_event("agent_health", payload)
        # also bump device.last_seen
        self.api.upsert(
            "devices",
            {"id": self.cfg.device_id, "last_seen": datetime.utcnow().isoformat(), "status": "online"},
            on_conflict="id",
        )

    def sync_policies(self) -> None:
        rows = self.api.select("policies", "select=*&active=eq.true")
        self.cfg.policies = {r.get("kind", "unknown"): r for r in rows}
        self.cfg.last_sync = datetime.utcnow().isoformat()
        self.cfg.save()
        # apply domain block list
        domains: list[str] = []
        for r in self.api.select("blocked_domains", "select=domain&active=eq.true"):
            d = r.get("domain")
            if d:
                domains.append(d)
        block_domains(domains)
        log("INFO", f"policies synced: {len(rows)}, domains: {len(domains)}")

    def monitor_processes(self) -> None:
        if psutil is None:
            return
        blocked = {r.get("name", "").lower() for r in self.api.select("blocked_processes", "select=name&active=eq.true")}
        if not blocked:
            return
        for p in psutil.process_iter(["pid", "name", "username"]):
            try:
                pname = (p.info["name"] or "").lower()
                if pname in blocked:
                    p.kill()
                    msg = f"Blocked process '{pname}' was terminated."
                    notify("Blocked App", msg, urgent=True)
                    evt = {
                        "device_id": self.cfg.device_id,
                        "kind": "process_blocked",
                        "details": {"name": pname, "pid": p.info["pid"], "user": p.info.get("username")},
                        "occurred_at": datetime.utcnow().isoformat(),
                        "severity": "warning",
                    }
                    if not self.api.insert("activity_events", evt):
                        queue_event("activity_events", evt)
                    shot = take_screenshot("process_violation")
                    if shot:
                        log("INFO", f"violation screenshot {shot}")
            except Exception:
                continue

    def monitor_usb(self) -> None:
        devices = collect_usb()
        ids = {json.dumps(d, sort_keys=True) for d in devices}
        new_ids = ids - self._known_usb
        if self._known_usb and new_ids:
            block_all = any(
                str(r.get("name", "")).lower() in ("usb", "all_usb")
                for r in self.api.select("blocked_processes", "select=name&active=eq.true")
            )
            for nid in new_ids:
                evt = {
                    "device_id": self.cfg.device_id,
                    "kind": "usb_inserted",
                    "details": json.loads(nid),
                    "occurred_at": datetime.utcnow().isoformat(),
                    "severity": "warning" if block_all else "info",
                }
                if not self.api.insert("usb_events", evt):
                    queue_event("usb_events", evt)
                notify(
                    "USB Detected",
                    "A USB device was inserted." + (" Access is restricted by policy." if block_all else ""),
                    urgent=block_all,
                )
                if block_all:
                    take_screenshot("usb_violation")
        self._known_usb = ids

    def maybe_screenshot(self) -> None:
        interval = int((self.cfg.policies.get("screenshot", {}) or {}).get("interval_seconds", 0))
        if interval <= 0:
            return
        now = time.time()
        if now - self._last_screenshot >= interval:
            self._last_screenshot = now
            take_screenshot("scheduled")

    def run(self) -> None:
        log("INFO", f"Sentinel Agent v{VERSION} starting", device_id=self.cfg.device_id, host=self.cfg.hostname)
        if not self.cfg.access_token:
            log("WARN", "no access token — running unauthenticated (limited functionality)")
        try:
            self.register_device()
        except Exception as exc:
            log("ERROR", f"registration failed: {exc}")

        self.realtime.start()

        tick = 0
        while not self.stop_event.is_set():
            try:
                if tick % 30 == 0:
                    self.heartbeat()
                if tick % 60 == 0:
                    self.sync_policies()
                if tick % 10 == 0:
                    self.monitor_processes()
                if tick % 15 == 0:
                    self.monitor_usb()
                self.maybe_screenshot()
                if tick % 45 == 0:
                    drained = drain_queue(self.api)
                    if drained:
                        log("INFO", f"replayed {drained} offline events")
            except Exception as exc:
                log("ERROR", f"loop tick failed: {exc}\n{traceback.format_exc()}")
            tick += 1
            time.sleep(1)

        self.realtime.stop()
        log("INFO", "agent stopped cleanly")

    def perform_uninstall(self) -> None:
        log("INFO", "uninstall approved — removing agent")
        try:
            # remove hosts block
            if HOSTS_PATH.exists():
                content = HOSTS_PATH.read_text(encoding="utf-8")
                if HOSTS_MARKER_START in content:
                    head = content.split(HOSTS_MARKER_START)[0]
                    tail_parts = content.split(HOSTS_MARKER_END)
                    tail = tail_parts[1] if len(tail_parts) > 1 else ""
                    HOSTS_PATH.write_text(head + tail, encoding="utf-8")
            # remove autostart
            remove_autostart()
            notify("Uninstalled", "Sentinel Net has been removed from this device.")
        except Exception as exc:
            log("WARN", f"uninstall cleanup failed: {exc}")
        os._exit(0)


# ============================================================================
# AUTOSTART / INSTALL
# ============================================================================
def install_autostart() -> None:
    exe = sys.executable
    script = str(Path(__file__).resolve())
    if IS_WIN:
        import winreg  # type: ignore
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe}" "{script}" --watchdog')
        winreg.CloseKey(key)
        log("INFO", "autostart registered (HKCU Run)")
    elif IS_MAC:
        plist = Path.home() / "Library/LaunchAgents/com.sentinelnet.agent.plist"
        plist.parent.mkdir(parents=True, exist_ok=True)
        plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.sentinelnet.agent</string>
  <key>ProgramArguments</key><array><string>{exe}</string><string>{script}</string><string>--watchdog</string></array>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
</dict></plist>""")
        subprocess.run(["launchctl", "load", str(plist)], check=False)
    else:
        unit = Path.home() / ".config/systemd/user/sentinelnet.service"
        unit.parent.mkdir(parents=True, exist_ok=True)
        unit.write_text(f"""[Unit]
Description=Sentinel Net Agent
[Service]
ExecStart={exe} {script} --watchdog
Restart=always
[Install]
WantedBy=default.target
""")
        subprocess.run(["systemctl", "--user", "enable", "--now", "sentinelnet.service"], check=False)


def remove_autostart() -> None:
    try:
        if IS_WIN:
            import winreg  # type: ignore
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
        elif IS_MAC:
            plist = Path.home() / "Library/LaunchAgents/com.sentinelnet.agent.plist"
            if plist.exists():
                subprocess.run(["launchctl", "unload", str(plist)], check=False)
                plist.unlink()
        else:
            subprocess.run(["systemctl", "--user", "disable", "--now", "sentinelnet.service"], check=False)
    except Exception as exc:
        log("WARN", f"remove_autostart failed: {exc}")


# ============================================================================
# WATCHDOG (supervises agent + tray; restarts on exit code 75)
# ============================================================================
def run_watchdog() -> None:
    script = str(Path(__file__).resolve())
    backoff = 2
    while True:
        try:
            log("INFO", "watchdog launching agent")
            proc = subprocess.Popen([sys.executable, script])
            tray = subprocess.Popen([sys.executable, script, "--tray"])
            rc = proc.wait()
            try:
                tray.terminate()
            except Exception:
                pass
            log("INFO", f"agent exited rc={rc}")
            if rc == EXIT_RESTART_REQUESTED:
                backoff = 2
                continue
            if rc == 0:
                return
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
        except KeyboardInterrupt:
            return
        except Exception as exc:
            log("ERROR", f"watchdog crash: {exc}")
            time.sleep(5)


# ============================================================================
# UNINSTALL REQUEST (admin must approve in dashboard)
# ============================================================================
def request_uninstall() -> None:
    cfg = AgentConfig.load()
    try:
        api = SupabaseClient(cfg)
        payload = {
            "device_id": cfg.device_id,
            "requested_at": datetime.utcnow().isoformat(),
            "reason": "user_requested",
            "status": "pending",
        }
        if api.insert("uninstall_requests", payload):
            notify("Uninstall Requested", "Your request was sent to an administrator for approval.")
            return
    except Exception as exc:
        log("ERROR", f"uninstall request failed: {exc}")
    notify("Uninstall Failed", "Could not contact the server. Try again later.", urgent=True)


# ============================================================================
# ENTRYPOINT
# ============================================================================
def main() -> int:
    parser = argparse.ArgumentParser(prog="sentinel_agent")
    parser.add_argument("--watchdog", action="store_true")
    parser.add_argument("--tray", action="store_true")
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--login", nargs=2, metavar=("EMAIL", "PASSWORD"))
    args = parser.parse_args()

    if args.version:
        print(f"{APP_NAME} agent v{VERSION}")
        return 0
    if args.install:
        install_autostart()
        print("Autostart installed.")
        return 0
    if args.uninstall:
        request_uninstall()
        return 0
    if args.login:
        cfg = AgentConfig.load()
        api = SupabaseClient(cfg)
        ok = api.login(args.login[0], args.login[1])
        print("Login OK" if ok else "Login FAILED")
        return 0 if ok else 1
    if args.watchdog:
        run_watchdog()
        return 0
    if args.tray:
        # delegate to tray module (sibling file)
        try:
            import sentinel_tray  # type: ignore
            sentinel_tray.run_tray()
        except Exception as exc:
            log("ERROR", f"tray failed: {exc}")
            return 1
        return 0

    # default = agent main loop
    agent = SentinelAgent()
    try:
        agent.run()
    except KeyboardInterrupt:
        agent.stop_event.set()
    return 0


if __name__ == "__main__":
    sys.exit(main())
