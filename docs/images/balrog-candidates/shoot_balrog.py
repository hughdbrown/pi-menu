"""Eight staged frames of the balrog fight, player pinned in the arena.

A photography rig, not a playthrough: the player is held at a chosen
spot and kept alive, so the camera stays where the demon is and every
attack happens on screen.
"""
import sys
from pathlib import Path

ROOT = Path("/Users/hughbrown/workspace/tyler/pi-menu")
sys.path.insert(0, str(ROOT / "src"))

from pi_menu.capture import to_image
from pi_menu.display.protocol import pixel_offset, HEIGHT, WIDTH
from pi_menu.platformer import bosses, render
from pi_menu.platformer.levels import LEVELS
from pi_menu.platformer.world import World

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
level = next(l for l in LEVELS if l.id == "the-balrog")

def fresh(x):
    w = World(level)
    w.x, w.y = float(x), 13.0
    w.step(frozenset())  # arms the fight (x is past the arena line)
    return w

def run(w, x, until, limit=800):
    for _ in range(limit):
        w.step(frozenset())
        w.alive = True          # the rig: nothing may end the shoot
        w.x, w.y = float(x), 13.0
        w.on_ground = True
        if until(w):
            return True
    return False

def save(name, w, phase=None):
    frame = render.draw_world(w, phase=phase if phase is not None else w.tick)
    to_image(frame).save(OUT / f"balrog-{name}.png")
    print(f"saved {name:22} boss_tick={w.boss_tick}")

# 1: the demon at rest, eyes lit, before anything is thrown.
w = fresh(54); run(w, 54, lambda w: w.boss_tick == 4)
save("1-the-demon", w, phase=0)

# 2: mouth lit, fireball just leaving.
w = fresh(54); run(w, 54, lambda w: any(x > 50 for x, _ in w.fireball_cells()))
save("2-breathing-fire", w)

# 3: fireball mid-flight towards the player.
w = fresh(52); run(w, 52, lambda w: any(44 < x < 50 for x, _ in w.fireball_cells()))
save("3-incoming", w)

# 4: the fist high above the player, about to fall.
w = fresh(52); run(w, 52, lambda w: w.fist_cells() and min(y for _, y in w.fist_cells()) <= 1)
save("4-fist-raised", w)

# 5: the fist buried beside the player. Column 48 has open sky -- at 52
# a platform overhead catches the fist before it reaches the ground.
w = fresh(48); run(w, 48, lambda w: w.fist_cells() and max(y for _, y in w.fist_cells()) >= 13)
save("5-fist-down", w)

# 6: right under the demon.
w = fresh(56); run(w, 56, lambda w: bool(w.fist_cells()) and w.boss_tick > 40)
save("6-under-the-demon", w)

# 7: the last wave, fist and fireball together.
late = bosses.BALROG.duration - bosses.BALROG.waves[-1].ticks
w = fresh(54); run(w, 54, lambda w: w.boss_tick and w.boss_tick > late
                   and w.fist_cells() and w.fireball_cells())
save("7-final-wave", w)

# 8: the fight survived -- demon gone, goal flashing open.
w = fresh(52); run(w, 52, lambda w: w.boss_done)
w.coins = frozenset()  # the goal only opens with the coins taken too
w.x, w.y = 65.0, 13.0
w.step(frozenset()); w.alive = True; w.x, w.y = 65.0, 13.0
save("8-goal-open", w, phase=0)
