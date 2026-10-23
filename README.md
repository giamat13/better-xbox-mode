# Xbox Mode

A console-style, full-screen shell for Windows that you drive entirely with a gamepad: a home screen, an app
library, a Guide-button task switcher, controller-as-mouse for desktop apps, and a built-in on-screen keyboard
(English, Hebrew, symbols).

It is modelled on the Windows 11 "Xbox full screen experience" from public documentation and screenshots. It is a
behavioral approximation, not a copy, and **it is not affiliated with, endorsed by, or sponsored by Microsoft**.
"Xbox" and the Xbox logo are trademarks of Microsoft.

## How it works

```
 Electron (UI)  ──JSON lines over stdio──  Python engine (system layer)
 renderer/*.html,css,js                    xbox_mode/*.py, no pip dependencies
 main.js, preload.js                       gamepad (XInput), windows, apps, mouse/keyboard injection
```

- The **UI** (home, switcher, keyboard) is HTML/CSS/JS in Electron. Window thumbnails come from Electron's
  `desktopCapturer`, app icons from the Windows shell.
- The **engine** is Python using only the standard library and `ctypes`. It polls the controller, lists and focuses
  windows, hides the taskbar, and injects mouse and keyboard input.

## Requirements

- Windows 10 or 11
- Node.js 20+ and Python 3.10+
- An XInput gamepad (Xbox controllers and most compatible pads)

## Run

```
npm install
npm start               # full screen, hides the taskbar
npm run windowed        # 1280x720 window, handy for development
```

The engine uses `python` from your `PATH`. To use a specific interpreter, set `XBOX_PYTHON`.

If the app is killed before it can restore the taskbar, bring it back with:

```
python -c "from xbox_mode import winman; winman.set_taskbar_visible(True)"
```

## Controls

| Where | Input | Action |
|---|---|---|
| Anywhere | Xbox (Guide) button | Open the app switcher |
| Anywhere | Hold the Xbox button | Quick settings: volume, brightness, Wi-Fi, Bluetooth, screenshot, lock, sleep, restart, shut down |
| Home | D-pad / left stick | Navigate |
| Home | A / B | Select / back |
| Home | LB / RB | Previous / next tab (Library, Places, Running, Settings) |
| Home | Menu | Settings |
| Places tab | A / X | Open a favourite site, folder or recent file / remove a favourite site |
| Running tab | X | Close the selected app |
| Switcher | A / X / B | Switch to app / close app / leave |
| Switcher | Menu | Window options: maximize, minimize, snap left or right, move to the next monitor, close |
| Desktop apps | Left stick | Move the cursor |
| Desktop apps | A / X | Left / right click |
| Desktop apps | Right stick | Scroll, sideways too |
| Desktop apps | Click the right stick | Jump the cursor to the next monitor |
| Desktop apps | D-pad, B | Arrow keys, Esc |
| Desktop apps | LB | Copy (Ctrl+C), then open the clipboard history (Win+V) |
| Desktop apps | Y | Open or close the on-screen keyboard |
| Desktop apps | RT / LT | Zoom the whole screen in / out (no Magnifier window; back at 100% it is gone). Both triggers reset |
| Keyboard | A / B / X | Type / backspace / space |
| Keyboard | Menu / LB / RB | Enter / cursor left / cursor right |
| Library grid | D-pad, LB / RB | Move, jump a page |
| Library grid | Y / A / B | Search / launch / back |
| Switcher | Y | Flip the selected app between "game" (keeps the controller) and "mouse" |

The on-screen keyboard has English, Hebrew and symbol layers, word suggestions above the letters (built-in words plus
the ones you type), a shortcuts layer (sticky Ctrl / Alt / Win / Shift that apply to the next key, copy, paste, cut,
undo, redo, select all, save, close, refresh, find, Alt+Tab, desktop, dictation with Win+H, clipboard history, the
Windows emoji panel, arrows and function keys) and an emoji layer.

The library also lists Microsoft Store apps. The Places tab shows favourite sites (edit `favorites` in the config),
your folders and your recently opened files. Settings can run Xbox Mode as administrator (so it can drive windows that
run as administrator; Windows asks for permission on each start, and the UAC prompt itself still cannot be controlled),
move the interface to another display, and switch interface sounds and the button hints bar off. The controller's
battery shows next to the clock, with a notification when it runs low.

Outside the Xbox UI the controller drives the mouse in every window, except games. A window counts as a game when
its program reads the controller itself (it loaded XInput, DirectInput, SDL, GameInput or Steam's API), runs exclusive
Direct3D full screen, or cannot be inspected (anti-cheat protected). In a game only the Guide button stays ours. Each
card in the switcher shows what was detected, and Y flips it; the choice is remembered. Launchers such as Steam and
Epic default to "mouse".
Apps launched from the library are made borderless and screen-sized (like pressing F11); turn it off in Settings.
Dev fallback in the UI window: arrow keys, Enter (A), Esc (B), X, Y, Q/E (LB/RB), S (Menu), F1 (Guide).

## Configuration

Settings live in `%APPDATA%\xbox_mode\config.json` and can be changed from the Settings tab.

## Browser extension

`extension/` is a Chrome extension that adds controller support to YouTube (the page keeps its normal look), and only
while Xbox Mode is running. Load it from `chrome://extensions` (Developer mode, "Load unpacked", pick `extension`).

Xbox Mode serves a tiny status endpoint on `127.0.0.1:47821` that answers only requests coming from a browser
extension. The extension polls it; while it answers, YouTube gets D-pad navigation between its controls (A selects,
B goes back, Y jumps to the search box and opens the on-screen keyboard, LB / RB scroll, or change the volume on a
video, Menu moves between the player and the rest of the page) and a clear focus ring. When Xbox Mode is closed YouTube
is untouched.

## Steam and the Guide button

Steam also listens to the Guide button and may raise its own window (Big Picture or the regular client) over the
switcher. For four seconds after each Guide press the engine minimizes any Steam window that takes the screen and
brings the switcher back, unless you have just launched an app from the library (so opening Steam yourself works).
This is a workaround; if Steam still wins, turn off its "Guide Button Focuses Steam" (Settings, Controller).

## Known limitations

- The Guide button is read through XInput's undocumented `XInputGetStateEx` (ordinal 100); some pads and drivers
  do not report it.
- Live thumbnails of exclusive-fullscreen DirectX games may be black.
- Apps are discovered from Start Menu shortcuts; Microsoft Store apps are not listed yet.
- Windows only.

## Tests

```
python -m unittest discover -s tests -v
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Released under the [MIT License](LICENSE).
