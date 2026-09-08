import sys
import time
import threading
import ctypes
from typing import Optional

import pystray

from config import (
    trim_memory,
    acquire_single_instance,
    is_startup_enabled,
    set_startup,
    is_light_mode,
    get_peak_millivolts,
    set_peak_millivolts,
)
from devices import find_pulsar, read_pulsar_battery
from icon_drawer import get_icon_data


# =============================================================================
# Tray Application
# =============================================================================
class BatteryTrayApp:
    def __init__(self):
        self.icon = None
        self.running = True
        self.last_battery = -1
        self.status = "disconnected"
        self.current_model = "No device"

        self.last_millivolts: Optional[int] = None
        self.peak_millivolts: int = get_peak_millivolts()

        self.last_theme: bool = is_light_mode()
        self._icon_cache = {}
        self.poll_thread = threading.Thread(target=self.poll_loop, daemon=True)

    def update_battery_level(self, battery: int, charging: bool = False):
        self.last_battery = battery
        self.status = "charging" if charging else "connected"
        self.update_tray()

    def create_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(lambda item: self.current_model, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Start with Windows", self.toggle_startup,
                             checked=lambda item: is_startup_enabled()),
            pystray.MenuItem("Exit", self.on_exit),
        )

    def get_voltage_str(self) -> Optional[str]:
        if self.last_millivolts is None:
            return None
        if self.peak_millivolts > 0:
            return f"{self.last_millivolts}/{self.peak_millivolts} mV"
        return f"{self.last_millivolts} mV"

    def update_tray(self):
        if not self.icon:
            return

        self.last_theme = is_light_mode()
        self.icon.icon = get_icon_data(self.status, self.last_battery, self._icon_cache)

        volts = self.get_voltage_str()
        if self.status == "disconnected":
            self.icon.title = "Disconnected"
        elif self.status == "unknown":
            self.icon.title = "Battery unavailable"
        elif self.last_battery < 0:
            self.icon.title = "Waiting for battery reading..."
        else:
            details = []
            if self.status == "charging":
                details.append("charging")
            if volts:
                details.append(volts)
            suffix = f" ({', '.join(details)})" if details else ""
            self.icon.title = f"{self.last_battery}%{suffix}"

    def poll_loop(self):
        last_trim = time.time()
        while self.running:
            if time.time() - last_trim > 60:
                trim_memory()
                last_trim = time.time()

            if is_light_mode() != self.last_theme:
                self.update_tray()

            path, name, _ = find_pulsar()
            if path:
                self.current_model = name
                battery, charging, millivolts = read_pulsar_battery(path)
                if millivolts:
                    self.last_millivolts = millivolts
                    if millivolts > self.peak_millivolts:
                        self.peak_millivolts = millivolts
                        set_peak_millivolts(millivolts)
                if battery is not None:
                    self.update_battery_level(battery, bool(charging))
                elif self.last_battery < 0:
                    # Silence normally just means the mouse is asleep, so an
                    # established reading is kept rather than cleared.
                    self.status = "unknown"
                    self.update_tray()
                time.sleep(10)
                continue

            if self.status != "disconnected":
                self.status = "disconnected"
                self.current_model = "No device"
                self.update_tray()
            time.sleep(5)

    def on_exit(self, icon, item):
        self.running = False
        self.icon.stop()

    def toggle_startup(self, icon, item):
        set_startup(not item.checked)

    def run(self):
        self.icon = pystray.Icon(
            "MouseBatteryTray",
            get_icon_data(self.status, self.last_battery, self._icon_cache),
            "Initializing...",
            self.create_menu()
        )

        self.poll_thread.start()
        self.icon.run()


if __name__ == "__main__":
    if not acquire_single_instance():
        try:
            ctypes.windll.user32.MessageBoxW(
                None,
                "Mouse Battery Tray is already running in the notification area.",
                "Mouse Battery Tray",
                0x40,  # MB_ICONINFORMATION
            )
        except Exception:
            pass
        sys.exit(0)
    app = BatteryTrayApp()
    app.run()
