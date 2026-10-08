from urllib.parse import parse_qs, unquote, urlsplit

from src.template_share import SHARE_ADDRESS, share_mail

TEMPLATE = {"Study": {"OriginalName": "Händigkeit & Co", "TaskName": "haendigkeit",
                      "Citation": "Oldfield 1971", "Category": "Handedness"},
            "Technical": {"SoftwarePlatform": "LimeSurvey", "SoftwareVersion": "6"}}


def test_mail_goes_to_the_prism_team_with_the_title_in_the_subject():
    mail = share_mail(TEMPLATE, "survey-haendigkeit.json")
    assert mail["to"] == SHARE_ADDRESS == "mri-lab@uni-graz.at"
    assert "Händigkeit & Co" in mail["subject"]


def test_body_names_file_citation_and_asks_for_the_attachment():
    body = share_mail(TEMPLATE, "survey-haendigkeit.json")["body"]
    assert "survey-haendigkeit.json" in body and "Oldfield 1971" in body
    assert "attach" in body.lower()


def test_mailto_is_url_safe_and_round_trips():
    mail = share_mail(TEMPLATE, "survey-haendigkeit.json")
    parts = urlsplit(mail["mailto"])
    assert parts.scheme == "mailto" and unquote(parts.path) == SHARE_ADDRESS
    query = parse_qs(parts.query)
    assert query["subject"] == [mail["subject"]] and query["body"] == [mail["body"]]


def test_missing_study_block_still_builds():
    mail = share_mail({}, "survey-x.json")
    assert "survey-x.json" in mail["subject"] and "not given" in mail["body"]
