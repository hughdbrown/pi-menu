import importlib.util
import json
import sys

import pytest

from pi_menu.config import ConfigError, apps_path, load_apps


def write(tmp_path, payload):
    path = tmp_path / "apps.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_the_packaged_app_list_loads_and_offers_both_apps():
    apps = load_apps()
    assert {app.id for app in apps} == {"life", "imgshow"}


def test_the_packaged_commands_point_at_real_importable_modules():
    for app in load_apps():
        command = app.resolved_command()
        assert command[0] == sys.executable
        assert command[1] == "-m"
        # The module must actually exist, or the menu entry is dead.
        assert importlib.util.find_spec(command[2]) is not None


def test_a_bare_list_is_accepted_as_well_as_an_apps_key(tmp_path):
    path = write(tmp_path, [{"name": "Thing", "command": ["true"]}])
    assert load_apps(path)[0].name == "Thing"


def test_placeholders_are_substituted_at_launch_time(tmp_path):
    path = write(tmp_path, [{"name": "T", "command": ["{python}", "-c", "pass"]}])
    assert load_apps(path)[0].resolved_command()[0] == sys.executable


def test_an_id_is_derived_from_the_name_when_absent(tmp_path):
    path = write(tmp_path, [{"name": "My Cool App!", "command": ["true"]}])
    assert load_apps(path)[0].id == "my-cool-app"


def test_defaults_are_applied_to_optional_fields(tmp_path):
    path = write(tmp_path, [{"name": "T", "command": ["true"]}])
    app = load_apps(path)[0]
    assert (app.hold, app.terminal, app.enabled, app.description) == (
        "on-error",
        True,
        True,
        "",
    )


def test_a_string_command_is_rejected_with_advice(tmp_path):
    path = write(tmp_path, [{"name": "T", "command": "python3 -m thing"}])
    with pytest.raises(ConfigError, match="list of arguments"):
        load_apps(path)


@pytest.mark.parametrize(
    "entry,message",
    [
        ({"command": ["true"]}, "name"),
        ({"name": "", "command": ["true"]}, "name"),
        ({"name": "T"}, "command"),
        ({"name": "T", "command": []}, "command"),
        ({"name": "T", "command": [1, 2]}, "must be a string"),
        ({"name": "T", "command": ["true"], "hold": "maybe"}, "hold"),
        ("not an object", "must be an object"),
    ],
)
def test_bad_entries_are_rejected_with_a_useful_message(tmp_path, entry, message):
    path = write(tmp_path, [entry])
    with pytest.raises(ConfigError, match=message):
        load_apps(path)


def test_malformed_json_names_the_file(tmp_path):
    path = tmp_path / "apps.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError, match="not valid JSON"):
        load_apps(path)


def test_a_missing_file_is_a_config_error(tmp_path):
    with pytest.raises(ConfigError, match="no app list"):
        load_apps(tmp_path / "absent.json")


def test_a_top_level_object_without_apps_is_rejected(tmp_path):
    path = write(tmp_path, {"programs": []})
    with pytest.raises(ConfigError, match="list of apps"):
        load_apps(path)


def test_the_environment_variable_overrides_the_packaged_list(tmp_path, monkeypatch):
    path = write(tmp_path, [{"name": "Override", "command": ["true"]}])
    monkeypatch.setenv("PI_MENU_APPS", str(path))

    assert apps_path() == path
    assert load_apps()[0].name == "Override"
