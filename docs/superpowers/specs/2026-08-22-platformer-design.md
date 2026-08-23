# Platform game for the Stellar Unicorn

A fifth application for Pi Menu: a side-scrolling platform game played with
the arrow keys and drawn entirely on the 16x16 LED panel.

## What it is

The player is one cyan pixel. Levels are wider than the panel — around 48
columns by 16 rows — and a camera follows the player horizontally. Collect
every amber coin to open the goal, avoid the red spikes and the drop off the
bottom, then reach the goal to finish the level.

The menu lives on the panel too. There is no Tk control surface beyond the
window that holds keyboard focus and prints a status line: `PLAY` and `LVLS`
are drawn in a 3x5 pixel font, and the level picker is a grid of coloured
tiles. Arrow keys and Enter drive all of it.

## Why it is built this way

The panel is the display, so the game must be legible at 16x16 and playable
without looking anywhere else. That rules out on-screen text of any length
and rules in a tiny font, a tile grid, and colour as the only status
indicator. It also means the Tk window must not become a second, competing
view of the game — it holds focus and reports errors, nothing more.

Everything below the Tk layer is ordinary Python with no I/O, following the
split that `pi_menu.life` already uses: `Board` and `LifeSession` are tested
without hardware, and only `life/app.py` touches a widget. A game has more
moving parts than Life, so the same idea is carried further and the parts are
kept small.

## Modules

| Module | Responsibility | Depends on |
| --- | --- | --- |
| `platformer/font.py` | 3x5 glyphs for the menu words and digits 0-9 | nothing |
| `platformer/level.py` | `Level`: parse an ASCII map; `solid()`, coins, spikes, spawn, goal | nothing |
| `platformer/levels.py` | The twenty-seven level maps, as ASCII art with ids | `level` |
| `platformer/world.py` | `World`: physics, collision, pickups, death, win | `level` |
| `platformer/camera.py` | `window_x()`: centre on the player, clamp to the level | nothing |
| `platformer/render.py` | Framebuffer painters for world, menu, picker and flashes | `level`, `world`, `font`, `display.protocol` |
| `platformer/progress.py` | Load and save completed level ids | nothing |
| `platformer/session.py` | State machine; owns the frame sink | all of the above |
| `platformer/app.py` | Tk window: key capture, 20 Hz timer, `FramePump` | `session`, `display` |

The package is named `platformer`, not `platform`, so that it can never be
confused with the standard library module of that name.

Nothing below `session.py` knows a display exists. `PlatformSession` takes the
same `Sink = Callable[[bytes], None]` that `LifeSession` does, so it can be
driven by a recording function in tests and by a `FramePump` in the app,
without either knowing about the other.

## Level format

A level is a list of equal-length strings, 16 rows tall:

```
.  empty          ^  spike           -  horizontal mover track
=  solid          G  goal            |  vertical mover track
@  spawn          i  ice             E  enemy
o  coin           b  bounce pad      p  portal (in pairs)
c  crumbling      <  belt, pushes left    >  belt, pushes right
```

The moving parts are static descriptions of movement. A mover's track is the
run of `-` or `|` it slides along; an enemy's patrol is worked out once, when
the level is parsed, from the ledge it starts on. Where each one *is* at any
moment is a pure function of the tick, so a level has a **period** — how long
until everything is back where it started — a world can be rewound by
rewinding its clock, and the solver can treat time as one more coordinate
instead of modelling a simulation inside its search.

Two enemies in pens of different lengths gave one level a period of 2184,
which multiplied the search past reach. Matching the pens brought it to 24. A
test now caps the period at 240.

`Level` rejects a map that is not 16 rows tall, has ragged rows, contains an
unknown character, or does not have exactly one spawn and one goal. Those are
programming errors in `levels.py`, not user input, so they raise at import.

The level edges are solid: walking into column -1 or past the last column
stops the player. Falling below row 15 kills.

## Physics

Positions and velocities are floats in cell units, advanced at 20 Hz and
floored to integers only when drawing.

| Constant | Value | Effect |
| --- | --- | --- |
| `GRAVITY` | 0.055 | ~3.6 cells of rise from a full jump |
| `JUMP_VELOCITY` | -0.66 | apex after 12 ticks, a little over half a second |
| `CUT_JUMP_VELOCITY` | -0.34 | releasing Up early gives ~1.5 cells |
| `RUN_SPEED` | 0.22 | ~4.4 cells a second |
| `ACCELERATION` | 0.11 | full speed in two ticks |
| `FRICTION` | 0.11 | stop in two ticks |
| `MAX_FALL_SPEED` | 0.85 | under one cell a tick |
| `COYOTE_TICKS` | 3 | jump still works just after leaving a ledge |
| `BUFFER_TICKS` | 4 | jump pressed just before landing is remembered |
| `BOUNCE_VELOCITY` | -0.85 | a pad throws you ~6 cells, well past a jump |
| `ICE_ACCELERATION` / `ICE_FRICTION` | 0.03 / 0.015 | ice barely grips |
| `CONVEYOR_SPEED` | 0.12 | about half a run, so a belt can be walked against |
| `MOVER_TICKS` / `ENEMY_TICKS` | 6 | one whole cell per six ticks |

`MAX_FALL_SPEED` being below 1.0 is load-bearing: a faster fall could move the
player from above a one-cell floor to below it in a single tick without ever
overlapping it, and they would drop through the world.

Horizontal and vertical movement are resolved in separate passes — move in x
and push out of anything hit, then move in y and push out again. Doing both at
once makes a player moving diagonally into a corner pick the wrong axis to
resolve and either stick or pass through.

Contact is measured by distance, not by overlap: a coin or the goal is taken
within 0.8 of a cell, a spike kills only within 0.6. Spikes being the tighter
of the two is deliberate -- brushing one should be survivable and walking
into one should not.

Coyote time and jump buffering are not polish. On a screen 16 pixels tall a
jump missed by one tick is a death, and without them the game reads as broken
rather than hard.

These are not the values a continuous formula suggests. Integrating in
discrete ticks loses height to the first tick of gravity, so the -0.62 that
should give 3.5 cells actually gives 3.19 -- close enough to a three-cell
ledge to make it a coin flip. The constants above are the ones the tests
measure, not the ones the algebra predicts.

The reachable envelope that follows from these numbers: about 3.6 cells of
height, and about 5 cells of gap cleared from a running start. Levels are
built to gaps of at most 3 and ledges of at most 3, which leaves margin for a
player who is not frame-perfect.

## Camera

`window_x` centres the 16-wide window on the player and clamps it to the
level, so the first and last screens do not scroll past the ends. Levels are
exactly 16 rows tall, so there is no vertical camera.

## Screens

**Menu.** `PLAY` and `LVLS` in a four-row, variable-width font. Three pixels
is as narrow as a letter can be and still be read — at two, `A` has nowhere to
put its crossbar and `V` and `Y` collapse into the same shape — so the width
comes down by letting `L` be two columns wide rather than by shrinking every
glyph past legibility. `PLAY` is 14x4 rather than 15x5, which leaves a margin
and a spare column for a white marker beside the chosen entry. Up and Down
move; Enter, Space or Right chooses.

**Level picker.** One pixel per level, eight to a row, every other column and
row: green for completed, dim blue for not, a white pulse for the cursor, and
the number of the selected level below the grid. It holds forty. The 3x3 tiles
this replaced were readable at twelve levels and ran out of panel well before
twenty-seven.

**Play.** The camera window, drawn back to front: platforms, spikes, coins,
goal, player. The goal is dim grey until the last coin is taken, then flashing
green.

**Death and completion.** Death flashes the panel red for a few ticks and
restarts the level from its spawn — there is no lives counter and nothing to
lose but the attempt. Completion flashes green, records the level id, and
advances to the next level, or returns to the menu after the last one.

## Progress

Completed level ids are stored in
`~/.config/pi-menu/platform-progress.json` as `{"completed": [...]}`. Ids
are strings from `levels.py`, not indexes, so reordering or inserting a level
does not silently mark the wrong one done.

Every level is always playable. A missing, unreadable or corrupt file means
"nothing completed yet" and is not an error: the file exists to colour the
picker, and refusing to start a game over it would be absurd.

## Key handling

X11 auto-repeat delivers a `KeyRelease` immediately followed by a `KeyPress`
while a key is held down. Read naively that says the player is letting go of
the arrow key several times a second. `app.py` keeps a set of held keys and
defers each release by one tick, cancelling it if the matching press arrives
first.

## Testing

Physics, levels, rendering and the state machine are all reachable without a
window or a panel.

- `test_platform_level.py` — parsing, tile lookup, and every malformed map
  rejected.
- `test_platform_world.py` — gravity, landing, walls, coyote and buffer
  windows, jump cut, coin pickup opening the goal, spikes and falls killing.
- `test_platform_render.py` — glyphs land where expected, camera clamps at
  both ends, each tile gets its colour.
- `test_platform_session.py` — every transition pushes a frame, in the shape
  the Life session tests use, plus one run driven through the real firmware
  over a pseudo-terminal.
- `test_platform_levels.py` — a best-first search over the real physics with
  quantised state, asserting that a winning sequence of key presses exists for
  every one of the twenty-seven levels. This is the test that makes the level
  set trustworthy: hand-drawn maps are easy to get subtly wrong, and a level
  whose last coin sits one cell too high is unwinnable in a way no amount of
  reading the ASCII will reveal. It has caught five so far.

  Two things about the search are load-bearing. Its state key carries the
  world's clock, the crumbled tiles and the portal latch, because once
  platforms slide, standing in one place at two different moments is two
  different situations. And it scores states by a flood fill over open ground
  rather than by straight-line distance: guided by the latter it walks up to
  the wall in `two-doors` and mills about, because the far side is close in a
  way it cannot use. That change alone took the level from 15.5s to 0.1s.

## Wiring up

`apps.json` gains an entry, `pyproject.toml` a `pi-platformer` script,
`install.sh` a command and a desktop entry (with its test's expected list
updated), `README.md` a table row and a section, and
`tests/test_app_entrypoints.py` the new module.
