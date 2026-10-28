# GitHub Universe 2026
Mega directory of my Universe activities Oct 27-29 in SF!

The apps/ directory contains my custom badge apps:
Feel free to load these onto your badge, fork, or open issues / request changes!

| App | What it does | Badge components
|---|---|---|
| **Steps** | Pedometer with daily goal ring, distance, cadence, best/all-time, live sensor trace, hold-to-reset | IMU hardware step counter + accelerometer, `State` persistence, RTC/`time.localtime` for daily rollover, case lights (pulse per step), Up/Down/Select |
| **Marble Maze** | Procedurally generated perfect mazes (10 levels, tightening grids), tilt-driven marble physics with wall collision, pits from level 3, per-level best times, self-levelling on start | IMU accelerometer (with `rotate_180` handling), D-pad as fallback steering, `State`, Select / Left+Right combo |
| **Contrib Graph** | Your GitHub contribution year: 53×7 grid with month labels, last-16-weeks zoom, numbers page (weekday totals, longest streak dates), streaks/busiest/average; cached offline, background refresh | Wi-Fi + `fetch` (non-blocking), `/state` file cache, `secrets.py` (`GITHUB_USERNAME`), Left/Right/Select |
| **Amazeball** | The Copilot Amazeball: purple helmet, navy visor, blue goggles and bar eyes that squint/blink; shake flips it to the window side where the blue triangle floats up with one of 30 dev-flavoured answers | IMU jerk-energy shake detection, case lights (flicker while shaking, flash on reveal), Select as a no-shake alternative, vector shape transforms for the flip |