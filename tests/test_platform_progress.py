"""Which levels have been finished, remembered between runs.

The file exists to colour the level picker. Nothing about playing the
game depends on it, so every way it can go wrong -- missing, corrupt,
unreadable, unwritable -- has to read as "nothing finished yet" rather
than as an error. Refusing to start a game over a bad cache file would
be absurd.
"""

from __future__ import annotations

import json

import pytest

from pi_menu.platformer.progress import Progress, default_path


@pytest.fixture
def path(tmp_path):
    return tmp_path / "nested" / "platform-progress.json"


def test_nothing_is_finished_to_begin_with(path):
    assert Progress(path).completed == frozenset()


def test_what_is_marked_comes_back(path):
    Progress(path).mark("first-steps")

    assert "first-steps" in Progress(path).completed


def test_marking_the_same_level_twice_records_it_once(path):
    progress = Progress(path)
    progress.mark("first-steps")
    progress.mark("first-steps")

    assert sorted(json.loads(path.read_text())["completed"]) == ["first-steps"]


def test_several_levels_are_all_remembered(path):
    progress = Progress(path)
    progress.mark("first-steps")
    progress.mark("the-tower")

    assert Progress(path).completed == frozenset({"first-steps", "the-tower"})


def test_a_missing_file_is_not_an_error(path):
    assert not path.exists()
    assert Progress(path).completed == frozenset()


def test_a_corrupt_file_reads_as_nothing_finished(path):
    path.parent.mkdir(parents=True)
    path.write_text("{not json at all", encoding="utf-8")

    assert Progress(path).completed == frozenset()


def test_a_file_of_the_wrong_shape_reads_as_nothing_finished(path):
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"completed": "first-steps"}), encoding="utf-8")

    assert Progress(path).completed == frozenset()


def test_a_list_with_junk_in_it_keeps_only_the_names(path):
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"completed": ["ok", 7, None]}), encoding="utf-8")

    assert Progress(path).completed == frozenset({"ok"})


def test_a_directory_where_the_file_should_be_does_not_raise(path):
    path.parent.mkdir(parents=True)
    path.mkdir()

    progress = Progress(path)
    progress.mark("first-steps")  # cannot be saved, must not raise

    assert progress.completed == frozenset({"first-steps"})


def test_is_done_answers_for_one_level(path):
    progress = Progress(path)
    progress.mark("the-pit")

    assert progress.is_done("the-pit") is True
    assert progress.is_done("zigzag") is False


def test_the_default_path_lives_beside_the_other_settings():
    assert default_path().name == "platform-progress.json"
    assert default_path().parent.name == "pi-menu"


def test_the_default_path_can_be_overridden(monkeypatch, tmp_path):
    monkeypatch.setenv("PI_MENU_PROGRESS", str(tmp_path / "elsewhere.json"))

    assert default_path() == tmp_path / "elsewhere.json"
