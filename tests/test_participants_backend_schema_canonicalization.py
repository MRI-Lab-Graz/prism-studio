"""Unit tests for src.participants_backend's participants.json schema
canonicalization helpers (is_participant_id_field,
merge_participants_schema_field, canonicalize_participants_schema_keys).

Extracted from app/src/web/blueprints/projects_participants_handlers.py so
the CLI's `participants save-schema` command and the Studio GUI's
Neurobagel "Save Annotations" action share one implementation. See
docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md, P2.
"""

from src.participants_backend import (
    canonicalize_participants_schema_keys,
    is_participant_id_field,
    merge_participants_schema_field,
)


class TestIsParticipantIdField:
    def test_matches_by_name(self):
        assert is_participant_id_field("participant_id") is True
        assert is_participant_id_field("ParticipantID") is True

    def test_matches_by_neurobagel_annotation(self):
        field = {"Annotations": {"IsAbout": {"TermURL": "nb:ParticipantID"}}}
        assert is_participant_id_field("Code", field) is True

    def test_matches_by_label_fallback(self):
        field = {"Annotations": {"IsAbout": {"Label": "Subject ID"}}}
        assert is_participant_id_field("Code", field) is True

    def test_unrelated_field_is_false(self):
        assert is_participant_id_field("age") is False
        assert is_participant_id_field("sex", {"Description": "Sex"}) is False


class TestMergeParticipantsSchemaField:
    def test_fills_missing_keys_from_incoming(self):
        existing = {"Description": ""}
        incoming = {"Description": "A description", "DataType": "string"}
        merged = merge_participants_schema_field(existing, incoming)
        assert merged["Description"] == "A description"
        assert merged["DataType"] == "string"

    def test_does_not_overwrite_existing_nonblank_value(self):
        existing = {"Description": "Original"}
        incoming = {"Description": "Incoming"}
        merged = merge_participants_schema_field(existing, incoming)
        assert merged["Description"] == "Original"

    def test_deep_merges_annotations(self):
        existing = {"Annotations": {"IsAbout": {"TermURL": "nb:ParticipantID"}}}
        incoming = {"Annotations": {"IsAbout": {"Label": "ID"}}}
        merged = merge_participants_schema_field(existing, incoming)
        assert merged["Annotations"]["IsAbout"] == {
            "TermURL": "nb:ParticipantID",
            "Label": "ID",
        }


class TestCanonicalizeParticipantsSchemaKeys:
    def test_folds_aliased_id_field_into_participant_id(self):
        schema = {
            "Code": {
                "Annotations": {"IsAbout": {"TermURL": "nb:ParticipantID"}},
                "Description": "Subject code",
            }
        }
        result = canonicalize_participants_schema_keys(schema)
        assert "Code" not in result
        assert result["participant_id"]["Description"] == "Subject code"

    def test_non_id_fields_pass_through_unchanged(self):
        schema = {"age": {"Description": "Age in years"}}
        result = canonicalize_participants_schema_keys(schema)
        assert result == schema

    def test_merges_when_both_explicit_and_aliased_id_present(self):
        schema = {
            "participant_id": {"Description": "Unique participant identifier"},
            "Code": {
                "Annotations": {"IsAbout": {"TermURL": "nb:ParticipantID"}},
                "Description": "",
            },
        }
        result = canonicalize_participants_schema_keys(schema)
        assert "Code" not in result
        assert result["participant_id"]["Description"] == "Unique participant identifier"

    def test_non_dict_input_returns_empty_dict(self):
        assert canonicalize_participants_schema_keys(None) == {}
        assert canonicalize_participants_schema_keys([1, 2, 3]) == {}
