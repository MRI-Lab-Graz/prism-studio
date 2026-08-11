import pytest

from src.converters.survey_lsa import _apply_lsa_structural_matching


class _FakeMatch:
    def __init__(self, is_participants=False, confidence="exact", template_key="panas",
                 overlap_count=5, template_items=5):
        self.is_participants = is_participants
        self.confidence = confidence
        self.template_key = template_key
        self.overlap_count = overlap_count
        self.template_items = template_items


class _FakeUnmatchedGroupsError(ValueError):
    def __init__(self, unmatched, message):
        super().__init__(message)
        self.unmatched = unmatched


def test_no_lsa_analysis_is_a_no_op():
    templates = {}
    item_to_task = {}
    warnings = _apply_lsa_structural_matching(
        templates=templates,
        item_to_task=item_to_task,
        participant_columns_lower=set(),
        lsa_analysis=None,
        survey_filter=None,
        add_matched_template_fn=lambda *a: None,
        unmatched_groups_error_cls=_FakeUnmatchedGroupsError,
    )
    assert warnings == []
    assert templates == {}


def test_survey_filter_set_skips_structural_matching_entirely():
    add_matched_calls = []
    lsa_analysis = {"groups": {"g1": {"match": _FakeMatch(confidence="exact")}}}

    _apply_lsa_structural_matching(
        templates={},
        item_to_task={},
        participant_columns_lower=set(),
        lsa_analysis=lsa_analysis,
        survey_filter="panas",
        add_matched_template_fn=lambda *a: add_matched_calls.append(a),
        unmatched_groups_error_cls=_FakeUnmatchedGroupsError,
    )
    assert add_matched_calls == []


def test_exact_confidence_match_calls_add_matched_template_with_no_warning():
    add_matched_calls = []
    lsa_analysis = {"groups": {"g1": {"match": _FakeMatch(confidence="exact")}}}

    warnings = _apply_lsa_structural_matching(
        templates={},
        item_to_task={},
        participant_columns_lower=set(),
        lsa_analysis=lsa_analysis,
        survey_filter=None,
        add_matched_template_fn=lambda *a: add_matched_calls.append(a),
        unmatched_groups_error_cls=_FakeUnmatchedGroupsError,
    )
    assert len(add_matched_calls) == 1
    assert warnings == []


def test_medium_confidence_match_calls_add_matched_template_and_warns():
    lsa_analysis = {
        "groups": {"g1": {"match": _FakeMatch(confidence="medium", template_key="phq9")}}
    }

    warnings = _apply_lsa_structural_matching(
        templates={},
        item_to_task={},
        participant_columns_lower=set(),
        lsa_analysis=lsa_analysis,
        survey_filter=None,
        add_matched_template_fn=lambda *a: None,
        unmatched_groups_error_cls=_FakeUnmatchedGroupsError,
    )
    assert len(warnings) == 1
    assert "medium confidence" in warnings[0]
    assert "phq9" in warnings[0]


def test_unmatched_group_raises_the_injected_error_class():
    lsa_analysis = {
        "groups": {
            "g1": {"match": None, "item_codes": {"q1", "q2"}, "prism_json": {"q1": {}, "q2": {}}}
        }
    }

    with pytest.raises(_FakeUnmatchedGroupsError) as exc_info:
        _apply_lsa_structural_matching(
            templates={},
            item_to_task={},
            participant_columns_lower=set(),
            lsa_analysis=lsa_analysis,
            survey_filter=None,
            add_matched_template_fn=lambda *a: None,
            unmatched_groups_error_cls=_FakeUnmatchedGroupsError,
        )
    assert len(exc_info.value.unmatched) == 1


def test_is_participants_group_registers_participant_columns_not_a_template():
    add_matched_calls = []
    lsa_analysis = {
        "groups": {
            "g1": {
                "match": _FakeMatch(is_participants=True),
                "questions": {"age": {}, "sex": {}},
            }
        }
    }

    _apply_lsa_structural_matching(
        templates={},
        item_to_task={},
        participant_columns_lower=set(),
        lsa_analysis=lsa_analysis,
        survey_filter=None,
        add_matched_template_fn=lambda *a: add_matched_calls.append(a),
        unmatched_groups_error_cls=_FakeUnmatchedGroupsError,
    )
    assert add_matched_calls == []
