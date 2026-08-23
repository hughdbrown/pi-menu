"""The sixty levels, as specs. ``build_levels.py`` paints them.

Each entry is a handful of lines: the floor with its pits punched out,
then where everything else goes. Runs are ``(row, x0, x1)``; vertical
runs are ``(column, y0, y1)``; everything else is a list of cells.

Rules the maps are drawn to, all of them measured rather than guessed:

* a flat gap of four is comfortable, five is the limit
* a ledge three cells up is reachable, four never is
* a three-cell rise buys only about three cells of horizontal reach
* a bounce pad throws you about six cells
* mover tracks need at least three cells, and nothing may be drawn on
  one -- a coin on a track splits it into two stubs
* enemy pens want matching lengths, or the level's period explodes
* at most four crumbling tiles, or the solver's search doubles per tile

The solver checks all of this by playing each level. Change a number
above and it is the levels, not the rule, that break.
"""

from __future__ import annotations

from build_levels import PANEL, ground

TALL = 32

SPECS = {}
BLURBS = {}


def level(name, blurb, **spec):
    SPECS[name] = spec
    BLURBS[name] = blurb
    return name


# ======================================================================
# 1-14: the ground floor. Everything here was drawn before the game had
# a third dimension to speak of.
# ======================================================================

level("first-steps", "Walk, hop for the high coin, and clear the gap.",
      width=32, solid=ground(32, gaps=[(16, 18)]) + [(11, 7, 9)],
      coins=[(8, 9), (13, 13), (23, 13)], spawn=(2, 13), goal=(29, 13))

level("up-we-go", "A staircase. Every coin is on the way up.",
      width=32,
      solid=ground(32) + [(12, 6, 8), (10, 11, 13), (8, 16, 18), (6, 21, 23), (4, 26, 30)],
      coins=[(7, 11), (12, 9), (17, 7), (22, 5)], spawn=(2, 13), goal=(28, 3))

level("mind-the-spikes", "Flat ground, but not empty ground.",
      width=36, solid=ground(36),
      spikes=[(9, 13), (16, 13), (17, 13), (25, 13)],
      coins=[(5, 13), (12, 13), (21, 13), (30, 13)], spawn=(2, 13), goal=(34, 13))

level("the-pit", "Three pits. The coins sit at the top of the arc.",
      width=36, solid=ground(36, gaps=[(8, 10), (17, 19), (26, 28)]),
      coins=[(9, 11), (18, 11), (27, 11)], spawn=(2, 13), goal=(34, 13))

level("down-and-out", "Start high and climb down. There is no way back up.",
      width=36,
      solid=ground(36, gaps=[(0, 18)]) + [(4, 0, 5), (7, 7, 11), (10, 13, 17)],
      coins=[(3, 3), (9, 6), (15, 9), (25, 13)], spawn=(2, 3), goal=(34, 13))

level("low-ceiling", "A tunnel you cannot jump in, and a roof you can walk on.",
      width=40, solid=ground(40) + [(12, 10, 20)],
      coins=[(13, 13), (17, 13), (15, 11), (33, 13)], spawn=(2, 13), goal=(37, 13))

level("the-tower", "Three columns, three cells apart, all the way up.",
      width=24,
      solid=ground(24) + [(12, 2, 6), (9, 9, 13), (6, 16, 21), (3, 9, 13)],
      coins=[(4, 11), (11, 8), (18, 5), (11, 2), (20, 13)],
      spawn=(1, 13), goal=(10, 2))

level("spike-corridor", "Take the spikes or take the high road.",
      width=40, solid=ground(40) + [(11, 9, 12), (11, 17, 20), (11, 25, 28)],
      spikes=[(10, 13), (11, 13), (18, 13), (19, 13), (26, 13), (27, 13)],
      coins=[(10, 10), (18, 10), (26, 10), (35, 13)], spawn=(2, 13), goal=(37, 13))

level("leap-of-faith", "Gap, island, gap, island.",
      width=44, solid=ground(44, gaps=[(8, 10), (15, 17), (22, 24), (29, 31)]),
      coins=[(9, 11), (16, 11), (23, 11), (30, 11)], spawn=(2, 13), goal=(40, 13))

level("zigzag", "Up, down, up, down, and pits in between.",
      width=44,
      solid=ground(44, gaps=[(10, 12), (22, 24), (34, 36)])
            + [(11, 6, 9), (8, 13, 16), (11, 18, 21), (8, 25, 28), (11, 30, 33)],
      coins=[(7, 10), (14, 7), (19, 10), (26, 7), (31, 10)],
      spawn=(2, 13), goal=(41, 13))

level("the-gauntlet", "Spikes, pits and platforms, all at once.",
      width=48,
      solid=ground(48, gaps=[(12, 14), (26, 28)])
            + [(11, 6, 9), (11, 16, 19), (8, 21, 24), (11, 31, 34), (12, 38, 44)],
      spikes=[(4, 13), (17, 13), (18, 13), (36, 13), (37, 13)],
      coins=[(7, 10), (17, 10), (22, 7), (32, 10), (41, 11)],
      spawn=(1, 13), goal=(46, 13))

level("the-summit", "The long climb. The goal is at the top.",
      width=48,
      solid=ground(48, gaps=[(9, 11), (20, 22)])
            + [(12, 14, 17), (11, 25, 28), (9, 30, 33), (7, 35, 38), (5, 40, 43), (3, 36, 39)],
      spikes=[(6, 13), (24, 13)],
      coins=[(15, 11), (26, 10), (31, 8), (36, 6), (37, 2)],
      spawn=(2, 13), goal=(38, 1))

level("moving-day", "A pit too wide to jump, and a platform that crosses it.",
      width=36, solid=ground(36, gaps=[(10, 20)]), track_h=[(12, 10, 20)],
      coins=[(6, 13), (14, 11), (18, 11), (30, 13)], spawn=(2, 13), goal=(34, 13))

level("up-and-over", "A lift to the high ground. You will have to wait for it.",
      width=32,
      solid=[(14, 0, 13), (15, 0, 13), (8, 17, 31), (9, 17, 31)],
      track_v=[(15, 7, 13)],
      coins=[(6, 13), (16, 10), (21, 7), (28, 7)], spawn=(2, 13), goal=(30, 7))


# ======================================================================
# 15: the first demon. Boss levels are long -- a run in, then an arena
# with room to move and something to hide behind.
# ======================================================================

def arena(width, boss_at, blocks=(), **rest):
    """The shared shape of a boss level: a long approach, then the fight."""
    spec = dict(width=width, solid=ground(width) + list(blocks), **rest)
    spec["boss"] = boss_at
    return spec


level("imps-den", "The first demon. Watch what it throws, then get past it.",
      **arena(
          64, boss_at=(46, 3, "IMP"),
          blocks=[(11, 20, 24), (11, 34, 38), (11, 50, 54)],
          spikes=[(14, 13), (28, 13)],
          coins=[(8, 13), (22, 10), (36, 10), (43, 13)],
          spawn=(2, 13), goal=(62, 13),
      ))


# ======================================================================
# 16-28: the rest of the flat game.
# ======================================================================

level("ferry", "Two ferries and the islands between them.",
      width=44,
      solid=[(14, 0, 7), (15, 0, 7), (14, 36, 43), (15, 36, 43),
             (12, 18, 19), (12, 30, 35)],
      track_h=[(12, 8, 17), (12, 20, 29)],
      coins=[(12, 11), (18, 11), (25, 11), (33, 11)], spawn=(2, 13), goal=(41, 13))

level("springboard", "Bounce pads throw you further than any jump.",
      width=32, solid=ground(32) + [(8, 6, 10), (8, 17, 21), (8, 26, 31)],
      bounce=[(14, 7, 8), (14, 18, 19), (14, 27, 28)],
      coins=[(8, 7), (19, 7), (28, 7)], spawn=(2, 13), goal=(30, 7))

level("high-jump", "Pads over spikes, and nothing else to land on.",
      width=36, solid=ground(36) + [(8, 8, 12), (8, 20, 24)],
      bounce=[(14, 5, 6), (14, 16, 18), (14, 28, 29)],
      spikes=[(9, 13), (13, 13), (22, 13), (26, 13)],
      coins=[(10, 7), (22, 7), (29, 7), (33, 13)], spawn=(2, 13), goal=(34, 13))

level("patrol", "Enemies, each penned between two blocks. Go over them.",
      width=36,
      solid=ground(36) + [(13, 7, 7), (13, 14, 14), (13, 21, 21), (13, 28, 28)],
      enemies=[(10, 13), (17, 13), (24, 13)],
      coins=[(4, 13), (11, 13), (18, 13), (25, 13)], spawn=(2, 13), goal=(33, 13))

level("no-loitering", "Enemies where the ground runs out.",
      width=40,
      solid=ground(40, gaps=[(12, 14), (26, 28)])
            + [(13, 6, 6), (13, 20, 20), (11, 16, 19), (11, 30, 33)],
      enemies=[(9, 13), (18, 10), (32, 10)], spikes=[(23, 13)],
      coins=[(8, 13), (17, 10), (31, 10), (37, 13)], spawn=(2, 13), goal=(38, 13))

level("black-ice", "Ice barely grips. Aim for the wall and let it stop you.",
      width=36, solid=ground(36) + [(13, 20, 20), (11, 24, 28)],
      ice=[(14, 6, 18), (14, 24, 30)],
      coins=[(10, 13), (16, 13), (26, 10), (33, 13)], spawn=(2, 13), goal=(34, 13))

level("skid-row", "Ice above a drop. Braking has to start early.",
      width=40,
      solid=ground(40, gaps=[(16, 18), (30, 32)]) + [(13, 12, 12), (13, 27, 27)],
      ice=[(14, 5, 11), (14, 19, 26)], spikes=[(14, 13)],
      coins=[(8, 13), (17, 11), (24, 13), (31, 11)], spawn=(2, 13), goal=(37, 13))

level("conveyor-belt", "Belts, one going your way and one not.",
      width=36, solid=ground(36, gaps=[(20, 22)]),
      belt_right=[(14, 5, 12)], belt_left=[(14, 25, 32)],
      coins=[(8, 13), (16, 13), (21, 11), (28, 13)], spawn=(2, 13), goal=(34, 13))

level("against-the-grain", "Most of the floor is pushing you back.",
      width=40, solid=ground(40) + [(11, 14, 18), (11, 26, 30)],
      belt_left=[(14, 4, 12), (14, 20, 24), (14, 32, 37)],
      belt_right=[(11, 14, 18)], spikes=[(19, 13)],
      coins=[(8, 13), (16, 10), (23, 13), (28, 10)], spawn=(1, 13), goal=(38, 13))

level("one-way-floor", "Crumbling tiles hold you once. There is no going back.",
      width=36, solid=ground(36, gaps=[(12, 15)]) + [(11, 20, 24)],
      crumble=[(14, 8, 11)],
      coins=[(5, 13), (10, 13), (22, 10), (31, 13)], spawn=(2, 13), goal=(33, 13))

level("the-shortcut", "A wall with no way over it, and a pair of doors.",
      width=40, solid=ground(40) + [(y, 20, 20) for y in range(2, 14)],
      portals=[(14, 12), (26, 12)],
      coins=[(6, 13), (16, 13), (30, 13), (36, 13)], spawn=(2, 13), goal=(38, 13))

level("two-doors", "Doors, and something waiting at each end.",
      width=44,
      solid=ground(44, gaps=[(10, 12)]) + [(y, 28, 28) for y in range(4, 14)]
            + [(11, 16, 21), (13, 22, 22), (13, 26, 26), (13, 34, 34), (13, 38, 38)],
      portals=[(18, 10), (32, 12)], enemies=[(24, 13), (36, 13)], spikes=[(6, 13)],
      coins=[(4, 13), (19, 10), (24, 11), (42, 13)], spawn=(1, 13), goal=(43, 13))

level("the-works", "Ice, a ferry, a belt, an enemy, a floor that goes, a pad.",
      width=48,
      solid=ground(48, gaps=[(12, 18), (34, 36)]) + [(11, 24, 29), (10, 42, 47)],
      track_h=[(12, 12, 18)], ice=[(14, 5, 10)], belt_right=[(11, 24, 29)],
      bounce=[(14, 40, 41)], crumble=[(14, 37, 39)], enemies=[(26, 10)],
      spikes=[(22, 13)],
      coins=[(9, 13), (15, 11), (26, 9), (33, 13), (45, 9)],
      spawn=(1, 13), goal=(46, 9))


# ======================================================================
# 29-44: the game finds a vertical axis. Ladders, one-way platforms,
# updraughts and blinking blocks, then levels tall enough to need them.
# ======================================================================

level("first-rungs", "A ledge with no jump that reaches it, and a ladder.",
      width=36, solid=ground(36) + [(9, 10, 20)],
      ladders=[(9, 8, 13)],
      coins=[(5, 13), (14, 8), (18, 8), (28, 13)], spawn=(2, 13), goal=(20, 8))

level("wyrms-nest", "It throws high and low. Neither ducking nor jumping is enough.",
      **arena(
          64, boss_at=(46, 3, "WYRM"),
          blocks=[(11, 18, 22), (9, 26, 30), (11, 36, 40), (11, 52, 56)],
          spikes=[(12, 13), (33, 13)],
          coins=[(7, 13), (20, 10), (28, 8), (38, 10)],
          spawn=(2, 13), goal=(62, 13),
      ))

level("the-shaft", "Straight up, on ladders, through holes in the floors.",
      width=20, height=TALL,
      solid=ground(20, height=TALL)
            + [(24, 2, 7), (24, 9, 16), (18, 3, 10), (18, 12, 17),
               (12, 2, 7), (12, 9, 16), (6, 3, 11), (6, 13, 16)],
      ladders=[(8, 23, 29), (11, 17, 23), (8, 11, 17), (12, 5, 11)],
      coins=[(4, 23), (15, 17), (4, 11), (15, 5)], spawn=(2, 29), goal=(9, 5))

level("through-the-floor", "Platforms you rise through and land on.",
      width=36,
      solid=ground(36) + [(6, 16, 22), (6, 28, 34)],
      one_way=[(11, 2, 10), (8, 2, 10), (6, 2, 8), (9, 14, 24), (11, 26, 34)],
      coins=[(5, 10), (19, 8), (30, 10), (31, 5)], spawn=(2, 13), goal=(4, 5))

level("updraught", "Step into the column and it takes you up.",
      width=36, solid=ground(36) + [(6, 10, 16), (6, 24, 30)],
      updraft=[(8, 5, 13), (9, 5, 13), (26, 5, 13), (27, 5, 13)],
      coins=[(5, 13), (13, 5), (20, 13), (28, 5)], spawn=(2, 13), goal=(30, 5))

level("now-you-dont", "The floor is there half the time.",
      width=36, solid=ground(36, gaps=[(10, 14), (22, 26)]),
      blinking=[(13, 10, 14), (13, 22, 26)],
      coins=[(6, 13), (12, 11), (18, 13), (24, 11)], spawn=(2, 13), goal=(33, 13))

level("tall-order", "Ladders up, one-way platforms down.",
      width=24, height=TALL,
      solid=ground(24, height=TALL) + [(22, 2, 9), (22, 11, 21), (14, 2, 12), (14, 14, 21), (6, 4, 16), (6, 18, 21)],
      ladders=[(10, 21, 29), (13, 13, 21), (17, 6, 9)],
      one_way=[(18, 4, 20), (10, 3, 20)],
      coins=[(5, 21), (18, 13), (7, 9), (16, 5)], spawn=(2, 29), goal=(19, 5))

level("chimney", "One long column of rising air.",
      width=20, height=TALL,
      solid=ground(20, height=TALL) + [(20, 2, 6), (14, 12, 17), (8, 2, 8), (4, 10, 17)],
      updraft=[(9, 5, 29), (10, 5, 29)],
      coins=[(4, 19), (14, 13), (5, 7), (14, 3)], spawn=(2, 29), goal=(16, 3))

level("blink-and-climb", "Rungs, and a floor that keeps changing its mind.",
      width=32, solid=ground(32, gaps=[(14, 18)]) + [(8, 20, 30)],
      ladders=[(21, 7, 13)],
      blinking=[(13, 14, 18)],
      coins=[(6, 13), (16, 11), (25, 7), (29, 7)], spawn=(2, 13), goal=(28, 7))

level("scaffold", "A ferry, and boards you can climb through.",
      width=40, solid=ground(40, gaps=[(12, 24)]) + [(6, 28, 38)],
      track_h=[(11, 12, 24)],
      one_way=[(8, 26, 38)],
      coins=[(8, 13), (16, 10), (22, 10), (33, 5)], spawn=(2, 13), goal=(36, 5))

level("the-well", "All the way down, and the only way out is the ladder.",
      width=20, height=TALL,
      solid=ground(20, height=TALL)
            + [(6, 0, 8), (6, 10, 19), (12, 2, 11), (12, 13, 19), (18, 0, 7), (18, 9, 19),
               (24, 3, 12), (24, 14, 19)],
      ladders=[(16, 5, 29)],
      coins=[(4, 5), (14, 11), (4, 17), (7, 23)], spawn=(2, 5), goal=(17, 29))

level("hot-and-cold", "Ice one way, belts the other.",
      width=40, solid=ground(40) + [(11, 16, 24)],
      ice=[(14, 4, 14)], belt_left=[(14, 26, 36)],
      spikes=[(15, 13), (25, 13)],
      coins=[(9, 13), (20, 10), (30, 13), (37, 13)], spawn=(1, 13), goal=(38, 13))

# One ladder the whole way up, threading a gap left in every floor.
# The crumbling stretches are on the floors themselves, so coming back
# down the way you came is not an option.
level("crumbling-tower", "Every floor holds you once.",
      width=20, height=TALL,
      solid=ground(20, height=TALL)
            + [(24, 2, 6), (24, 9, 14), (24, 16, 18),
               (18, 2, 14), (18, 16, 18),
               (12, 2, 6), (12, 9, 14), (12, 16, 18),  # hole at 7-8 stays open
               (6, 2, 14), (6, 16, 18)],
      crumble=[(24, 7, 8), (18, 7, 8)],
      ladders=[(15, 5, 29)],
      coins=[(4, 23), (12, 17), (4, 11), (13, 5)], spawn=(2, 29), goal=(2, 5))

level("the-aviary", "Rising air, and something already up there.",
      width=36, solid=ground(36) + [(8, 10, 18), (8, 24, 32)],
      updraft=[(7, 7, 13), (8, 7, 13), (22, 7, 13), (23, 7, 13)],
      enemies=[(14, 7), (28, 7)],
      coins=[(5, 13), (17, 7), (20, 13), (31, 7)], spawn=(2, 13), goal=(33, 13))

level("portal-shaft", "A shaft, and a door at each end of it.",
      width=20, height=TALL,
      solid=ground(20, height=TALL) + [(8, 2, 17), (16, 2, 17), (24, 2, 17)],
      ladders=[(10, 23, 29), (10, 15, 23)],
      portals=[(4, 15), (14, 7)],
      coins=[(5, 29), (14, 23), (5, 15), (14, 6)], spawn=(2, 29), goal=(4, 7))

level("second-gauntlet", "Everything the middle of the game taught you.",
      width=48,
      solid=ground(48, gaps=[(14, 17), (30, 33)]) + [(9, 20, 27), (9, 36, 44)],
      one_way=[(12, 19, 28)],
      updraft=[(34, 8, 13), (35, 8, 13)],
      blinking=[(13, 14, 17)],
      ladders=[(18, 8, 13)],
      spikes=[(8, 13), (24, 13)],
      coins=[(5, 13), (16, 11), (23, 8), (40, 8)], spawn=(1, 13), goal=(45, 8))


# ======================================================================
# 45-60: the last stretch. Everything at once, and two more demons.
# ======================================================================

level("molochs-forge", "Fast fists, and fireballs that hang about.",
      **arena(
          68, boss_at=(50, 3, "MOLOCH"),
          blocks=[(11, 16, 20), (8, 24, 29), (11, 34, 39), (11, 44, 47), (11, 56, 60)],
          spikes=[(11, 13), (31, 13), (42, 13)],
          coins=[(6, 13), (18, 10), (26, 7), (37, 10)],
          spawn=(2, 13), goal=(66, 13),
      ))

level("ratlines", "Rungs, and something climbing about below.",
      width=36,
      solid=ground(36) + [(9, 8, 16), (9, 22, 32),
                          (13, 10, 10), (13, 16, 16), (8, 24, 24), (8, 30, 30)],
      ladders=[(7, 8, 13), (20, 8, 13)],
      enemies=[(13, 13), (27, 8)],
      coins=[(3, 13), (13, 8), (18, 13), (32, 8)], spawn=(1, 13), goal=(31, 8))

# The storeys are three cells apart, not four: a jump rises 3.6 cells,
# so a board four above the one below it might as well be a ceiling.
level("trapdoors", "Boards to fall through, and boards that only fall once.",
      width=36, solid=ground(36),
      one_way=[(11, 2, 12), (11, 22, 34), (8, 2, 10), (8, 24, 34)],
      crumble=[(14, 16, 17)],
      coins=[(6, 10), (16, 13), (28, 10), (32, 7)], spawn=(2, 13), goal=(4, 7))

level("thermals", "Rising air over a floor you would rather not touch.",
      width=40, solid=ground(40) + [(6, 12, 20), (6, 28, 38)],
      updraft=[(10, 5, 13), (11, 5, 13), (25, 5, 13), (26, 5, 13)],
      spikes=[(14, 13), (15, 13), (30, 13), (31, 13)],
      coins=[(6, 13), (16, 5), (22, 13), (33, 5)], spawn=(1, 13), goal=(36, 5))

level("stutter", "A ferry, and stepping stones that keep vanishing.",
      width=40, solid=ground(40, gaps=[(10, 30)]) + [(11, 18, 22)],
      track_h=[(12, 10, 16)],
      blinking=[(12, 24, 30)],
      coins=[(6, 13), (14, 11), (20, 10), (35, 13)], spawn=(2, 13), goal=(37, 13))

level("the-spire", "Up, by every means the game has.",
      width=24, height=TALL,
      solid=ground(24, height=TALL)
            + [(25, 2, 10), (25, 12, 21), (19, 3, 12), (19, 14, 21),
               (13, 2, 9), (13, 12, 21), (7, 4, 9), (7, 12, 21)],
      ladders=[(11, 24, 29), (13, 18, 24)],
      one_way=[(16, 3, 20)],
      updraft=[(10, 6, 12), (11, 6, 12)],
      bounce=[(25, 5, 6)],
      coins=[(6, 24), (17, 18), (5, 12), (16, 6)], spawn=(2, 29), goal=(19, 6))

level("greased", "Ice, and boards that will not stop you either.",
      width=40, solid=ground(40, gaps=[(18, 21)]) + [(7, 24, 34)],
      ice=[(14, 5, 16)],
      one_way=[(11, 22, 34), (8, 19, 23)],
      coins=[(9, 13), (15, 13), (28, 10), (30, 6)], spawn=(1, 13), goal=(32, 6))

level("belt-and-braces", "The floor is going one way and the ladder is not.",
      width=36, solid=ground(36) + [(8, 14, 24)],
      belt_left=[(14, 4, 12)], belt_right=[(14, 26, 33)],
      ladders=[(13, 7, 13), (25, 7, 13)],
      coins=[(6, 13), (12, 7), (20, 7), (30, 13)], spawn=(1, 13), goal=(34, 13))

# Each storey's hole is two cells wide and offset from the one above,
# so the descent is a zigzag of deliberate drops rather than one fall.
level("the-drop", "A long way down, and only one place to land.",
      width=20, height=TALL,
      solid=ground(20, height=TALL)
            + [(5, 0, 8), (5, 11, 19),
               (11, 0, 13), (11, 16, 19),
               (17, 0, 3), (17, 6, 19),
               (23, 0, 11), (23, 14, 19)],
      spikes=[(10, 16), (2, 22)],
      coins=[(4, 4), (16, 10), (8, 16), (16, 22)], spawn=(2, 4), goal=(3, 29))

level("hall-of-doors", "Doors, and a floor that is not always there.",
      width=40, solid=ground(40, gaps=[(12, 16), (24, 28)]) + [(y, 32, 32) for y in range(4, 14)],
      blinking=[(13, 12, 16), (13, 24, 28)],
      portals=[(20, 12), (36, 12)],
      coins=[(6, 13), (14, 11), (26, 11), (38, 13)], spawn=(2, 13), goal=(34, 13))

level("ferrymans-due", "Two ferries, and spikes where you would rather step.",
      width=44,
      solid=[(14, 0, 8), (15, 0, 8), (14, 20, 23), (15, 20, 23),
             (14, 35, 43), (15, 35, 43)],
      track_h=[(12, 9, 19), (12, 24, 34)],
      spikes=[(21, 13), (22, 13)],
      coins=[(5, 13), (14, 11), (29, 11), (40, 13)], spawn=(2, 13), goal=(42, 13))

level("the-hive", "Rising air, and it is not yours alone.",
      width=40,
      solid=ground(40) + [(7, 8, 12), (7, 26, 30), (13, 16, 16), (13, 22, 22)],
      updraft=[(6, 6, 13), (7, 6, 13), (24, 6, 13), (25, 6, 13)],
      enemies=[(10, 6), (19, 13), (28, 6)],
      coins=[(4, 13), (12, 6), (30, 6), (36, 13)], spawn=(1, 13), goal=(37, 13))

level("glass-floor", "Every board holds you once, and none of them twice.",
      width=36, solid=ground(36, gaps=[(8, 26)]) + [(11, 14, 20)],
      crumble=[(11, 10, 13)],
      one_way=[(11, 21, 27)],
      updraft=[(28, 8, 13), (29, 8, 13)],
      coins=[(5, 13), (12, 10), (18, 10), (31, 13)], spawn=(2, 13), goal=(33, 13))

level("the-long-climb", "Rungs and rising air, all the way to the top.",
      width=20, height=TALL,
      solid=ground(20, height=TALL)
            + [(25, 2, 9), (25, 11, 17), (19, 2, 7), (19, 9, 17),
               (13, 3, 10), (13, 12, 17), (7, 2, 17)],
      ladders=[(10, 24, 29), (8, 18, 24)],
      updraft=[(15, 6, 18), (16, 6, 18)],
      coins=[(5, 24), (14, 18), (5, 12), (12, 6)], spawn=(2, 29), goal=(9, 6))

level("everything-everywhere", "One of each, and no time to think about it.",
      width=52,
      solid=ground(52, gaps=[(16, 19), (34, 37)]) + [(9, 24, 28), (9, 40, 50)],
      track_h=[(12, 16, 19)],
      ice=[(14, 4, 12)],
      belt_right=[(9, 24, 28)],
      blinking=[(13, 34, 37)],
      updraft=[(38, 8, 13), (39, 8, 13)],
      ladders=[(21, 8, 13)],
      crumble=[(14, 30, 33)],
      enemies=[(26, 8)],
      # The enemy's ledge is five wide, matching the ferry's short track,
      # so the level's period stays inside what the solver can search.
      spikes=[(14, 13)],
      coins=[(8, 13), (18, 11), (26, 8), (45, 8)], spawn=(1, 13), goal=(49, 8))

level("the-balrog", "The last one. It has been saving all of it.",
      **arena(
          72, boss_at=(54, 3, "BALROG"),
          blocks=[(11, 14, 18), (8, 22, 27), (11, 32, 36), (9, 42, 46),
                  (11, 50, 54), (11, 62, 66)],
          spikes=[(10, 13), (29, 13), (39, 13), (48, 13)],
          coins=[(5, 13), (16, 10), (24, 7), (34, 10), (44, 8)],
          spawn=(2, 13), goal=(70, 13),
      ))


ORDER = (
    "first-steps", "up-we-go", "mind-the-spikes", "the-pit", "down-and-out",
    "low-ceiling", "the-tower", "spike-corridor", "leap-of-faith", "zigzag",
    "the-gauntlet", "the-summit", "moving-day", "up-and-over", "imps-den",
    "ferry", "springboard", "high-jump", "patrol", "no-loitering",
    "black-ice", "skid-row", "conveyor-belt", "against-the-grain",
    "one-way-floor", "the-shortcut", "two-doors", "the-works", "first-rungs",
    "wyrms-nest", "the-shaft", "through-the-floor", "updraught",
    "now-you-dont", "tall-order", "chimney", "blink-and-climb", "scaffold",
    "the-well", "hot-and-cold", "crumbling-tower", "the-aviary",
    "portal-shaft", "second-gauntlet", "molochs-forge", "ratlines",
    "trapdoors", "thermals", "stutter", "the-spire", "greased",
    "belt-and-braces", "the-drop", "hall-of-doors", "ferrymans-due",
    "the-hive", "glass-floor", "the-long-climb", "everything-everywhere",
    "the-balrog",
)

assert len(ORDER) == 60, f"{len(ORDER)} levels, expected 60"
assert set(ORDER) == set(SPECS), f"mismatch: {set(ORDER) ^ set(SPECS)}"
