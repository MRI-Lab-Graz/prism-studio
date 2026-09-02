"""Unit tests for app/src/plugins.py: the .prismrc.json / <dataset>/validators/
custom-validator plugin system used by the standalone PRISM validator CLI.

No prior test file covered this module -- these tests exercise the
load -> run round trip end to end via a real plugin file on disk, matching
how app/prism.py drives PluginManager.
"""

import dataclasses
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src")
)

from plugins import Plugin, PluginContext, PluginManager


def test_plugin_has_no_enabled_field():
    """Plugin.enabled was read in two places but never set to False anywhere
    in this codebase -- dead flexibility, deleted. This test pins the
    dataclass shape so it isn't silently reintroduced."""
    field_names = {f.name for f in dataclasses.fields(Plugin)}
    assert "enabled" not in field_names


def test_run_plugin_executes_a_discovered_plugin(tmp_path):
    validators_dir = tmp_path / "validators"
    validators_dir.mkdir()
    (validators_dir / "custom_check.py").write_text(
        "def validate(dataset_path, context):\n"
        "    return [('WARNING', 'test issue')]\n"
    )

    manager = PluginManager(str(tmp_path))
    manager.discover_local_plugins()
    assert len(manager.plugins) == 1

    context = PluginContext(
        dataset_path=str(tmp_path),
        schema_version="stable",
        subjects=[],
        sessions=[],
        tasks=[],
        modalities={},
    )
    issues = manager.run_plugin(manager.plugins[0], context)

    assert len(issues) == 1
    assert issues[0].message == "[custom_check] test issue"
