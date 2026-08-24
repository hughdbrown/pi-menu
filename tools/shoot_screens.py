#!/usr/bin/env python3
"""Photograph the game for the README, by playing it.

Runs the shipped auto-play routes headlessly and saves the frames worth
looking at -- the menu, the picker, mid-jump moments, a boss mid-swing.
Every image this produces is a genuine frame the panel would have
shown, captured through the same code the C key uses in the app.

    python3 tools/shoot_screens.py [output-dir]    # default docs/images
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pi_menu.capture import to_image  # noqa: E402
from pi_menu.platformer import render  # noqa: E402
from pi_menu.platformer.autopilot import Autopilot  # noqa: E402
from pi_menu.platformer.levels import LEVELS  # noqa: E402
from pi_menu.platformer.routes import ROUTES  # noqa: E402
from pi_menu.platformer.world import World  # noqa: E402

BY_ID = {level.id: level for level in LEVELS}


def play(level_id: str, until):
    """Auto-play a level until ``until(world)`` is true; return the world."""
    world = World(BY_ID[level_id])
    pilot = Autopilot(ROUTES[level_id])
    for _ in range(len(ROUTES[level_id]) * 2 + 10):
        world.step(pilot.held())
        pilot.advance()
        if until(world):
            return world
    return world


def best_boss_frame(level_id: str) -> bytes:
    """The playthrough frame that shows the most demon and the most fight.

    The route dodges wherever the fight pushes it, so no single stop
    condition reliably has the demon on camera. Playing the whole level
    and scoring every frame does.
    """
    from pi_menu.display.protocol import HEIGHT, WIDTH, pixel_offset
    from pi_menu.platformer.camera import window_x

    level = BY_ID[level_id]
    demon = set(render.DEMON_BODY.values())
    loud = {render.FIST, render.FIREBALL}
    best, best_score = None, -1.0

    world = World(level)
    pilot = Autopilot(ROUTES[level_id])
    for _ in range(len(ROUTES[level_id]) * 2 + 10):
        world.step(pilot.held())
        pilot.advance()
        if world.won:
            break
        if world.boss_tick is None or world.boss_done:
            continue
        frame = render.draw_world(world, phase=world.tick)
        colours = [
            tuple(frame[pixel_offset(x, y) : pixel_offset(x, y) + 3])
            for y in range(HEIGHT)
            for x in range(WIDTH)
        ]
        demon_pixels = sum(colour in demon for colour in colours)
        attack_pixels = sum(colour in loud for colour in colours)
        score = demon_pixels + 4 * min(attack_pixels, 8)
        if score > best_score:
            best, best_score = frame, score
    return best


def shoot(directory: Path) -> list:
    shots = []

    def save(name, frame):
        path = directory / f"{name}.png"
        to_image(frame).save(path)
        shots.append(path)
        print(f"  {path}")

    save("menu", render.draw_menu(selected=0, phase=0))
    save("picker", render.draw_picker(index=21, completed=set(range(14)), count=len(LEVELS), phase=0))

    world = play("first-steps", lambda w: w.vy < -0.3 and w.x > 5)
    save("first-jump", render.draw_world(world, phase=world.tick))

    world = play("moving-day", lambda w: w.on_ground and any(w.mover_cells()) and w.x > 12)
    save("riding-the-ferry", render.draw_world(world, phase=world.tick))

    world = play("the-spire", lambda w: w.y < 12)
    save("up-the-spire", render.draw_world(world, phase=world.tick))

    world = play("conveyor-belt", lambda w: w.x > 8)
    save("conveyor", render.draw_world(world, phase=world.tick))

    save("the-balrog", best_boss_frame("the-balrog"))

    return shots


def main() -> int:
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "images"
    directory.mkdir(parents=True, exist_ok=True)
    shots = shoot(directory)
    print(f"{len(shots)} screens shot")
    return 0


if __name__ == "__main__":
    sys.exit(main())
