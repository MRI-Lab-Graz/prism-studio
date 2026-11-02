"""The Projects page explains time vs content where the question is asked."""

from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "app" / "templates" / "includes" / "projects" / "study_metadata.html"


def test_the_page_explains_both_answers_and_the_folder_names():
    html = TEMPLATE.read_text(encoding="utf-8")
    info = html.split('id="smSDSessionLabelsInfo"', 1)[1].split("</div>", 1)[0]

    assert "same order for everyone" in info
    assert "order differs per participant" in info
    assert "ses-rested, not ses-2" in info
