import subprocess
import sys

import pytest

from pi_menu import terminal


@pytest.fixture(autouse=True)
def isolated_script_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal, "SCRIPT_DIR", tmp_path / "launch")


def test_find_terminal_returns_the_first_installed_emulator(monkeypatch):
    monkeypatch.setattr(
        terminal.shutil,
        "which",
        lambda name: "/usr/bin/xterm" if name == "xterm" else None,
    )
    assert terminal.find_terminal() == ("/usr/bin/xterm", ["-e"])


def test_find_terminal_prefers_lxterminal_which_is_the_pi_default(monkeypatch):
    monkeypatch.setattr(terminal.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert terminal.find_terminal()[0] == "/usr/bin/lxterminal"


def test_find_terminal_returns_none_when_nothing_is_installed(monkeypatch):
    monkeypatch.setattr(terminal.shutil, "which", lambda name: None)
    assert terminal.find_terminal() is None


def test_asking_for_a_terminal_when_none_exists_raises(monkeypatch):
    monkeypatch.setattr(terminal.shutil, "which", lambda name: None)
    with pytest.raises(terminal.NoTerminalFound, match="lxterminal"):
        terminal.launch(["true"])


def test_running_without_a_terminal_starts_the_process_directly():
    process = terminal.launch([sys.executable, "-c", "pass"], in_terminal=False)
    assert process.wait(timeout=10) == 0


def test_the_wrapper_script_runs_the_command_and_returns_its_status():
    script = terminal._write_script([sys.executable, "-c", "raise SystemExit(3)"], "T", "never")
    result = subprocess.run(["sh", str(script)], capture_output=True, text=True)
    assert result.returncode == 3
    assert "exited with status 3" in result.stdout


def test_a_successful_command_exits_cleanly():
    script = terminal._write_script([sys.executable, "-c", "print('hi')"], "T", "never")
    result = subprocess.run(["sh", str(script)], capture_output=True, text=True)
    assert result.returncode == 0
    assert "hi" in result.stdout


def test_arguments_with_spaces_survive_the_shell_wrapper():
    script = terminal._write_script(
        [sys.executable, "-c", "import sys; print(sys.argv[1])", "two words"],
        "T",
        "never",
    )
    result = subprocess.run(["sh", str(script)], capture_output=True, text=True)
    assert "two words" in result.stdout


def test_hold_always_waits_for_input_even_on_success():
    script = terminal._write_script([sys.executable, "-c", "pass"], "T", "always")
    result = subprocess.run(
        ["sh", str(script)], input="\n", capture_output=True, text=True, timeout=10
    )
    assert "Press Enter" in result.stdout


def test_hold_on_error_only_waits_when_the_command_fails():
    ok = terminal._write_script([sys.executable, "-c", "pass"], "T", "on-error")
    result = subprocess.run(["sh", str(ok)], capture_output=True, text=True, timeout=10)
    assert "Press Enter" not in result.stdout

    bad = terminal._write_script([sys.executable, "-c", "raise SystemExit(1)"], "T", "on-error")
    result = subprocess.run(
        ["sh", str(bad)], input="\n", capture_output=True, text=True, timeout=10
    )
    assert "Press Enter" in result.stdout


def test_each_launch_gets_its_own_script():
    first = terminal._write_script(["true"], "T", "never")
    second = terminal._write_script(["true"], "T", "never")
    assert first != second


def test_stale_scripts_are_pruned_but_fresh_ones_are_kept():
    import os
    import time

    old = terminal._write_script(["true"], "old", "never")
    os.utime(old, (0, time.time() - terminal.SCRIPT_MAX_AGE - 60))
    fresh = terminal._write_script(["true"], "fresh", "never")

    terminal._prune_old_scripts()

    assert not old.exists()
    assert fresh.exists()
