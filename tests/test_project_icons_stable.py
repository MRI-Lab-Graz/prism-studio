from src.project_icons import resolve_project_icon


def test_icon_without_project_json_is_stable(tmp_path):
    (tmp_path / "project.json").write_text("{}")
    icons = {resolve_project_icon(tmp_path, persist_when_missing=False) for _ in range(20)}
    assert len(icons) == 1
    assert (tmp_path / "project.json").read_text() == "{}"  # opening doesn't write
