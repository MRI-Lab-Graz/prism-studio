"""LimeSurvey import: one PRISM template per questionnaire (spec 2026-10-07)."""

from __future__ import annotations

from pathlib import Path

import defusedxml.ElementTree as ET

from src.converters.limesurvey import _parse_answers_into_questions

FIXTURE = Path(__file__).parent / "data" / "limesurvey_four_questionnaires.lss"


def _get_text(element, tag):
    child = element.find(tag)
    return (child.text if child is not None else "") or ""


def test_ls6_answer_labels_come_from_answer_l10ns():
    root = ET.fromstring(
        """<document>
          <answers><rows><row><aid>7</aid><qid>1</qid><code>A1</code></row></rows></answers>
          <answer_l10ns><rows>
            <row><aid>7</aid><answer>selten</answer><language>de</language></row>
            <row><aid>7</aid><answer>rarely</answer><language>en</language></row>
          </rows></answer_l10ns>
        </document>"""
    )
    questions_map = {"1": {"levels": {}}}

    _parse_answers_into_questions(root, questions_map, _get_text)

    assert questions_map["1"]["levels"] == {"A1": {"de": "selten", "en": "rarely"}}
