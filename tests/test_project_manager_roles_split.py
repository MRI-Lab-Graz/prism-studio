from src.project_manager import ProjectManager


def test_contact_roles_string_splits_on_semicolon_and_newline():
    pm = ProjectManager()
    author = pm._normalize_contact_author(
        {"name": "Ada Lovelace", "roles": "Investigation; chef\nMethodology"}
    )
    assert author["roles"] == ["Investigation", "chef", "Methodology"]


def test_merge_author_entries_splits_role_strings_on_semicolon():
    pm = ProjectManager()
    merged = pm._merge_author_entries(
        {"name": "Ada Lovelace", "roles": "Investigation; chef"},
        {"name": "Ada Lovelace", "roles": "Methodology"},
    )
    assert merged["roles"] == ["Investigation", "chef", "Methodology"]
