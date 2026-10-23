# Contributing

Thanks for helping out. Issues and pull requests are welcome.

## Setup

```
npm install
npm run windowed
python -m unittest discover -s tests -v
```

## Layout

- `main.js`, `preload.js`: Electron main process, the bridge to the engine, window and icon helpers.
- `renderer/`: UI (home, switcher, keyboard). Plain HTML/CSS/JS, no build step.
- `xbox_mode/`: Python engine. Standard library only; please keep it dependency-free.
- `tests/`: unit tests for the engine logic that does not need hardware.

## Guidelines

- Keep UI code out of Python and system calls out of the renderer; they talk through the JSON protocol described at
  the top of `xbox_mode/engine.py`.
- Match the surrounding style. Keep comments for the non-obvious "why".
- Do not add artwork, logos or code copied from Microsoft or other proprietary software.
- When you change input behavior, add a test if it can be tested without a physical controller, and say in the PR how
  you tried it on hardware.
