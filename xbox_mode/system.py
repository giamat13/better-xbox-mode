"""System actions for the quick settings panel: volume, brightness, settings pages, screenshots and power."""
import ctypes
import os
import subprocess

from .sendinput import send_combo, send_vk

CREATE_NO_WINDOW = 0x08000000
VK_VOLUME_MUTE, VK_VOLUME_DOWN, VK_VOLUME_UP = 0xAD, 0xAE, 0xAF
VK_LWIN, VK_SHIFT, VK_S = 0x5B, 0x10, 0x53
BRIGHTNESS_STEP = 10
SETTINGS_PAGES = {"wifi": "ms-settings:network-wifi", "bluetooth": "ms-settings:bluetooth",
                  "display": "ms-settings:display", "sound": "ms-settings:sound"}
POWER = {"sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
         "restart": ["shutdown", "/r", "/t", "0"], "shutdown": ["shutdown", "/s", "/t", "0"]}
# Actions that end the session or turn the machine off; the UI asks twice before running them.
DESTRUCTIVE = {"sleep", "restart", "shutdown"}


def brightness_script(delta):
    """PowerShell that nudges the built-in display's brightness by delta percent (laptops and tablets)."""
    return ("$b=(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness;"
            f"$n=[Math]::Min(100,[Math]::Max(0,$b+({int(delta)})));"
            "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1,$n)")


def _powershell(script):
    subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                     creationflags=CREATE_NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run(action):
    """Runs one quick settings action. Returns False for an action that does not exist."""
    if action == "volume_up":
        send_vk(VK_VOLUME_UP)
    elif action == "volume_down":
        send_vk(VK_VOLUME_DOWN)
    elif action == "mute":
        send_vk(VK_VOLUME_MUTE)
    elif action == "brightness_up":
        _powershell(brightness_script(BRIGHTNESS_STEP))
    elif action == "brightness_down":
        _powershell(brightness_script(-BRIGHTNESS_STEP))
    elif action in SETTINGS_PAGES:
        os.startfile(SETTINGS_PAGES[action])
    elif action == "screenshot":
        send_combo([VK_LWIN, VK_SHIFT, VK_S])
    elif action == "lock":
        ctypes.windll.user32.LockWorkStation()
    elif action in POWER:
        subprocess.Popen(POWER[action], creationflags=CREATE_NO_WINDOW)
    else:
        return False
    return True
