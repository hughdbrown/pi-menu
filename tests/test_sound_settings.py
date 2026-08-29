"""The sound setting file: three words, none of which may break the game."""

from __future__ import annotations

from pi_menu.platformer.sound_settings import DEFAULT, Sound, load, save


def test_the_choice_survives_a_round_trip(tmp_path):
    path = tmp_path / "sound.json"
    for mode in Sound:
        save(mode, path)
        assert load(path) is mode


def test_a_missing_file_means_the_default(tmp_path):
    assert load(tmp_path / "nothing-here.json") is DEFAULT


def test_a_corrupt_file_means_the_default(tmp_path):
    path = tmp_path / "sound.json"
    path.write_text("not json at all {", encoding="utf-8")
    assert load(path) is DEFAULT


def test_an_unknown_word_means_the_default(tmp_path):
    path = tmp_path / "sound.json"
    path.write_text('{"sound": "loudness"}', encoding="utf-8")
    assert load(path) is DEFAULT


def test_saving_somewhere_unwritable_is_quiet(tmp_path):
    blocked = tmp_path / "file-not-a-directory"
    blocked.write_text("", encoding="utf-8")
    save(Sound.OFF, blocked / "sound.json")  # must not raise
