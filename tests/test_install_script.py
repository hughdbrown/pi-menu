"""Checks on install.sh, driven by sourcing it in a throwaway HOME.

The script is sourceable without running, so the parts that generate
files can be exercised directly. Nothing here installs anything: HOME
points at a temporary directory throughout.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

INSTALL = Path(__file__).resolve().parents[1] / "install.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="needs bash"
)


def run_bash(script: str, home: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", f'source "{INSTALL}"\n{script}'],
        capture_output=True,
        text=True,
        env={"HOME": str(home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "USER": "tester"},
        timeout=60,
    )


def test_the_script_is_valid_bash():
    assert subprocess.run(["bash", "-n", str(INSTALL)]).returncode == 0


def test_sourcing_the_script_does_not_install_anything(tmp_path):
    result = run_bash("true", tmp_path)

    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []


def test_help_shows_the_usage_lines_and_nothing_else():
    result = subprocess.run(
        ["bash", str(INSTALL), "--help"], capture_output=True, text=True, timeout=30
    )

    assert result.returncode == 0
    assert "./install.sh --uninstall" in result.stdout
    assert "set -" not in result.stdout  # no script body leaking through


def test_an_unknown_option_is_refused():
    result = subprocess.run(
        ["bash", str(INSTALL), "--wat"], capture_output=True, text=True, timeout=30
    )

    assert result.returncode != 0
    assert "unknown option" in result.stderr


def test_desktop_entries_are_written_for_every_windowed_app(tmp_path):
    result = run_bash("install_desktop_entries", tmp_path)
    assert result.returncode == 0, result.stderr

    applications = tmp_path / ".local" / "share" / "applications"
    written = sorted(path.name for path in applications.glob("*.desktop"))
    assert written == [
        "pi-imgshow.desktop",
        "pi-life.desktop",
        "pi-menu.desktop",
        "pi-platformer.desktop",
    ]


def test_the_platform_game_is_installed_as_a_game(tmp_path):
    run_bash("install_desktop_entries", tmp_path)
    entry = (tmp_path / ".local/share/applications/pi-platformer.desktop").read_text()

    fields = dict(
        line.split("=", 1) for line in entry.strip().splitlines()[1:] if "=" in line
    )
    assert fields["Categories"] == "Game;ArcadeGame;"
    assert fields["Exec"].endswith("/venv/bin/pi-platformer")
    assert fields["Terminal"] == "true"


def test_a_desktop_entry_has_the_fields_a_menu_needs(tmp_path):
    run_bash("install_desktop_entries", tmp_path)
    entry = (tmp_path / ".local/share/applications/pi-life.desktop").read_text()

    assert entry.startswith("[Desktop Entry]\n")
    fields = dict(
        line.split("=", 1) for line in entry.strip().splitlines()[1:] if "=" in line
    )
    assert fields["Type"] == "Application"
    assert fields["Name"] == "Game of Life (Stellar Unicorn)"
    assert fields["Categories"].endswith(";")  # XDG requires the trailing ;
    assert fields["Exec"].endswith("/venv/bin/pi-life")
    assert fields["Terminal"] == "true"


def test_the_menu_entry_itself_does_not_ask_for_a_terminal(tmp_path):
    run_bash("install_desktop_entries", tmp_path)
    entry = (tmp_path / ".local/share/applications/pi-menu.desktop").read_text()

    # Pi Menu is the thing that opens terminals, so it must not be one.
    assert "Terminal=false" in entry


def test_every_exec_line_points_inside_the_install_prefix(tmp_path):
    run_bash("install_desktop_entries", tmp_path)
    applications = tmp_path / ".local/share/applications"

    for entry in applications.glob("*.desktop"):
        exec_line = next(
            line for line in entry.read_text().splitlines() if line.startswith("Exec=")
        )
        assert exec_line[len("Exec=") :].startswith(f"{tmp_path}/.local/share/pi-menu/venv/bin/")


def test_the_default_app_list_is_copied_but_never_overwritten(tmp_path):
    run_bash("install_user_config", tmp_path)
    config = tmp_path / ".config" / "pi-menu" / "apps.json"
    assert "Conway" in config.read_text()

    config.write_text('{"apps": []}', encoding="utf-8")
    result = run_bash("install_user_config", tmp_path)

    assert config.read_text() == '{"apps": []}'
    assert "Keeping your existing" in result.stdout


def test_uninstall_removes_what_install_created_but_keeps_your_app_list(tmp_path):
    run_bash("install_desktop_entries; install_user_config", tmp_path)
    (tmp_path / ".local/share/pi-menu").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".local/share/pi-menu/venv").mkdir(exist_ok=True)

    result = run_bash("uninstall", tmp_path)
    assert result.returncode == 0, result.stderr

    assert not list((tmp_path / ".local/share/applications").glob("*.desktop"))
    assert not (tmp_path / ".local/share/pi-menu").exists()
    # The app list is yours, so it survives.
    assert (tmp_path / ".config/pi-menu/apps.json").exists()


def test_uninstall_is_safe_to_run_when_nothing_is_installed(tmp_path):
    assert run_bash("uninstall", tmp_path).returncode == 0


def timeout_supports_a_kill_deadline() -> bool:
    if shutil.which("timeout") is None:
        return False
    probe = subprocess.run(
        ["timeout", "--kill-after=1s", "1s", "true"], capture_output=True
    )
    return probe.returncode == 0


@pytest.mark.skipif(
    not timeout_supports_a_kill_deadline(), reason="needs GNU timeout --kill-after"
)
def test_a_wedged_lxpanelctl_cannot_hang_the_installer(tmp_path):
    # The real hang: lxpanelctl waiting on a panel that will never answer.
    # SIGTERM alone is not enough to model it -- a process is free to
    # ignore that -- so the stub does, and only SIGKILL can end it.
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    stub = stub_bin / "lxpanelctl"
    stub.write_text("#!/bin/sh\ntrap '' TERM\nsleep 300\n", encoding="utf-8")
    stub.chmod(0o755)

    home = tmp_path / "home"
    home.mkdir()
    started = time.monotonic()
    result = subprocess.run(
        ["bash", "-c", f'source "{INSTALL}"\nrefresh_menu'],
        capture_output=True,
        text=True,
        env={
            "HOME": str(home),
            "PATH": f"{stub_bin}:{os.environ['PATH']}",
            "USER": "tester",
            "DISPLAY": ":0",
        },
        timeout=60,
    )
    elapsed = time.monotonic() - started

    assert result.returncode == 0, result.stderr
    # 5s to give up, 1s more to kill: anything past that is the old hang.
    assert elapsed < 15, f"refresh_menu took {elapsed:.1f}s"
