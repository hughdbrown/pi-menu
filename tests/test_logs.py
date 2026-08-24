"""The log file: written where expected, and never fatal.

The whole point is the GUI-launched case, where stdout and stderr go
nowhere and the log is the only witness.
"""

from __future__ import annotations

import logging

import pytest

from pi_menu import logs


@pytest.fixture(autouse=True)
def clean_handlers():
    logger = logging.getLogger("pi_menu")
    before = list(logger.handlers)
    yield
    for handler in logger.handlers:
        if handler not in before:
            handler.close()
            logger.removeHandler(handler)


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    monkeypatch.setenv(logs.ENV_VAR, str(tmp_path / "logs"))
    return tmp_path / "logs"


def test_setup_creates_the_file_and_messages_arrive(log_dir):
    path = logs.setup("pi-menu")
    logging.getLogger("pi_menu.launcher").info("three apps loaded")

    assert path == log_dir / "pi-menu.log"
    assert "three apps loaded" in path.read_text()


def test_each_app_gets_its_own_file(log_dir):
    assert logs.setup("pi-menu").name == "pi-menu.log"
    assert logs.setup("platformer").name == "platformer.log"


def test_calling_setup_twice_does_not_double_every_line(log_dir):
    logs.setup("pi-menu")
    path = logs.setup("pi-menu")
    logging.getLogger("pi_menu.launcher").info("once only")

    assert path.read_text().count("once only") == 1


def test_an_unwritable_directory_is_not_fatal(tmp_path, monkeypatch):
    blocked = tmp_path / "blocked"
    blocked.write_text("a file where the directory should go")
    monkeypatch.setenv(logs.ENV_VAR, str(blocked / "logs"))

    assert logs.setup("pi-menu") is None  # and no exception


def test_uncaught_exceptions_reach_the_log(log_dir):
    import sys

    path = logs.setup("pi-menu")
    logger = logging.getLogger("pi_menu.launcher")
    previous = sys.excepthook
    try:
        logs.log_unhandled(logger)
        sys.excepthook(ValueError, ValueError("boom in the GUI"), None)
    finally:
        sys.excepthook = previous

    assert "boom in the GUI" in path.read_text()
    assert "CRITICAL" in path.read_text()
