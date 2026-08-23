# Platform Game Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a side-scrolling platform game to Pi Menu, played with the arrow keys and drawn entirely on the 16x16 Stellar Unicorn.

**Architecture:** A new `src/pi_menu/platformer/` package split the way `pi_menu.life` is: pure Python for the level format, physics, camera, rendering, progress and the screen state machine, with a thin Tk shell that only captures keys and runs a 20 Hz timer. Frames reach the panel through the existing `FramePump`.

**Tech Stack:** Python 3.9+, tkinter, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-22-platformer-design.md` — it carries the physics constants, the level glyphs, the screen layouts and the reasoning. This plan gives the order of work and the test names; the spec is the reference for behaviour and is not repeated here.

**Note on the code in this plan:** implementation bodies are described rather than transcribed, because the spec already pins the constants and the behaviour, and a second copy of them would be one more thing to drift. Test names and file paths are exact.

---

## Chunk 1: Pure logic, no rendering

### Task 1: The level format

**Files:**
- Create: `src/pi_menu/platformer/__init__.py`, `src/pi_menu/platformer/level.py`
- Test: `tests/test_platform_level.py`

- [ ] **Step 1: Write the failing tests** — `test_a_level_knows_its_size`, `test_solid_tiles_are_solid_and_gaps_are_not`, `test_off_the_sides_is_solid_and_below_the_floor_is_not`, `test_the_spawn_and_goal_are_found`, `test_coins_and_spikes_are_listed`, and one rejection test per malformed map: ragged rows, wrong height, unknown glyph, no spawn, two spawns, no goal.
- [ ] **Step 2: Run and watch them fail** — `python -m pytest tests/test_platform_level.py -q`
- [ ] **Step 3: Implement `Level`** — parse a list of equal-length strings; `solid(x, y)` true for `=` and for x outside the level, false below the floor (falling out is death, not a wall); `coins`, `spikes` as frozensets of `(x, y)`; `spawn`, `goal` as single points; `LevelError` for every malformed map.
- [ ] **Step 4: Run the tests** — all pass
- [ ] **Step 5: Commit** — `feat(platformer): read levels from ASCII maps`

### Task 2: The camera

**Files:**
- Create: `src/pi_menu/platformer/camera.py`
- Test: `tests/test_platform_camera.py`

- [ ] **Step 1: Write the failing tests** — `test_the_window_centres_on_the_player`, `test_the_window_stops_at_the_left_edge`, `test_the_window_stops_at_the_right_edge`, `test_a_level_no_wider_than_the_panel_never_scrolls`.
- [ ] **Step 2: Run and watch them fail**
- [ ] **Step 3: Implement `window_x(player_x, level_width)`** — centre, then clamp to `0 .. level_width - 16`, and to 0 when the level is not wider than the panel.
- [ ] **Step 4: Run the tests**
- [ ] **Step 5: Commit** — `feat(platformer): follow the player with a clamped camera`

### Task 3: Physics and the world

**Files:**
- Create: `src/pi_menu/platformer/world.py`
- Test: `tests/test_platform_world.py`

- [ ] **Step 1: Write the failing tests** — a player left in the air falls and accelerates; a fall stops on a platform; falling never exceeds `MAX_FALL_SPEED`; holding left and right moves and stops; a wall stops horizontal movement without stopping the fall; a jump from the ground rises about 3.5 cells; releasing Up early gives about 1.5; a jump within `COYOTE_TICKS` of leaving a ledge still works and one after does not; a jump pressed within `BUFFER_TICKS` before landing fires on landing; touching a coin removes it; the goal is shut until the last coin is taken; a spike kills; falling below the floor kills; reaching an open goal wins; and `test_a_fast_fall_cannot_pass_through_a_one_cell_floor`.
- [ ] **Step 2: Run and watch them fail**
- [ ] **Step 3: Implement `World`** — float position and velocity in cell units; `step(held)` returning an `Event` (`NONE`, `COIN`, `DIED`, `WON`); x and y resolved in separate passes; the constants from the spec.
- [ ] **Step 4: Run the tests**
- [ ] **Step 5: Commit** — `feat(platformer): give the player weight and a jump`

### Task 4: The twelve levels

**Files:**
- Create: `src/pi_menu/platformer/levels.py`
- Test: `tests/test_platform_levels.py`

- [ ] **Step 1: Write the failing tests** — `test_there_are_at_least_ten_levels`, `test_every_level_parses`, `test_every_level_id_is_unique`, `test_every_level_has_at_least_one_coin`, `test_no_level_starts_the_player_inside_a_wall`.
- [ ] **Step 2: Run and watch them fail**
- [ ] **Step 3: Draw the levels** — twelve maps, 16 rows tall, 32 to 64 columns wide, each introducing one idea: walking and a first gap; a climb; spikes on the floor; a spike gap; a descent; a ceiling to duck under; a coin that needs a full-height jump; staircases; a spike corridor; a tower; a long run with everything; a finale.
- [ ] **Step 4: Run the tests**
- [ ] **Step 5: Commit** — `feat(platformer): draw twelve levels`

### Task 5: Prove the levels are completable

**Files:**
- Create: `tests/platform_solver.py`
- Modify: `tests/test_platform_levels.py`

- [ ] **Step 1: Write the failing test** — `test_every_coin_and_the_goal_can_be_reached`, parametrised over all twelve levels.
- [ ] **Step 2: Run and watch it fail**
- [ ] **Step 3: Implement the solver** — breadth-first search over the real `World.step`, with state quantised to a fraction of a cell so the search terminates, a small input alphabet (left, right, neither, each with and without Up), and a node cap. It returns the set of reachable coins and whether the goal is reachable once they are all taken.
- [ ] **Step 4: Run the tests** — fix any level the solver cannot finish, rather than weakening the solver.
- [ ] **Step 5: Commit** — `test(platformer): search each level for a way through`

---

## Chunk 2: What the panel shows

### Task 6: The 3x5 font

**Files:**
- Create: `src/pi_menu/platformer/font.py`
- Test: `tests/test_platform_font.py`

- [ ] **Step 1: Write the failing tests** — every glyph is 5 rows of 3 columns; the menu words and all ten digits have glyphs; `text_width` accounts for the one-pixel gaps; `PLAY` is exactly 15 pixels wide, the panel's width less one.
- [ ] **Step 2: Run and watch them fail**
- [ ] **Step 3: Implement the font** — glyphs as tuples of row strings, plus `text_width` and an iterator over lit pixels.
- [ ] **Step 4: Run the tests**
- [ ] **Step 5: Commit** — `feat(platformer): add a 3x5 font for the panel`

### Task 7: Rendering

**Files:**
- Create: `src/pi_menu/platformer/render.py`
- Test: `tests/test_platform_render.py`

- [ ] **Step 1: Write the failing tests** — the world draws platforms, coins, spikes, the goal and the player in their own colours; the player is drawn over everything; the camera offset is applied; a shut goal and an open goal differ; the menu lights the selected entry brighter; the picker colours completed and uncompleted tiles differently and marks the cursor; the picker shows the level number; a flash fills the panel.
- [ ] **Step 2: Run and watch them fail**
- [ ] **Step 3: Implement the painters** — `draw_world`, `draw_menu`, `draw_picker`, `flash`, each returning `FRAME_BYTES` bytes.
- [ ] **Step 4: Run the tests**
- [ ] **Step 5: Commit** — `feat(platformer): paint the game onto a frame`

### Task 8: Remembering progress

**Files:**
- Create: `src/pi_menu/platformer/progress.py`
- Test: `tests/test_platform_progress.py`

- [ ] **Step 1: Write the failing tests** — a round trip; a missing file reads as nothing completed; a corrupt file reads as nothing completed and does not raise; an unwritable directory does not raise; completing twice does not duplicate.
- [ ] **Step 2: Run and watch them fail**
- [ ] **Step 3: Implement `Progress`** — `load()`, `mark(level_id)`, `completed`, saving to `~/.config/pi-menu/platform-progress.json`, honouring `PI_MENU_CONFIG_DIR` so tests do not touch the real home directory.
- [ ] **Step 4: Run the tests**
- [ ] **Step 5: Commit** — `feat(platformer): remember which levels are finished`

---

## Chunk 3: The game and the window

### Task 9: The state machine

**Files:**
- Create: `src/pi_menu/platformer/session.py`
- Test: `tests/test_platform_session.py`

- [ ] **Step 1: Write the failing tests** — opening the session pushes a menu frame; Down then Enter on the menu opens the picker; Enter on `PLAY` starts level one; arrows move the picker cursor and clamp at the grid edges; Escape returns to the menu; a tick while playing pushes a frame; dying flashes and restarts at the spawn with the coins back; winning flashes, records the level and advances; winning the last level returns to the menu; and the Life-session pattern — every control pushes exactly one frame.
- [ ] **Step 2: Run and watch them fail**
- [ ] **Step 3: Implement `PlatformSession`** — states `MENU`, `PICKER`, `PLAY`, `DEAD`, `WON`; `press(key)`, `release(key)`, `tick()`, `framebuffer()`, `status_text()`; takes a `Sink` and a `Progress`.
- [ ] **Step 4: Run the tests**
- [ ] **Step 5: Commit** — `feat(platformer): drive the screens from one state machine`

### Task 10: Through the real firmware

**Files:**
- Modify: `tests/test_platform_session.py`

- [ ] **Step 1: Write the failing test** — `test_a_frame_survives_the_trip_to_the_pico`, using the `pico` fixture from `tests/conftest.py` as `test_life_session.py` does: play a few ticks through a `SerialDisplay` and assert the firmware's fake graphics show the player pixel.
- [ ] **Step 2: Run and watch it fail**
- [ ] **Step 3: Make it pass**
- [ ] **Step 4: Run the tests**
- [ ] **Step 5: Commit** — `test(platformer): drive the panel through the real firmware`

### Task 11: The Tk window

**Files:**
- Create: `src/pi_menu/platformer/app.py`
- Modify: `tests/test_app_entrypoints.py`

- [ ] **Step 1: Write the failing tests** — add `pi_menu.platformer.app` to `MODULES`, and add `test_a_deferred_release_is_cancelled_by_a_repeat_press` against the key-holding helper, which is a plain class with no Tk in it.
- [ ] **Step 2: Run and watch them fail**
- [ ] **Step 3: Implement the app** — a `HeldKeys` helper holding the auto-repeat rule, a Tk window with the status line and a Quit button, key bindings, a 20 Hz timer, and `main()` with the shared display arguments.
- [ ] **Step 4: Run the tests**
- [ ] **Step 5: Commit** — `feat(platformer): hold the keyboard and run the clock`

### Task 12: Wiring it in

**Files:**
- Modify: `src/pi_menu/apps.json`, `pyproject.toml`, `install.sh`, `README.md`
- Test: `tests/test_install_script.py`, `tests/test_app_entrypoints.py`

- [ ] **Step 1: Write the failing tests** — the install script writes `pi-platformer.desktop`; `pi-menu --list` names the platform game.
- [ ] **Step 2: Run and watch them fail**
- [ ] **Step 3: Wire it up** — the `apps.json` entry, the `pi-platformer` script, the install script's command list and desktop entry, and the README table row and section.
- [ ] **Step 4: Run the whole suite**
- [ ] **Step 5: Commit** — `feat(platformer): put the game on the menu`
