import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "modality_issue_to_files.py"
spec = importlib.util.spec_from_file_location("modality_issue_to_files", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod  # dataclasses looks the module up by name
spec.loader.exec_module(mod)

BASE = "https://github.com/user-attachments/files"


def _body(proposal="[blood.xlsx](%s/1/blood.xlsx)" % BASE,
          sample="[blood.tsv](%s/2/blood.tsv)" % BASE,
          privacy="- [x] The sample file contains no real participant data."):
    return (
        "### Proposal file\n\n" + proposal + "\n\n"
        "### Sample data file\n\n" + sample + "\n\n"
        "### Privacy\n\n" + privacy + "\n"
    )


def test_parses_one_upload_per_field():
    files = mod.parse_issue(_body())
    assert files.proposal_url == f"{BASE}/1/blood.xlsx"
    assert files.proposal_ext == "xlsx"
    assert files.sample_url == f"{BASE}/2/blood.tsv"
    assert files.sample_ext == "tsv"


def test_compound_sample_extension_is_kept():
    files = mod.parse_issue(_body(sample="[blood.tsv.gz](%s/2/blood.tsv.gz)" % BASE))
    assert files.sample_ext == "tsv.gz"


@pytest.mark.parametrize(
    "kwargs,needle",
    [
        (dict(proposal="no upload here"), "Proposal file"),
        (dict(sample="_No response_"), "Sample data file"),
        (dict(proposal="[a.xlsx](%s/1/a.xlsx) [b.xlsx](%s/3/b.xlsx)" % (BASE, BASE)), "exactly one"),
        (dict(proposal="[a.xlsx](https://evil.example/a.xlsx)"), "Proposal file"),
        (dict(proposal="[a.exe](%s/1/a.exe)" % BASE), "must be .xlsx"),
        (dict(proposal="[a.xlsx](%s/../1/a.xlsx)" % BASE), "'..'"),
        (dict(privacy="- [ ] The sample file contains no real participant data."), "privacy"),
    ],
)
def test_bad_issue_bodies_are_clear_errors(kwargs, needle):
    with pytest.raises(mod.IssueError) as exc:
        mod.parse_issue(_body(**kwargs))
    assert needle.lower() in str(exc.value).lower()


def test_pr_body_links_the_issue_and_carries_warnings():
    text = mod.pr_body(7, "Wrote 9 files\nWARNING: s.tsv column 'patient_name': looks like an identifier\n")
    assert "#7" in text
    assert "Closes #7" in text
    assert "patient_name" in text
    assert "draft" in text.lower()
    assert "REGISTRATION.md" in text
    assert "CI has not run on this bot commit" in text


def test_pr_body_neutralises_warning_text():
    text = mod.pr_body(7, "WARNING: `x` hi @someone [l](http://e.example)\n")
    assert "- `WARNING: 'x' hi @someone [l](http://e.example)`" in text
    assert "``" not in text


def test_pr_body_subcommand_reads_issue_number_and_log(tmp_path, monkeypatch, capsys):
    log = tmp_path / "propose.log"
    log.write_text("WARNING: x\n", encoding="utf-8")
    monkeypatch.setenv("ISSUE_NUMBER", "12")
    monkeypatch.setenv("LOG_FILE", str(log))
    assert mod.main(["pr-body"]) == 0
    out = capsys.readouterr().out
    assert "#12" in out and "WARNING: x" in out
