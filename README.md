# Mini Racing Game

A 2D top-down racing game written in Python with pygame. You race one car
against three AI opponents over three laps, collecting bonuses and using a
nitro boost.

## Features

- Player car controlled with **WASD** or **arrow keys**
- **3 AI opponent cars** with selectable difficulty (Easy / Normal / Hard)
- **3 tracks** to choose from: Oval Speedway, Snake Circuit, Hairpin Loop
- **Lap timing** — current lap, best lap, and every lap listed at the finish
- **Live race position** (1st to 4th), calculated from distance around the track
- **Random bonus pickups** — yellow coins give points, blue ones give nitro
- **Off-track penalty** — driving on the grass cuts your top speed by more than half
- **Nitro boost** — charges while you drive, spend it with **X**

## Requirements

- Python 3.9 or newer
- The packages listed in `requirements.txt` (just `pygame-ce`)

## Setup

```bash
git clone https://github.com/Maryum-Khalid/DSA_Project.git
cd DSA_Project
pip install -r requirements.txt
```

Using a virtual environment instead (keeps the project's packages separate
from the rest of your system):

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

## Running

```bash
python racing_game.py
```

Pick a track and a difficulty on the menu, then press **Enter** to start.

## Controls

| Key | Action |
| --- | --- |
| `W` / `Up` | Accelerate |
| `S` / `Down` | Brake and reverse |
| `A` / `Left` | Steer left |
| `D` / `Right` | Steer right |
| `X` | Use nitro boost |
| `R` | Restart the race |
| `Esc` | Back to the menu |

Menu navigation: left/right changes the track, up/down changes the difficulty.

## Troubleshooting

**`ModuleNotFoundError: No module named 'pygame'`**
The dependency was not installed, or it went into a different Python
installation than the one running the game. Install it with the same
interpreter you use to run it:

```bash
python -m pip install -r requirements.txt
```

**pygame fails to build, with errors about `distutils` or a C compiler**
You are installing the original `pygame` rather than `pygame-ce`. On Python
3.13 and newer, `pygame` has no prebuilt package and tries to compile from
source. Use `pip install -r requirements.txt`, which installs `pygame-ce`.

**`pygame` and `pygame-ce` conflict**
The two packages cannot be installed at the same time, since both provide the
`pygame` module. If you already have the original, remove it first:

```bash
pip uninstall pygame
pip install -r requirements.txt
```

## Project layout

| File | Purpose |
| --- | --- |
| `racing_game.py` | The whole game — settings, track, car, bonuses, and game loop |
| `project.ipynb` | Earlier browser-based prototype of the same idea |
| `requirements.txt` | Python packages needed to run the game |

`racing_game.py` is organised in numbered sections: settings, math helpers,
`Track`, `Car`, `Bonus`, then the `Game` class holding the menu, the race loop
and the results screen.
