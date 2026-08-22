"""Smoke tests for the three Tk front-ends.

The windows themselves need a display, but importing the modules and
building their argument parsers does not. That is enough to catch a
mistyped import or a broken option before it reaches the Pi.

Where tkinter is genuinely absent -- a developer machine without
python3-tk -- it is stubbed, since none of this touches a real widget.
"""

from __future__ import annotations

import importlib
import sys
import types

import pytest


def _stub_tkinter():
    """Install a tkinter stub, only if the real one is unavailable."""
    try:
        import tkinter  # noqa: F401

        return
    except ImportError:
        pass

    tkinter = types.ModuleType("tkinter")
    for name in ("Tk", "Canvas", "Listbox", "StringVar", "IntVar", "BooleanVar"):
        setattr(tkinter, name, type(name, (), {}))
    tkinter.TclError = type("TclError", (Exception,), {})
    tkinter.END = "end"

    for submodule in ("ttk", "filedialog"):
        module = types.ModuleType(f"tkinter.{submodule}")
        sys.modules[f"tkinter.{submodule}"] = module
        setattr(tkinter, submodule, module)

    sys.modules["tkinter"] = tkinter


_stub_tkinter()

MODULES = ["pi_menu.launcher", "pi_menu.life.app", "pi_menu.imgshow.app"]


@pytest.mark.parametrize("name", MODULES)
def test_the_module_imports_and_exposes_main(name):
    module = importlib.import_module(name)
    assert callable(module.main)


@pytest.mark.parametrize("name", MODULES)
def test_help_lists_the_options_without_opening_a_window(name, capsys):
    module = importlib.import_module(name)

    with pytest.raises(SystemExit) as exit_info:
        module.main(["--help"])

    assert exit_info.value.code == 0
    assert "usage:" in capsys.readouterr().out


@pytest.mark.parametrize("name", ["pi_menu.life.app", "pi_menu.imgshow.app"])
def test_the_apps_share_the_display_options(name, capsys):
    module = importlib.import_module(name)

    with pytest.raises(SystemExit):
        module.main(["--help"])

    help_text = capsys.readouterr().out
    for option in ("--backend", "--port", "--brightness"):
        assert option in help_text


def test_an_unknown_option_is_rejected(capsys):
    module = importlib.import_module("pi_menu.life.app")
    with pytest.raises(SystemExit) as exit_info:
        module.main(["--nonsense"])
    assert exit_info.value.code == 2


def test_list_prints_every_registered_app_without_a_window(capsys):
    launcher = importlib.import_module("pi_menu.launcher")

    assert launcher.main(["--list"]) == 0

    output = capsys.readouterr().out
    assert "Conway's Game of Life" in output
    assert "Image Shower" in output
    assert "pi_menu.life.app" in output


def test_list_reports_a_broken_app_file_instead_of_crashing(tmp_path, monkeypatch, capsys):
    broken = tmp_path / "apps.json"
    broken.write_text("{oops", encoding="utf-8")
    monkeypatch.setenv("PI_MENU_APPS", str(broken))

    launcher = importlib.import_module("pi_menu.launcher")

    assert launcher.main(["--list"]) == 1
    assert "not valid JSON" in capsys.readouterr().err
