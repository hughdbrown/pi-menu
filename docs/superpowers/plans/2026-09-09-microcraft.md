# MicroCraft Port Plan

**Goal:** Port `MicroCraft — 16×16.html` — a two-layer, looping, block-building
world with fluids, fire, grass, weather, a day/night sky, an inventory and two
crafting benches — to a `pi-microcraft` app in the Pi Menu framework, drawn on
the 16×16 Stellar Unicorn and driven from the keyboard.

**Source:** the HTML file at the repo root (≈3,900 lines of JavaScript in one
IIFE, five embedded PNG sprite sheets). It stays in the repo as the reference;
nothing at runtime reads it.

**Architecture:** a new `src/pi_menu/microcraft/` package laid out the way
`pi_menu.platformer` is: pure Python for the world, simulation, inventory and
rendering; a `Session` state machine that takes a frame *sink*; and a thin Tk
shell that holds the keyboard, runs a 20 Hz clock and reports status in words.
Frames reach the panel through the existing `FramePump`, and the terminal
preview works with no hardware, as it does for the other apps.

**Tech stack:** Python 3.9+, tkinter, pytest. No new dependencies. Pillow is
already a dependency and is used only by the sprite-sheet extraction tool.

---

## 1. What the HTML does (review)

| Area | In the HTML | Notes for the port |
| --- | --- | --- |
| Screen | 16×16 canvas, 2×2 px per block, so an 8×8 block view | Same. One LED per canvas pixel. |
| World | Looping strip 2000 blocks around (`wrapX`), 1250 rows deep, front + background layer, 32-wide chunks generated on demand from hashed value noise and never evicted | Same numbers. Chunks as `bytearray` rows. |
| Terrain | Rolling hills + sharp mountains, a continent mask giving oceans, inland lakes wherever land dips below sea level, sand/clay beds, tree cells, ore and a lava-rich core | Pure functions of `(x, seed)`; ported exactly, including the 32-bit `Math.imul` hash. |
| Fluids | Water/lava sources and 7 flow tiles each, spreading, tapering, falling, receding; two sources make a new source | Same rules. Scan a 65×65 box, not 65×1250 columns (see §3). |
| Fire | Flammables next to lava ignite, burn 30 ticks, water puts them out, clay next to fire bakes to brick, a stick tapped 5× lights one | Same. |
| Grass | Spreads to sunlit dirt, dies under cover after 24 ticks, never above the grass line | Same. |
| Sky | Real-time 40-minute day, position on the loop shifts local time like time zones, keyframed gradient, sunrise glow, sun disc, moon with real synodic phase drawn as a 5-pixel plus, stars, total eclipse near new moon | Same. Alpha blending done by a small software canvas. |
| Weather | Particle-swarm clouds of three types, mini wisps, constant wind, cover/rain intensity per column, overcast tint, rain drops in a 32×32 box, lightning flash + bolts, ocean waves whose height follows depth and weather, swimmable crests | Same, with particle updates limited to clouds near the camera. |
| Player | 1-block box, per-frame physics at 60 Hz (`GRAV .02, MOVE .08, JUMP .32`), edge-accurate collision, buoyancy, swim stroke, pixel snap after 1 s idle, falling through the core comes out at the antipode | Physics constants kept; run three 60 Hz substeps per 20 Hz tick. |
| Cursor | 1-pixel reticle moved by arrows, drawn with `difference` compositing | Same; drawn by inverting the pixel under it. |
| Inventory | 8 hotbar + 32 backpack slots, stacks of 16 (tools/buckets 1), select/move/swap/merge, double-tap to arm a split, quantity dots, item drops that fall and bob and are picked up on contact | Same. |
| Crafting | 2×2 bench from the inventory screen; 3×3 table opened from a placed crafting table; recipes: log→4 planks, 2 planks→4 sticks, 4 planks→table, 3 stone tools; output slot crafts on pick-up; leftovers returned or dropped on close | Same. |
| Breaking/placing | Hold Backspace to break with per-block times and axe/pickaxe multipliers, crack overlay; Enter places, pours/scoops buckets, or opens a table | Same. |
| Opening screen | Grey panel + play button over a live demo tour of twelve shots (ground, underground, clouds, timelapse, eclipse) | Same. |
| HUD | HTML text: hp, held block, layer | Goes in the Tk status line. HP is never changed by the game; shown anyway. |
| Touch controls | On-screen buttons | Dropped: the Pi has a keyboard. |

## 2. Keys

The HTML's desktop layout, kept as is so the help text carries across:

| Key | Does |
| --- | --- |
| A / D | walk |
| W / Space | jump, or swim up |
| Arrows | move the cursor one pixel (auto-repeat welcome) |
| Enter | place / interact / "click" a slot or button under the cursor |
| Backspace (held) | break the block under the cursor |
| 1–8 | choose a hotbar slot |
| E or I | open / close the inventory |
| L | target the front or the background layer |
| Q ×3 quickly | drop one of the held item at the cursor |
| Esc | close a screen; from the world, back to the opening screen |
| C | save the panel as a PNG (framework convention) |

## 3. Deliberate deviations

- **Simulation boxes are bounded vertically.** The JS scans full 1,250-row
  columns for fluids, fire and grass every tick. Python cannot afford 160k
  cell reads five times a second, so the box is ±32 columns *and* ±32 rows
  around the player. Nothing outside the panel's neighbourhood was visible
  anyway.
- **Cloud particles move only near the camera.** Every cloud still drifts on
  the wind and still counts for cover and rain; only clouds within 40 blocks
  of the camera get their per-particle wobble integrated. Off-screen swarms
  frozen in shape are indistinguishable from moving ones.
- **Fixed tick.** 20 Hz session tick with `dt = 50 ms`; player physics runs
  three substeps per tick so the 60 Hz constants keep their feel. Everything
  that used `frameDt` (break progress, fluid/grass/weather accumulators,
  rain, lightning decay) takes the tick's dt.
- **Injected clock and RNG.** `Session(clock=, rng=)` so tests are
  deterministic; the app passes `time.monotonic` and a fresh `random.Random`.
  A `--seed` flag pins the world for screenshots.
- **Esc from the world returns to the opening screen** (the HTML has no way
  back). The world is kept; Play resumes it.
- **No persistence**, same as the HTML.

## 4. Package layout

```
src/pi_menu/microcraft/
  __init__.py
  tiles.py       ids, names, sets, fluid metadata, break times, tool multipliers
  sprites.py     the five sheets as tuples of RGB rows (transcribed, with alpha), average colours
  noise.py       hash2 / hash1 / noise1d with 32-bit imul semantics; wrap_x
  terrain.py     heights, oceans, trees, chunk generation, World (layers, get/set)
  sim.py         fluids, fire, grass, stick ignition
  sky.py         day fraction, moon phase, sky colours, sun/moon/stars/eclipse
  weather.py     clouds, cover/rain queries, rain drops, lightning, waves
  inventory.py   Stack, Inventory (hotbar/backpack/bench/table), recipes, slot clicks
  player.py      Player physics, breaking, placing, item drops
  canvas.py      16×16 RGB canvas: blend, rect, radial/linear gradients, invert, to bytes
  render.py      world, hotbar, inventory, bench, table, opening menu, cursor
  demo.py        the opening-screen shot list and camera
  session.py     Session: screens, keys, tick(dt), framebuffer(), status_text()
  app.py         Tk shell, argparse, main()
tools/extract_microcraft_sprites.py   regenerates sprites.py from the HTML
tests/test_microcraft_*.py
```

Registration: `pyproject.toml` script `pi-microcraft`, `apps.json` entry,
`install.sh` COMMANDS/DESKTOP_FILES, README table and section.

## 5. Order of work

Each task: tests first where the behaviour is pure, `pytest -q`, commit.

- [x] **Task 1 — sprites and tiles.** `tools/extract_microcraft_sprites.py`
  decodes the base64 PNGs and writes `sprites.py`; `tiles.py` carries every
  id/name/set from the HTML. Tests: every tile and item has a sprite and a
  name; fluids/items/tools sets are disjoint where they should be.
  Commit: `feat(microcraft): tiles and the sprite sheets`.
- [x] **Task 2 — noise and terrain.** `noise.py`, `terrain.py` with `World`.
  Tests: `hash2` is deterministic and in `[0,1)`; `wrap_x` folds both ends;
  `front_height` is stable under wrapping; a flooded column has water from
  sea level to the bed and sand/clay beneath; trees never stand in water or
  above the tree line; `find_spawn_x` lands on dry land; set/get round-trips
  across a chunk edge; below the world is stone, above is sky.
  Commit: `feat(microcraft): a looping world generated on demand`.
- [x] **Task 3 — simulation.** `sim.py`. Tests: a water source over air
  drips a falling tile; a source on a shelf tapers R1, R2, R3 and stops;
  removing the source recedes the flow; two sources make a third; a plank
  beside lava burns away in 30 ticks; water beside a burning plank saves it;
  clay beside fire becomes brick; sunlit dirt beside grass greens (rng
  pinned); covered grass dies after 24 ticks.
  Commit: `feat(microcraft): water, lava, fire and grass`.
- [x] **Task 4 — canvas and sky.** `canvas.py`, `sky.py`. Tests: blending a
  half-alpha white over black gives grey; invert flips; the sky at noon is
  blue, at midnight near black; the moon plus has 5 lit pixels at full and
  0 at new; an eclipse draws a dark centre with a corona.
  Commit: `feat(microcraft): a blending canvas and the sky`.
- [x] **Task 5 — weather.** `weather.py`. Tests: clouds seed without
  overlap; a cloud drifting out of range is recycled behind the leftmost;
  cover under a cumulonimbus is higher than under cumulus; rain only spawns
  under raining clouds and respects the per-column cap; a drop lands on the
  first solid row; lightning only from cumulonimbus; wave height is 0 in a
  shallow pond and > 0 in deep ocean.
  Commit: `feat(microcraft): clouds, rain, lightning and waves`.
- [x] **Task 6 — inventory and crafting.** `inventory.py`. Tests: pick-up
  fills partial stacks before empty slots; tools stack to one; select/move/
  swap/merge with overflow; double-tap arms a split and the split halves;
  each recipe on the bench and, shifted, on the table; the stone tool
  patterns incl. both axe hands; output crafts once and consumes then;
  closing a bench returns leftovers.
  Commit: `feat(microcraft): the inventory and both crafting benches`.
- [x] **Task 7 — player.** `player.py`. Tests: falls to the ground and
  stops flush; a wall stops walking; jump rises and lands; water is
  buoyant and W swims up; the core teleports to the antipode; breaking
  takes the tabled time, faster with the right tool; a placed block
  decrements the stack; can't place inside the player; buckets scoop and
  pour; drops fall, land, bob, and are picked up after the grace period.
  Commit: `feat(microcraft): a player who walks, swims, digs and builds`.
- [x] **Task 8 — rendering.** `render.py`. Tests: frames are 768 bytes;
  the front layer is drawn over the darkened background; the hotbar sits on
  the bottom row with the selected slot blinking white; the inventory
  screen has the exit tile at (14,0); the bench and table layouts match
  their hit tests; the opening panel is grey with the play button at
  (4..11, 5..7); the cursor inverts its pixel.
  Commit: `feat(microcraft): paint the world and the screens`.
- [x] **Task 9 — demo and session.** `demo.py`, `session.py`. Tests: opens
  on the menu; Enter on the play button starts play, elsewhere does not;
  E opens and closes the inventory; the bench opens from the inventory
  button and the table from a placed table; Esc closes each; every
  transition pushes a frame; ticks advance fluids on schedule; status text
  names the held stack and layer.
  Commit: `feat(microcraft): one state machine for every screen`.
- [x] **Task 10 — app, registration, docs.** `app.py`, `pyproject.toml`,
  `apps.json`, `install.sh`, README. Tests: entry-point smoke tests join the
  parametrised lists; `--list` names MicroCraft; install script tests cover
  the new desktop file.
  Commit: `feat(microcraft): put MicroCraft on the menu`.
- [x] **Task 11 — review pass.** Run the whole suite, time a tick on this
  machine, read the code once more for anything the port lost.

## 6. Performance budget

Measured on the dev Mac (Python 3.14) once the port was complete: a world
tick including the frame is 1–3 ms, a fluid tick 0.7–1.5 ms with a lake in
the box, cloud drawing about 1 ms for a storm centred on screen, a fresh
chunk 14 ms, start-up 60 ms. All inside the targets below.

### Added during the port

- **`palette.py`.** The user pointed out mid-port that the target is the
  Stellar Unicorn's LEDs, whose gamma makes anything under about 40 read as
  off, and that at two LEDs a block the HTML's greys were indistinguishable.
  Every block and item now has its own two-tone pattern lifted above the
  floor and given a hue no neighbour shares; a test asserts pairwise
  separation. Layout and behaviour are unchanged.
- **`tools/extract_microcraft_sprites.py`** regenerates `sprites.py` from the
  HTML's embedded PNGs; the palette overrides are applied on top at import.

A tick has 50 ms. Targets measured with `python -m timeit` on the dev Mac,
which is faster than a Pi 4 by roughly 3×, so aim for ≤ 12 ms here:

- render a world frame (two layers, waves, clouds, rain): ≤ 6 ms
- fluid + fire tick over the 65×65 box: ≤ 4 ms (every 220 ms)
- grass tick: ≤ 3 ms (every 500 ms)
- weather motion for on-camera clouds: ≤ 2 ms
- a fresh chunk: ≤ 40 ms, paid once per 32 blocks of travel
