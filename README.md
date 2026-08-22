# Pi Menu — Stellar Unicorn applications

Three programs for a Raspberry Pi with a [Pimoroni Stellar
Unicorn](https://shop.pimoroni.com/products/space-unicorns) (16×16 RGB LED
panel) attached over USB:

| Program | What it does |
| --- | --- |
| **Pi Menu** (`pi-menu`) | Lists the other programs and runs the one you pick in a terminal window. |
| **Game of Life** (`pi-life`) | Conway's Game of Life on the panel, with start/stop/reset/random and a 16×16 grid you draw on. |
| **Image Shower** (`pi-imgshow`) | Pick an image file and show it on the panel. PNG, JPEG, BMP, WebP and animated GIF. |

Each app opens a window for its controls and mirrors what it is doing onto
the LED panel. When Pi Menu launches one it does so inside a terminal, so
connection messages and errors stay visible.

## How the pieces fit

The Stellar Unicorn is a Raspberry Pi **Pico W**, not a Pi HAT, so the two
boards talk over USB:

```
Raspberry Pi                                Stellar Unicorn (Pico W)
┌────────────────────────────┐   USB CDC    ┌──────────────────────┐
│ pi-menu ──launches──▶      │ ──frames──▶  │ stellar_frame_server │
│   pi-life     (Life rules) │              │        │             │
│   pi-imgshow  (scaling)    │ ◀── acks ─── │        ▼             │
└────────────────────────────┘              │   16×16 RGB LEDs     │
        all the logic                       └──────────────────────┘
                                                 just blits frames
```

Every decision is made on the Pi, which sends complete 768-byte frames. The
Pico only paints them. That keeps the firmware trivial and means the Life
rules and the image scaling are ordinary Python that runs — and is tested —
without any hardware.

## Installing

On the Raspberry Pi:

```bash
git clone <this repo> pi-menu
cd pi-menu
./install.sh
```

The installer creates a virtualenv in `~/.local/share/pi-menu/venv`, installs
the package, links `pi-menu`, `pi-life` and `pi-imgshow` into `~/.local/bin`,
and adds three entries to the Raspberry Pi desktop menu. It asks before
running anything with `sudo` — that is only ever `apt-get install python3-tk`
/ `python3-venv` if they are missing, and `usermod -a -G dialout` so you can
open the serial port.

Then set up the panel itself. Copy the firmware onto the Stellar Unicorn as
`main.py` so it starts at power-on:

```bash
mpremote cp firmware/stellar_frame_server.py :main.py
```

(Thonny works too, as does dragging the file across.) The firmware needs the
Pimoroni MicroPython build, which already includes the `stellar` and
`picographics` modules.

To remove everything: `./install.sh --uninstall`.

## Using it

Open **Pi Menu** from the Raspberry Pi menu, or run `pi-menu` in a terminal.
Pick a program and press Run.

### Game of Life

- **Start** / **Stop** run and pause the simulation.
- **Reset** rewinds to generation 0 of the current seed — the pattern you
  drew or the last one Random produced.
- **Clear** blanks the grid, and makes *that* the seed.
- **Random** fills the grid at the density set by the slider.
- **Click or drag the grid** to draw. It works while the simulation runs, so
  you can poke a living pattern and see what happens.
- Speed, brightness and colour have sliders. Keys: space, `r`, `n`, `c`, `q`.

The grid wraps around, so a glider leaving the right edge returns on the
left. On a board this small a hard edge kills travelling patterns almost
immediately; pass `--no-wrap` if you want that anyway. When the board
settles into a still life the simulation stops on its own and says so.

### Image Shower

Choose a file, and the 16×16 result appears in the preview and on the panel
together. Three scale modes decide what happens to a non-square image:
**Fit** shows all of it with black bars, **Fill** crops to the edges, and
**Stretch** distorts it to fill the panel. Animated GIFs play at their own
frame timings; untick Animate for just the first frame.

### No panel attached?

Both apps fall back to an ANSI preview in their terminal, printing why on the
way. Handy for working on the code away from the hardware. Force it with
`--backend term`, and name a port explicitly with `--port /dev/ttyACM0`.

## Adding your own programs

`install.sh` copies the app list to `~/.config/pi-menu/apps.json`. Add an
entry and press *Reload list*:

```json
{
  "apps": [
    {
      "name": "My Program",
      "description": "Shown under the list.",
      "command": ["{python}", "/home/pi/my_program.py"],
      "hold": "always"
    }
  ]
}
```

`command` is a list of arguments, never a single string, so nothing needs
shell quoting. `{python}` becomes the interpreter running the menu and
`{home}` your home directory. `hold` controls the terminal window after the
program exits: `on-error` (default), `always`, or `never`. Set
`"terminal": false` to run without a terminal window at all.

## The wire protocol

Each message is `"SU"`, a command byte, then a fixed payload.
`pi_menu/display/protocol.py` and `firmware/stellar_frame_server.py` must
agree; `tests/test_firmware_link.py` checks that they do.

| Command | Payload | Reply |
| --- | --- | --- |
| `0x00` ping | — | `STELLAR16\n` |
| `0x01` blit | 768 bytes RGB, row-major, x fastest | `K\n` |
| `0x02` brightness | 1 byte, 0–255 | `K\n` |
| `0x03` clear | — | `K\n` |

The Pi waits for each acknowledgement before sending the next frame, which
stops it running ahead of the panel. Frames are written from a background
thread that keeps only the newest one, so a slow link drops stale frames
instead of making the buttons feel sticky.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

The tests need no hardware. `tests/test_firmware_link.py` runs the real
firmware against a pseudo-terminal with the Pimoroni modules stubbed, so
both halves of the protocol are exercised together.

## Troubleshooting

**"Stellar Unicorn unavailable" every time.** Check the Pico is running the
frame server (`mpremote ls` should show `main.py`) and that you are in the
`dialout` group — `id -nG | grep dialout`. Group changes need a fresh login.

**Nothing appears in the Raspberry Pi menu.** Log out and back in, or run
`lxpanelctl restart`. The entries are in `~/.local/share/applications`.

**The menu says no terminal emulator was found.** `sudo apt install
lxterminal`. The menu still runs apps without one, just without a console.
