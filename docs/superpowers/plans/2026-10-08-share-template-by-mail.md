# Share a New Template by Mail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After a student saves a valid template that came from an import with no library match, Studio offers to send it to mri-lab@uni-graz.at (download of the template JSON + a prefilled mail draft).

**Architecture:** One backend function (`src/template_share.py::share_mail`) builds `{to, subject, body, mailto}`. The CLI (`prism_tools.py library share-template`) and one Flask route both call it. The GUI only remembers "this import had no library match", asks after a successful save, downloads the JSON through the existing download flow and opens the mailto link.

**Tech Stack:** Python 3 (argparse CLI, Flask blueprint, pytest), browser JS ES modules (vitest).

**Spec:** `docs/superpowers/specs/2026-10-08-share-template-by-mail-design.md`

## Global Constraints

- Address: `mri-lab@uni-graz.at`, defined once as `SHARE_ADDRESS` in `src/template_share.py`.
- Share file = the template JSON itself (existing `/api/template-editor/download`); no new format, no SMTP, no server.
- Logic lives in `src/` and is reachable from the CLI; the GUI is an adapter (repo rule "one implementation").
- Do not add a same-named file under `app/src/` (dual-tree drift). Import as `src.template_share`.
- TDD: every task writes the failing test first, sees it fail, then implements.
- Commits end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Before merging: run `/ponytail:ponytail-audit` on the branch (repo rule).

## Review Focus

- Template with no `Study` block or no title/citation: mail still builds (no KeyError); body says "not given".
- Title with `&`, `#`, `?`, newlines, umlauts (e.g. "Händigkeit & Co"): mailto stays valid, round-trips through `urllib.parse.unquote`.
- Student answers No: never asked again for that template in the same session.
- Template loaded from the library or a plain JSON import (no `library_match` key in the response): never offered.
- Template with a library match (`library_match` not null): never offered.
- Save fails or is declined (overwrite prompt): no share prompt.

## File Structure

- Create `src/template_share.py` - `SHARE_ADDRESS`, `share_mail()`. One job: build the mail.
- Modify `app/src/cli/commands/library.py` - `cmd_library_share_template`.
- Modify `app/src/cli/parser.py`, `app/src/cli/dispatch.py`, `app/src/cli/entrypoint.py` - register the command.
- Modify `app/src/web/blueprints/tools_template_editor_blueprint.py` - route `/api/template-editor/share-mail`.
- Modify `app/static/js/template-editor/source-workflow.js` - remember candidate, `offerShare`, call after save.
- Tests: `tests/test_template_share.py`, `tests/test_cli_dispatch_routing.py` (+case), `tests/test_prism_tools_cli_contract.py`, `tests/test_template_editor_share_route.py`, `app/static/js/template-editor/source-workflow.test.js`.

---

### Task 1: `share_mail` backend function

**Files:**
- Create: `src/template_share.py`
- Test: `tests/test_template_share.py`

**Interfaces:**
- Produces: `SHARE_ADDRESS: str`; `share_mail(template: dict, filename: str) -> dict` with keys `to`, `subject`, `body`, `mailto` (all `str`).

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_template_share.py -q`
Expected: FAIL (`ModuleNotFoundError: src.template_share`).

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_template_share.py -q`
Expected: 4 passed. Also run `find app/src -name template_share.py` (must print nothing).

- [ ] **Step 5: Commit**

```bash
git add src/template_share.py tests/test_template_share.py
git commit -m "feat(share): build the prefilled share mail for a new template"
```

---

### Task 2: CLI `library share-template`

**Files:**
- Modify: `app/src/cli/commands/library.py` (add after `cmd_library_template_delete`)
- Modify: `app/src/cli/parser.py` (next to `template-delete`, ~line 2041)
- Modify: `app/src/cli/dispatch.py` (~line 142), `app/src/cli/entrypoint.py` (import ~line 51, handler map ~line 185)
- Test: `tests/test_cli_dispatch_routing.py`, `tests/test_prism_tools_cli_contract.py`

**Interfaces:**
- Consumes: `src.template_share.share_mail(template, filename) -> dict`.
- Produces: `cmd_library_share_template(args)`; handler key `library_share_template`; args `--input PATH`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_cli_dispatch_routing.py` add to `DISPATCH_CASES` after the `template-delete` line:

```python
    (dict(command="library", action="share-template"), "library_share_template"),
```

In `tests/test_prism_tools_cli_contract.py` add:

```python
def test_library_help_lists_share_template() -> None:
    _assert_help_contains(["library", "--help"], ["share-template"])
```

Create `tests/test_library_share_template_cli.py`:

```python
import json
from argparse import Namespace

from app.src.cli.commands.library import cmd_library_share_template


def test_prints_address_subject_and_mailto(tmp_path, capsys):
    path = tmp_path / "survey-x.json"
    path.write_text(json.dumps({"Study": {"OriginalName": "X"}}), encoding="utf-8")
    cmd_library_share_template(Namespace(input=str(path)))
    out = capsys.readouterr().out
    assert "mri-lab@uni-graz.at" in out and "PRISM template share: X" in out and "mailto:" in out
```

(If `app.src.cli.commands.library` is imported as `src.cli.commands.library` in the other CLI tests, copy their import style.)

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_cli_dispatch_routing.py tests/test_prism_tools_cli_contract.py tests/test_library_share_template_cli.py -q`
Expected: FAIL (new case, missing help entry, ImportError).

- [ ] **Step 3: Implement**

`library.py`:

```python
def cmd_library_share_template(args) -> None:
    """Print the prefilled share mail for a template file - the CLI equivalent of
    the Studio Template Editor's share offer after saving a new template."""
    from src.template_share import share_mail

    path = Path(args.input)
    template = json.loads(path.read_text(encoding="utf-8"))
    mail = share_mail(template, path.name)
    print(f"To:      {mail['to']}")
    print(f"Subject: {mail['subject']}")
    print(f"\n{mail['body']}\n")
    print(f"Mail link: {mail['mailto']}")
    print(f"Attach {path} and send it.")
```

(add `import json` at the top if missing.)

`parser.py` after the template-delete arguments:

```python
    parser_lib_share_template = subparsers_library.add_parser(
        "share-template",
        help="Print the prefilled mail for sharing a new template with the PRISM team. "
        "Matches the Studio Template Editor's share offer.",
    )
    parser_lib_share_template.add_argument("--input", required=True, help="Template JSON file to share")
```

`dispatch.py` after the `template-delete` branch:

```python
        elif args.action == "share-template":
            handlers["library_share_template"](args)
```

`entrypoint.py`: add `cmd_library_share_template,` to the import list and `"library_share_template": cmd_library_share_template,` to the handler map, next to the `library_template_delete` entries.

- [ ] **Step 4: Run to verify pass**

Run: same command as Step 2. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/src/cli src/ tests/test_cli_dispatch_routing.py tests/test_prism_tools_cli_contract.py tests/test_library_share_template_cli.py
git commit -m "feat(cli): library share-template prints the prefilled share mail"
```

---

### Task 3: Flask route `/api/template-editor/share-mail`

**Files:**
- Modify: `app/src/web/blueprints/tools_template_editor_blueprint.py` (after the download route, ~line 348)
- Test: `tests/test_template_editor_share_route.py`

**Interfaces:**
- Consumes: `share_mail`.
- Produces: `POST /api/template-editor/share-mail` JSON `{filename, template}` -> 200 `{to, subject, body, mailto}`; 400 `{error}` if `template` is not an object or `filename` is empty.

- [ ] **Step 1: Write the failing test** (client helper copied from `tests/test_template_editor_import_limesurvey_route.py`)

```python
import importlib
import os
from pathlib import Path

from flask import Flask


def _client():
    module = importlib.import_module("src.web.blueprints.tools_template_editor_blueprint")
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.secret_key = os.urandom(32)
    app.register_blueprint(module.tools_template_editor_bp)
    return app.test_client()


def test_returns_the_share_mail():
    response = _client().post("/api/template-editor/share-mail",
                              json={"filename": "survey-x.json", "template": {"Study": {"OriginalName": "X"}}})
    assert response.status_code == 200
    body = response.get_json()
    assert body["to"] == "mri-lab@uni-graz.at" and body["mailto"].startswith("mailto:")


def test_rejects_a_non_object_template_and_a_missing_filename():
    client = _client()
    assert client.post("/api/template-editor/share-mail", json={"filename": "a.json", "template": []}).status_code == 400
    assert client.post("/api/template-editor/share-mail", json={"template": {}}).status_code == 400
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_template_editor_share_route.py -q`
Expected: FAIL (404).

- [ ] **Step 3: Implement**

```python
@tools_template_editor_bp.route("/api/template-editor/share-mail", methods=["POST"])
def api_template_editor_share_mail():
    """Prefilled mail for sharing a new template. Same backend as `library share-template`."""
    from src.template_share import share_mail

    payload = request.get_json(silent=True) or {}
    filename = (payload.get("filename") or "").strip()
    template = payload.get("template")
    if not filename or not isinstance(template, dict):
        return jsonify({"error": "filename and a template object are required"}), 400
    print(f"[PRISM] CLI equivalent: python prism_tools.py library share-template --input {filename}")
    return jsonify(share_mail(_strip_template_editor_internal_keys(template), filename)), 200
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_template_editor_share_route.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add app/src/web/blueprints/tools_template_editor_blueprint.py tests/test_template_editor_share_route.py
git commit -m "feat(template-editor): share-mail route backed by template_share"
```

---

### Task 4: GUI offer after a successful save

**Files:**
- Modify: `app/static/js/template-editor/source-workflow.js` (`applyImportedTemplate` ~line 384, `saveCurrent` ~line 346, new `offerShare` after `saveCurrent`)
- Test: `app/static/js/template-editor/source-workflow.test.js`

**Interfaces:**
- Consumes: route from Task 3 via `context.apiPost`; existing `downloadCurrent(context)`.
- Produces: `export async function offerShare(context, filename)`; `context.shareCandidate` (string filename or `null`).

- [ ] **Step 1: Write the failing tests** (append to `source-workflow.test.js`; add `offerShare` to the import list and `vi` to the vitest import)

```js
describe('offerShare', () => {
    const ask = (answer) => { globalThis.confirm = vi.fn(() => answer); return globalThis.confirm; };

    it('asks nothing for a template that was not an unmatched import', async () => {
        const confirm = ask(true);
        await offerShare({ shareCandidate: null, apiPost: vi.fn() }, 'survey-x.json');
        expect(confirm).not.toHaveBeenCalled();
    });

    it('asks nothing when a different template was saved', async () => {
        const confirm = ask(true);
        await offerShare({ shareCandidate: 'survey-x.json', apiPost: vi.fn() }, 'survey-y.json');
        expect(confirm).not.toHaveBeenCalled();
    });

    it('asks once; No sends nothing and is not asked again', async () => {
        const confirm = ask(false);
        const context = { shareCandidate: 'survey-x.json', apiPost: vi.fn() };
        await offerShare(context, 'survey-x.json');
        await offerShare(context, 'survey-x.json');
        expect(confirm).toHaveBeenCalledTimes(1);
        expect(confirm.mock.calls[0][0]).toContain('mri-lab@uni-graz.at');
        expect(context.apiPost).not.toHaveBeenCalled();
        expect(context.shareCandidate).toBeNull();
    });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run app/static/js/template-editor/source-workflow.test.js`
Expected: FAIL (`offerShare` is not exported).

- [ ] **Step 3: Implement**

In `applyImportedTemplate`, after `context.currentTemplateFilename = ...` is set:

```js
  // Only a LimeSurvey import reports library_match; null there means nothing like it is in the library.
  context.shareCandidate = 'library_match' in data && !data.library_match ? context.currentTemplateFilename : null;
```

After `saveCurrent`:

```js
// Offer to mail a freshly imported, unmatched template to the PRISM team (asked once).
export async function offerShare(context, filename) {
  if (context.shareCandidate !== filename) {
    return;
  }
  context.shareCandidate = null;
  if (!confirm('Share this template with the PRISM team (mri-lab@uni-graz.at)? It will be checked, including its copyright status, before it is added to the library.')) {
    return;
  }
  await downloadCurrent(context);
  const mail = await context.apiPost('/api/template-editor/share-mail', { filename, template: context.currentTemplate });
  const link = document.createElement('a');
  link.href = mail.mailto;
  document.body.appendChild(link);
  link.click();
  link.remove();
  context.showAlert('info', 'Your mail program opened with a prefilled message. Attach the downloaded file and send it.');
}
```

In `saveCurrent`, after `await refreshTemplateList(context, { silent: true });` on the success path (inside the `try`, last line):

```js
    await offerShare(context, filename);
```

(The detached-draft early `return` above it is untouched, so that branch never offers.)

- [ ] **Step 4: Run to verify pass**

Run: `npx vitest run app/static/js/template-editor/source-workflow.test.js` then `python -m pytest tests/test_template_editor_workflow_wiring.py tests/e2e/test_template_editor_flows.py -q`
Expected: all pass (the wiring test guards source text; fix it only if it flags this change).

- [ ] **Step 5: Commit**

```bash
git add app/static/js/template-editor/source-workflow.js app/static/js/template-editor/source-workflow.test.js
git commit -m "feat(template-editor): offer to share a new template after saving it"
```

---

### Task 5: Manual check and changelog

**Files:**
- Modify: `CHANGELOG.md` (under `## [Unreleased]`)

- [ ] **Step 1: Add the changelog entry**

```markdown
### Added
- **Share a new template with the PRISM team.** After saving a template imported from LimeSurvey that has no
  library match, Studio offers to download it and open a prefilled mail to mri-lab@uni-graz.at. CLI:
  `prism_tools.py library share-template --input <file>`.
```

- [ ] **Step 2: Manual run in Studio** (this step is the owner's test)

Import `tests/data/limesurvey_four_questionnaires.lss`, load a questionnaire, fill Citation/Category, Validate, Save to Project. Expect the confirm; Yes: the JSON downloads and the mail program opens with To/Subject/Body prefilled; No: nothing, and saving again does not ask. A questionnaire with a library match, or a template loaded from the library, never asks.

- [ ] **Step 3: Full relevant test run, audit, commit**

Run: `python -m pytest tests -q -k "share or template_editor or cli" && npx vitest run`
Expected: all pass. Then `/ponytail:ponytail-audit`, apply what is worth it, commit:

```bash
git add CHANGELOG.md
git commit -m "docs: changelog for sharing a new template by mail"
```
