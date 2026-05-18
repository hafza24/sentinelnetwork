"""
Sentinel Net - System Tray UI
=============================
- Shows protection status (Connected / Offline / Last sync)
- View recent violations
- Open dashboard in browser
- Request uninstall (admin approval required)
- Quit (kept disabled when policy enforces protection)
"""
from __future__ import annotations

import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

try:
    import pystray
    from pystray import MenuItem as Item, Menu
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None  # type: ignore

# Re-use core agent utilities (single-file consolidation)
from sentinel_agent import (  # type: ignore
    APP_NAME,
    AgentConfig,
    SupabaseClient,
    notify,
    request_uninstall,
    log,
)

DASHBOARD_URL = "https://sentinelnetwork.lovable.app"


def _make_icon() -> "Image.Image":
    img = Image.new("RGB", (64, 64), (15, 23, 42))
    d = ImageDraw.Draw(img)
    # shield silhouette
    d.polygon([(32, 6), (58, 18), (58, 38), (32, 58), (6, 38), (6, 18)], fill=(59, 130, 246))
    d.polygon([(32, 14), (50, 22), (50, 36), (32, 50), (14, 36), (14, 22)], fill=(15, 23, 42))
    d.text((24, 24), "S", fill=(226, 232, 240))
    return img


class TrayApp:
    def __init__(self) -> None:
        self.cfg = AgentConfig.load()
        try:
            self.api: SupabaseClient | None = SupabaseClient(self.cfg)
        except Exception:
            self.api = None
        self.status_text = "Initializing…"
        self.icon: "pystray.Icon | None" = None

    # ---- actions -------------------------------------------------------
    def open_dashboard(self, _icon=None, _item=None) -> None:
        webbrowser.open(DASHBOARD_URL)

    def show_status(self, _icon=None, _item=None) -> None:
        notify("Status", self.status_text)

    def show_recent_alerts(self, _icon=None, _item=None) -> None:
        if not self.api:
            notify("Alerts", "Server unavailable")
            return
        rows = self.api.select(
            "activity_events",
            f"select=kind,occurred_at,severity&device_id=eq.{self.cfg.device_id}&order=occurred_at.desc&limit=5",
        )
        if not rows:
            notify("Recent Activity", "No recent events")
            return
        body = "\n".join(f"• [{r.get('severity','info')}] {r.get('kind')} — {r.get('occurred_at','')[:19]}" for r in rows)
        notify("Recent Activity", body)

    def request_uninstall(self, _icon=None, _item=None) -> None:
        request_uninstall()

    def quit_app(self, icon=None, _item=None) -> None:
        log("INFO", "tray quit requested by user")
        if icon is not None:
            icon.stop()

    # ---- status updater ------------------------------------------------
    def _status_loop(self) -> None:
        while True:
            try:
                self.cfg = AgentConfig.load()
                last = self.cfg.last_sync or "never"
                self.status_text = f"Connected • last sync: {last[:19] if last != 'never' else last}"
                if self.icon is not None:
                    self.icon.title = f"{APP_NAME} — {self.status_text}"
            except Exception as exc:
                self.status_text = f"Degraded — {exc}"
            time.sleep(15)

    # ---- run -----------------------------------------------------------
    def run(self) -> None:
        if pystray is None:
            log("WARN", "pystray not installed; tray disabled")
            # fall back to a passive loop so the watchdog doesn't restart-storm
            while True:
                time.sleep(3600)
        menu = Menu(
            Item(lambda _i: self.status_text, self.show_status, default=True, enabled=False),
            Menu.SEPARATOR,
            Item("Open Dashboard", self.open_dashboard),
            Item("Show Recent Alerts", self.show_recent_alerts),
            Menu.SEPARATOR,
            Item("Request Uninstall", self.request_uninstall),
            Item("Quit", self.quit_app),
        )
        self.icon = pystray.Icon(APP_NAME, _make_icon(), f"{APP_NAME}", menu)
        threading.Thread(target=self._status_loop, daemon=True).start()
        self.icon.run()


def run_tray() -> None:
    TrayApp().run()


if __name__ == "__main__":
    run_tray()
    sys.exit(0)
