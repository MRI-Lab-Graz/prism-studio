"""Prefilled mail for sharing a new template with the PRISM team."""

from urllib.parse import quote

SHARE_ADDRESS = "mri-lab@uni-graz.at"


def share_mail(template: dict, filename: str) -> dict:
    """{to, subject, body, mailto} for sending `filename` to the PRISM team."""
    study = template.get("Study") or {}
    title = study.get("OriginalName") or study.get("TaskName") or filename
    subject = f"PRISM template share: {title}"
    body = "\n".join([
        "Hello PRISM team,",
        "",
        "I would like to share this template for the library.",
        f"Title: {title}",
        f"File: {filename}",
        f"Citation: {study.get('Citation') or 'not given'}",
        "",
        "Please attach the downloaded file to this mail before sending.",
        "",
        "I understand the template is checked, including its copyright status, before it is added.",
    ])
    mailto = f"mailto:{SHARE_ADDRESS}?subject={quote(subject, safe='')}&body={quote(body, safe='')}"
    return {"to": SHARE_ADDRESS, "subject": subject, "body": body, "mailto": mailto}
