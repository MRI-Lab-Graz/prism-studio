from __future__ import annotations

import pytest

from src.token_rewrite_rules import build_example_keep_rule, rewrite_token


def test_build_example_keep_rule_suffix_strategy():
    rule = build_example_keep_rule(
        tokens=["sub-1291003"],
        example_token="sub-1291003",
        keep_fragment="003",
        token_prefix="sub-",
    )
    assert rule["strategy"] == "suffix"
    assert rewrite_token("sub-1291003", "example_keep", rule, "sub-") == "sub-003"


def test_build_example_keep_rule_prefix_strategy():
    rule = build_example_keep_rule(
        tokens=["sub-AB1234"],
        example_token="sub-AB1234",
        keep_fragment="AB",
        token_prefix="sub-",
    )
    assert rule["strategy"] == "prefix"
    assert rewrite_token("sub-AB1234", "example_keep", rule, "sub-") == "sub-AB"


def test_build_example_keep_rule_slice_strategy_anchors_on_text():
    rule = build_example_keep_rule(
        tokens=["sub-AB1234XY"],
        example_token="sub-AB1234XY",
        keep_fragment="1234",
        token_prefix="sub-",
    )
    assert rule["strategy"] == "slice"
    assert rewrite_token("sub-AB1234XY", "example_keep", rule, "sub-") == "sub-1234"
    # A shorter token with the same anchors still resolves correctly.
    assert rewrite_token("sub-AB12XY", "example_keep", rule, "sub-") == "sub-12"


def test_build_example_keep_rule_rejects_ambiguous_example():
    with pytest.raises(ValueError, match="Pattern is not unique"):
        build_example_keep_rule(
            tokens=["sub-103103"],
            example_token="sub-103103",
            keep_fragment="103",
            token_prefix="sub-",
        )


def test_build_example_keep_rule_rejects_fragment_not_in_example():
    with pytest.raises(ValueError, match="is not part of"):
        build_example_keep_rule(
            tokens=["sub-001"],
            example_token="sub-001",
            keep_fragment="DEMO001",
            token_prefix="sub-",
        )


def test_build_example_keep_rule_add_only_prepend():
    rule = build_example_keep_rule(
        tokens=["sub-001"],
        example_token="sub-001",
        keep_fragment=None,
        token_prefix="sub-",
        add_text="DEMO",
        add_position="prepend",
    )
    assert rewrite_token("sub-001", "example_keep", rule, "sub-") == "sub-DEMO001"


def test_build_example_keep_rule_add_only_append():
    rule = build_example_keep_rule(
        tokens=["sub-001"],
        example_token="sub-001",
        keep_fragment=None,
        token_prefix="sub-",
        add_text="PILOT",
        add_position="append",
    )
    assert rewrite_token("sub-001", "example_keep", rule, "sub-") == "sub-001PILOT"


def test_build_example_keep_rule_requires_keep_or_add():
    with pytest.raises(ValueError, match="part to keep and/or a part to add"):
        build_example_keep_rule(
            tokens=["sub-001"],
            example_token="sub-001",
            keep_fragment=None,
            token_prefix="sub-",
        )


def test_build_example_keep_rule_add_text_rejects_invalid_chars():
    with pytest.raises(ValueError, match="letters and numbers"):
        build_example_keep_rule(
            tokens=["sub-001"],
            example_token="sub-001",
            keep_fragment=None,
            token_prefix="sub-",
            add_text="DEMO_1",
        )


def test_build_example_keep_rule_uses_arbitrary_token_prefix():
    """The rule builder must work for any token prefix (e.g. ses-), not just
    sub-, since it is shared between the subject and session rewriters."""
    rule = build_example_keep_rule(
        tokens=["ses-baseline1"],
        example_token="ses-baseline1",
        keep_fragment="baseline",
        token_prefix="ses-",
    )
    assert rule["strategy"] == "prefix"
    assert rewrite_token("ses-baseline1", "example_keep", rule, "ses-") == "ses-baseline"


def test_rewrite_token_last3_extracts_last_three_digits():
    assert rewrite_token("sub-1293167", "last3", rule=None, token_prefix="sub-") == "sub-167"


def test_rewrite_token_last3_returns_unchanged_when_no_digits():
    assert rewrite_token("ses-followup", "last3", rule=None, token_prefix="ses-") == "ses-followup"
