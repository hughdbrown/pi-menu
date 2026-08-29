"""The sound settings file: two loudnesses and a tune, none of which may
break the game when the file is missing, corrupt or from an older version.
"""

from __future__ import annotations

from pi_menu.platformer.sound_settings import (
    DEFAULTS,
    MAX_LEVEL,
    TUNE_CHOICES,
    SoundSettings,
    load,
    save,
)


def test_the_choices_survive_a_round_trip(tmp_path):
    path = tmp_path / "sound.json"
    settings = SoundSettings(music=2, effects=7, tune=4)

    save(settings, path)

    assert load(path) == settings


def test_a_missing_file_means_the_defaults(tmp_path):
    assert load(tmp_path / "nothing-here.json") == DEFAULTS


def test_a_corrupt_file_means_the_defaults(tmp_path):
    path = tmp_path / "sound.json"
    path.write_text("not json at all {", encoding="utf-8")
    assert load(path) == DEFAULTS


def test_nonsense_values_fall_back_to_the_defaults(tmp_path):
    path = tmp_path / "sound.json"
    path.write_text('{"music": "loud", "effects": null, "tune": []}', encoding="utf-8")
    assert load(path) == DEFAULTS


def test_loudness_is_clamped_to_the_scale(tmp_path):
    path = tmp_path / "sound.json"
    path.write_text('{"music": 99, "effects": -5, "tune": 99}', encoding="utf-8")

    settings = load(path)

    assert settings.music == MAX_LEVEL
    assert settings.effects == 0
    assert settings.tune == TUNE_CHOICES


def test_an_old_one_word_file_keeps_its_meaning(tmp_path):
    """The first version of this file held {"sound": "music"|"effects"|"off"}."""
    path = tmp_path / "sound.json"

    path.write_text('{"sound": "off"}', encoding="utf-8")
    silent = load(path)
    assert silent.music == 0 and silent.effects == 0

    path.write_text('{"sound": "effects"}', encoding="utf-8")
    blips = load(path)
    assert blips.music == 0 and blips.effects > 0

    path.write_text('{"sound": "music"}', encoding="utf-8")
    tunes = load(path)
    assert tunes.music > 0


def test_saving_somewhere_unwritable_is_quiet(tmp_path):
    blocked = tmp_path / "file-not-a-directory"
    blocked.write_text("", encoding="utf-8")
    save(DEFAULTS, blocked / "sound.json")  # must not raise
