"""The diagnostic has to work when everything else does not.

Most of these run against the real firmware over a pseudo-terminal, so
a passing doctor here means the same code path would light real LEDs.
"""

from __future__ import annotations

import os

import pytest

from pi_menu import doctor

pytestmark = pytest.mark.skipif(
    not hasattr(os, "openpty"), reason="needs pseudo-terminals"
)


def levels(results, level):
    return [r for r in results if r.level == level]


def test_a_running_panel_passes_the_handshake_check(pico):
    _, path = pico
    results, version = doctor.check_handshake(path)

    assert version == 2
    assert levels(results, doctor.FAIL) == []
    assert "protocol v2" in results[0].title


def test_the_frame_test_lights_the_panel_and_reports_a_rate(pico):
    firmware, path = pico
    results = doctor.check_frames(path)

    assert levels(results, doctor.FAIL) == []
    assert any("frames/second" in r.detail for r in results)
    # The walking-pixel run ends with a clear, so the panel finishes dark.
    assert set(firmware.graphics.pixels.values()) == {(0, 0, 0)}


def test_the_frame_test_sends_the_byte_that_kills_stale_firmware(pico):
    """Channel value 3 is the whole point of including that pattern."""
    _, path = pico
    results = doctor.check_frames(path)
    assert any("channel value 3" in r.title for r in results)


def test_a_silent_port_is_reported_as_not_running_the_server():
    master_fd, slave_fd = os.openpty()
    try:
        results, version = doctor.check_handshake(os.ttyname(slave_fd))
        assert version is None
        assert levels(results, doctor.FAIL)
        assert "said nothing at all" in results[0].detail
    finally:
        os.close(master_fd)
        os.close(slave_fd)


def test_a_repl_reply_is_explained_rather_than_dumped():
    """This is the failure the doctor was written for."""
    advice = doctor.interpret_reply(b">>> \n")
    assert "REPL" in advice
    assert "main.py is not running" in advice
    assert "power-cycle" in advice


def test_an_unopenable_port_is_reported_with_its_reason(tmp_path):
    results, version = doctor.check_handshake(str(tmp_path / "ttyNOPE"))
    assert version is None
    assert levels(results, doctor.FAIL)


def test_a_full_run_reports_the_panel_as_healthy(pico, capsys):
    """The host may fail its own checks (no tkinter here); the panel must not."""
    _, path = pico
    assert doctor.main(["--port", path]) in (0, 1)

    output = capsys.readouterr().out
    assert "frame server answered" in output
    assert "frames/second" in output
    # Nothing about the link itself may be a failure.
    panel_failures = [
        line for line in output.splitlines() if " FAIL " in line and path in line
    ]
    assert panel_failures == []


def test_the_exit_code_reports_whether_anything_failed(monkeypatch, capsys):
    def only(results):
        monkeypatch.setattr(doctor, "run_checks", lambda **kwargs: results)

    only([doctor.Result(doctor.OK, "fine")])
    assert doctor.main([]) == 0
    assert "Everything checks out" in capsys.readouterr().out

    only([doctor.Result(doctor.WARN, "not ideal")])
    assert doctor.main([]) == 0
    assert "1 warning(s)" in capsys.readouterr().out

    only([doctor.Result(doctor.FAIL, "broken")])
    assert doctor.main([]) == 1
    assert "1 problem(s) found" in capsys.readouterr().out


def test_the_frame_test_can_be_skipped_for_a_quick_check(pico, capsys):
    _, path = pico
    doctor.main(["--port", path, "--no-frames"])

    output = capsys.readouterr().out
    assert "frame test skipped" in output
    assert "frames/second" not in output


def test_results_render_with_their_detail_indented():
    rendered = doctor.Result(doctor.FAIL, "it broke", "line one\nline two").render()
    assert "[ FAIL ] it broke" in rendered
    assert "           line one" in rendered
    assert "           line two" in rendered
