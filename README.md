# Xbox Mode

A clone of the Windows 11 "Xbox full screen experience", built from public documentation of its behavior.
The original is not installed on the development machine, so this is a behavioral approximation rather than a
binary-level 1:1 copy.

## Run

```
pip install -r requirements.txt
python -m xbox_mode            # full screen, hides the taskbar
python -m xbox_mode --windowed # 1280x720 window for development
```

## Controls

| Where | Input | Action |
|---|---|---|
| Launcher | D-pad / left stick | Navigate |
| Launcher | A | Launch / select |
| Launcher | LB / RB | Switch tab (Home, Library, Settings) |
| Launcher | Y | Rescan apps |
| Anywhere | Guide (Xbox button) | Open the switcher over the launcher |
| Switcher | A / X / B | Switch to window / close window / back |
| Desktop apps | Left stick | Move cursor |
| Desktop apps | A / X | Left / right click |
| Desktop apps | Right stick | Scroll |
| Desktop apps | D-pad | Arrow keys |
| Desktop apps | B | Esc |
| Desktop apps | Y | Open the built-in on-screen keyboard (English / Hebrew / symbols) |
| Keyboard | D-pad / stick, A | Move, type |
| Keyboard | B / X / Start | Backspace / space / Enter |
| Keyboard | LB / RB | Cursor left / right |
| Keyboard | Y / Guide | Close |

Keyboard fallback for development: arrows, Enter (A), Esc (B), X, Y, Q/E (LB/RB), F1 (Guide).

Controller-as-mouse is automatically off while a full-screen app (a game) is in the foreground.
The taskbar is restored on exit.
