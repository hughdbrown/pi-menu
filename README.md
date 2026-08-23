# Pi Menu — Stellar Unicorn applications

Programs for a Raspberry Pi with a [Pimoroni Stellar
Unicorn](https://shop.pimoroni.com/products/space-unicorns) (16×16 RGB LED
panel) attached over USB:

| Program | What it does |
| --- | --- |
| **Pi Menu** (`pi-menu`) | Lists the other programs and runs the one you pick in a terminal window. |
| **Game of Life** (`pi-life`) | Conway's Game of Life on the panel, with start/stop/reset/random and a 16×16 grid you draw on. |
| **Image Shower** (`pi-imgshow`) | Pick an image file and show it on the panel. PNG, JPEG, BMP, WebP and animated GIF. |
| **Platform Game** (`pi-platformer`) | A side-scrolling platform game with chiptune from the panel's speaker. Sixty levels, four boss fights, and a menu drawn on the panel itself. |
| **Panel Self-Test** (`pi-menu-doctor`) | Checks every layer between the Pi and the LEDs, then lights the panel up. Run this first when the panel stays dark. |
| **Flash Panel Firmware** (`pi-menu-flash`) | Copies the frame server onto the Stellar Unicorn's Pico over USB. Needs nothing but pyserial. |

Each app opens a window for its controls and mirrors what it is doing onto
the LED panel. When Pi Menu launches one it does so inside a terminal, so
connection messages and errors stay visible.

## How the pieces fit

The Stellar Unicorn is a Raspberry Pi **Pico W**, not a Pi HAT, so the two
boards talk over USB:

```
Raspberry Pi                                  Stellar Unicorn (Pico W)
┌──────────────────────────────┐   USB CDC    ┌──────────────────────┐
│ pi-menu ──launches──▶        │ ──frames──▶  │ stellar_frame_server │
│   pi-life       (Life rules) │              │        │             │
│   pi-imgshow    (scaling)    │ ◀── acks ─── │        ▼             │
│   pi-platformer (physics)    │              │   16×16 RGB LEDs     │
└──────────────────────────────┘              └──────────────────────┘
         all the logic                           just blits frames
```

Every decision is made on the Pi, which sends complete 768-byte frames. The
Pico only paints them. That keeps the firmware trivial and means the Life
rules, the image scaling and the platform game's physics are ordinary Python
that runs — and is tested — without any hardware.

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

`install.sh` offers to do the next step for you, and you can run it any time:

```bash
pi-menu-flash
```

That copies `src/pi_menu/firmware/stellar_frame_server.py` onto the Pico as
`main.py`, reads it back to check it arrived intact, and restarts the board.
It talks to MicroPython's raw REPL over pyserial, so there is nothing extra to
install — no `mpremote`, no `ampy`. (Both still work if you prefer them, as
does dragging the file across in Thonny.)

Re-run it whenever you update this repo. The Pi refuses to drive firmware
older than the protocol it expects, and says so rather than misbehaving.

The board needs the Pimoroni MicroPython build, which already includes the
`stellar` and `picographics` modules.

**One catch worth knowing.** The frame server disables Ctrl-C (see the
protocol section), so no ordinary tool can interrupt it to replace the file.
`pi-menu-flash` handles that by asking the running server to step aside over
the protocol itself. If the board is wedged and even that fails, **hold the A
button while the panel powers up** — that skips the frame server and leaves
you a REPL.

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
- **Click or drag the grid** to draw your starting pattern.
- **While it runs, the panel is the display.** The on-screen grid stops
  following the simulation and greys out, so there is only one thing to watch
  and no second copy racing the LEDs. Press Stop and the grid comes back for
  editing. Tick **Mirror on screen** to have the window follow along as well —
  with no panel attached that is the default, since otherwise the window would
  have nothing in it.
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

### Platform Game

Everything is on the panel — there is nothing to look at in the window. Keep
it focused, because it is what holds the keyboard.

- **Left** and **Right** run, **Up** jumps. Holding Up jumps higher than
  tapping it. On a ladder, Up and Down climb.
- **Enter** chooses, **Esc** goes back. From a level, Esc returns to the menu.
- The menu is two words: **PLAY** carries on from the first level you have not
  finished, **LVLS** opens the picker — a pixel per level, eight to a row,
  green once it is done, with the number of the one under the cursor below.
- **Collect every coin to open the goal**, then reach it. The goal is dim grey
  until the last coin is taken, then it flashes green.
- There are no lives. Anything that kills you simply starts the level again.

Sixty levels, each new mechanic introduced on its own before any level
combines them. Some levels are two panels tall — the camera follows in both
directions. Colour is the only label the panel has room for:

| | Colour | What it is |
| --- | --- | --- |
| `@` | cyan | you |
| `o` | amber | a coin. Take them all and the goal opens |
| `G` | grey → flashing green | the goal, shut then open |
| `=` | dark blue | ordinary ground |
| `-` `\|` | bright blue | a platform sliding along a track. Ride it |
| `b` | lime | a bounce pad — about six cells, well past a jump |
| `i` | pale blue | ice. Almost no grip; stopping has to be planned |
| `<` `>` | teal | a conveyor. The highlight travels the way it pushes you |
| `c` | rust | a crumbling tile. It holds you once, then it is gone |
| `p` | magenta | a portal. Its pair is somewhere else on the level |
| `^` | red | a spike |
| `E` | pink | an enemy, pacing its ledge. Go over it — you cannot land on it |
| `H` | brown | a ladder. Up and Down climb it; it lines you up as you go |
| `_` | pale green | a one-way platform. Jump up through it, land on top |
| `u` | flickering cyan | an updraught. Step in and it carries you up |
| `x` | violet | a blinking block, solid half the time on a fixed cycle |

**Boss fights.** Levels 15, 30, 45 and 60 each end in an arena under an 8×8
demon, drawn dim behind the level — you never touch it. It slams fists down
where you stand and throws fireballs on a pattern that quickens wave by wave;
both kill. There is nothing to shoot and no health bar: survive everything it
has and it withdraws, which is what opens the goal. Each demon throws
differently — the fists are the same everywhere, the fireballs are what you
learn.

**Music.** The game plays three-channel chiptune — square lead, triangle
bass, noise percussion — through the Stellar Unicorn's own speaker: a title
theme, field themes that darken as you go deeper, a boss theme, stings for
death and victory, and a finale for level sixty. All of it is original,
written for this game. No panel, no speaker: the music simply does not play,
and nothing else cares.

The jump is deliberately forgiving. It still fires for a few hundredths of a
second after you walk off a ledge, and one pressed just before you land is
remembered and fires on landing. On a screen sixteen pixels tall, a jump
missed by one frame is a death, and without that the game reads as broken
rather than hard.

### No panel attached?

The apps fall back to an ANSI preview in their terminal rather than refusing
to start — handy for working on the code away from the hardware. The fallback
announces itself in a banner you cannot miss, and each window carries an
**Output:** line naming the device it is really drawing on, because a preview
that runs perfectly looks exactly like a working program.

Force the preview with `--backend term`. Use `--backend serial` to make a
missing panel an error instead of a fallback, and `--port /dev/ttyACM0` to
name a device explicitly.

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
| `0x00` ping | — | `STELLAR16 2\n` |
| `0x01` blit | 768 bytes RGB, row-major, x fastest | `K\n` |
| `0x02` brightness | 1 byte, 0–255 | `K\n` |
| `0x04` clear | — | `K\n` |
| `0x05` exit | — | `K\n`, then quits to the REPL |

**`0x03` is deliberately absent, and this is the single most important thing
about the protocol.** MicroPython's USB serial driver reads `0x03` as Ctrl-C:
it swallows the byte and raises `KeyboardInterrupt` in whatever is running.
Binary frame data is full of `0x03` — every pixel with a channel value of 3 —
so the firmware calls `micropython.kbd_intr(-1)` at boot to switch that off.
Keeping `0x03` out of the command set as well means a Pico still running old
firmware is merely confused by a clear rather than killed by one. The ping
reply carries a protocol version so the Pi can tell you when the two have
drifted apart.

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

`tests/test_platform_levels.py` is worth knowing about: it plays every level
of the platform game with a search that steps the real physics, and passes
only when it finds a sequence of key presses that finishes the level. A map
can be well formed, readable and still impossible — a coin one cell above the
jump arc looks exactly like a coin one cell below it — so a new or edited
level that cannot be won fails the suite rather than the player. It has caught
over twenty broken levels so far, including every one of the first drafts of
the tall levels — a ladder through a one-cell hole is unusable unless the
game lines the climber up with the rung, which is a physics fix no amount of
staring at the map would have found.

Two things about that search are worth knowing before adding a level. It
carries the world's clock in its state, so a level's *period* — how long until
every moving thing is back where it started — multiplies its work; keep enemy
pens and mover tracks to matching lengths and the period stays small. And it
scores positions by a flood fill over open ground rather than by straight-line
distance, which is what lets it find a portal that leads away from the goal.

## Troubleshooting

**The panel stays dark, or the app runs in the terminal instead.** Run
`pi-menu-doctor` (or Panel Self-Test in the menu). It walks the whole path one
layer at a time and names the layer that broke. The usual causes are a Pico
that is not running `main.py`, and a `dialout` group change that has not taken
effect yet — `id -nG | grep dialout`, and log out and back in if it is missing.

**It worked once and then stopped until I power-cycled the Pico.** That is
firmware from before the `kbd_intr` fix: the clear sent when an app exited was
byte `0x03`, which killed the frame server. Run `pi-menu-flash`.

**`pi-menu-flash` cannot get the board into its REPL.** Hold the **A button**
while power-cycling the panel, then run it again. Ctrl-C is disabled while the
frame server runs, so the A button is the reliable way in.

**Nothing appears in the Raspberry Pi menu.** Log out and back in, or run
`lxpanelctl restart`. The entries are in `~/.local/share/applications`.

**The menu says no terminal emulator was found.** `sudo apt install
lxterminal`. The menu still runs apps without one, just without a console.
