# Installing an Unsigned Build + Tutorial Chapter 0 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give unsigned-binary friction its own honest, complete page (what "unsigned" means, exactly what each OS shows, how to get past it, how to verify a download, and a gentler alternative for anyone who'd rather not), and add a Tutorial Chapter 0 that walks a first-time user through the same territory as part of the guided tutorial flow, so Chapter 1 no longer silently assumes the app is already open.

**Architecture:** One new reference page (`docs/INSTALLATION_SECURITY.md`) holding the definitive unsigned-build content, linked from `docs/INSTALLATION.md`. One new tutorial chapter (`docs/TUTORIAL_BEGINNER_0_INSTALL.md`) that narrates the same territory for a first-time reader and links to the reference page for the parts that don't need repeating. No renumbering of the existing six chapters — "Chapter 0" is a prologue, matching how `TUTORIAL_BEGINNER.md` already treats its persona picker as pre-Chapter-1 content.

**Tech Stack:** Sphinx + MyST, existing `prism-chapter-grid`/`prism-persona-*` CSS classes already defined in `docs/_static/custom.css`.

**Spec:** `docs/superpowers/specs/2026-09-12-documentation-expansion-design.md` — this plan implements Section C (Installation and code signing) and Section E1 (Chapter 0) together, per the spec's explicit sequencing ("C + E1, shared content, done together").

## Global Constraints

- The RTD build must stay green after every task: `cd docs && python3 -m sphinx -b html -W --keep-going . <outdir>` (matches `.readthedocs.yaml`'s `fail_on_warning: true`).
- No Python autodoc anywhere.
- Binaries stay unsigned — this plan documents that reality, it does not attempt to change it. Do not suggest pursuing a specific signing vendor (e.g. SignPath) as part of this work; that decision, if made, belongs to a different task.
- Every factual claim about OS behavior, file names, or scripts is verified against this repository's actual build output and release history before being written — not invented from general SmartScreen/Gatekeeper knowledge alone, since exact filenames and click-paths are project-specific.
- **Markdown cross-page links use the `.md` extension, not `.html`** (`[text](Other.md)`, or `[text](Other.md#anchor)` for a specific heading). This is the house convention (verified: every existing bare cross-page Markdown link in `docs/` uses `.md`; `.html` only ever appears inside raw `<a href>` HTML tags, e.g. the chapter-grid cards). MyST's cross-reference checker treats a Markdown-syntax `.html` link as an external/broken reference and fails the build under `-W` — confirmed by dry-running this plan's own drafted content, which originally used `.html` in five places and failed with `myst.xref_missing` until fixed.
- Git commit messages end with: `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`

---

### Task 1: Write `docs/INSTALLATION_SECURITY.md`

**Files:**
- Create: `docs/INSTALLATION_SECURITY.md`

**Interfaces:**
- Consumes: nothing.
- Produces: `docs/INSTALLATION_SECURITY.md` as a link target. Task 2 links to it
  from `docs/INSTALLATION.md`; Task 3 links to it from the new Chapter 0.
  Both link to it as `INSTALLATION_SECURITY.md` (same directory, no `../`
  needed — both files live directly under `docs/`).

Verified facts this content relies on (checked in this working session,
2026-09-12 — do not re-derive from general OS knowledge, use these exact
values):

- macOS first-launch helpers, verbatim from `docs/RELEASE_NOTES_v1.18.0.md`
  and `CHANGELOG.md` (`macOS First Launch Helpers` entry): the release ZIP
  contains `Prism Studio Installer.app` (auto-detects and opens
  `PrismStudio.app`; if App Translocation prevents auto-detection, it asks
  the user to select `PrismStudio.app` once) and `Open Prism Studio.command`
  (removes the quarantine attribute from `PrismStudio.app` and starts it).
  Manual Finder fallback: right-click `PrismStudio.app` → **Open** → confirm
  **Open** in the dialog. Apple's own guide:
  https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unidentified-developer-mh40616/mac
- Windows: the release ZIP contains `PrismStudio.exe` directly (no helper
  script needed — confirmed via `scripts/build/build_windows.ps1:84-85`,
  which tells the developer to run `PrismStudio.exe` directly). SmartScreen
  shows "Windows protected your PC" with an "Unrecognized app" message;
  click **More info**, then **Run anyway** (this click-path is also
  documented, independently, in the archived
  `docs/_archive/WINDOWS_DISTRIBUTION.md:15`, which predates this page and
  describes the same underlying OS behavior for the same unsigned-build
  situation).
- Default network binding: `app/prism-studio.py:1582` defaults `--host` to
  `127.0.0.1` (localhost-only); binding to all interfaces requires an
  explicit `--allow-external` flag (`app/prism-studio.py:1594`). So a
  default launch should not trigger a Windows Firewall network prompt —
  phrase this as "if you see one" rather than "you will see one."
- Release asset names, from `docs/INSTALLATION.md`:
  `prism-studio-macOS-AppleSilicon.zip`, `prism-studio-macOS-AppleIntel.zip`,
  `prism-studio-Windows.zip`, `prism-studio-Linux.zip`, all from
  `https://github.com/MRI-Lab-Graz/prism-studio/releases/latest`.
- **No published checksums exist today.** Checked
  `.github/workflows/` (no release-signing/checksum workflow) and
  `scripts/future_features/homebrew/` (a `sha256`-computing cask-formula
  updater exists but is unwired — sits under `future_features/`, not called
  from any workflow, and its expected artifact names
  (`prism-studio-macOS-arm64.zip` etc.) don't even match the real release
  names above). Do not claim checksums are published; say plainly that they
  are not, and that the strongest verification available today is
  downloading only from the official Releases URL, never a mirror or
  forwarded link.
- Source install commands already live in `docs/INSTALLATION.md`'s "Source
  Install (Advanced)" section — link to it, do not duplicate the command
  blocks here (avoids the two copies drifting the way `CLAUDE.md` warns
  about for code; the same discipline applies to docs).

- [ ] **Step 1: Write the page**

```markdown
# Installing an Unsigned Build

PRISM Studio's prebuilt releases are not code-signed. Signing costs money
the project doesn't currently have — a Windows certificate runs
$200-500/year, and an Apple Developer Program membership is $99/year, paid
annually for as long as the software is distributed. This page explains
what that means in practice, exactly what you'll see, how to get past it,
how to check you downloaded the real thing, and an alternative if you'd
rather not click past a security warning at all.

## What "unsigned" means (and what it doesn't)

Code signing is a paid certificate a developer attaches to a build so the
operating system can show *"this came from a verified publisher"* instead
of *"this came from someone unknown."* It says nothing about whether the
software is safe — it only says who published it, in a way the OS can
check cryptographically.

An unsigned build is not a build the OS has flagged as malicious. It's a
build the OS has no publisher information for at all, so it defaults to
its most cautious warning — the same warning it would show for genuinely
unwanted software, because from the OS's point of view the two look
identical at this check. That's an unavoidable side effect of not paying
for signing, not a judgment about this specific software.

## What you'll see on macOS, and how to get past it

macOS's Gatekeeper blocks the app on first launch with a dialog saying it
"cannot be opened because the developer cannot be verified" (or "is
damaged and can't be opened" on some macOS versions — this wording is
Gatekeeper's, not a sign of a bad download). The release ZIP includes two
helpers to get past this without going through System Settings:

1. **`Prism Studio Installer.app`** — double-click it. It finds
   `PrismStudio.app` in the same folder and opens it. If macOS's App
   Translocation feature prevents that auto-detection, it asks you to
   select `PrismStudio.app` yourself, once.
2. **`Open Prism Studio.command`** — if the installer doesn't work, use
   this instead. It removes the quarantine flag macOS attaches to
   downloaded files and starts the app directly.

If neither is available or both fail, the manual route:

1. Right-click (or Control-click) `PrismStudio.app` in Finder.
2. Click **Open**.
3. Confirm **Open** in the dialog that appears.

This manual route only needs to happen once — after this first
right-click-Open, macOS remembers your choice and future launches work
normally. Apple's own guide covers the same steps with screenshots:
[Open a Mac app from an unidentified developer](https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unidentified-developer-mh40616/mac).

## What you'll see on Windows, and how to get past it

Windows Defender SmartScreen shows a blue "Windows protected your PC"
screen the first time you run `PrismStudio.exe`, naming it an
unrecognized app. To proceed:

1. Click **More info** (a small link inside the SmartScreen dialog).
2. Click **Run anyway**.

This appears once per downloaded copy of the file, not once per computer
— if you re-download a new release later, expect to see it again.

If Windows Firewall separately prompts you to allow network access when
Studio first starts: PRISM Studio listens on `127.0.0.1` (your own machine
only) by default, so this prompt is unusual for a normal launch — but if
you do see it, **Allow** is safe; it does not expose the app to your
network.

## Verifying your download

PRISM Studio does not currently publish checksums for release assets, so
there is no independent value to check your download against yet. Until
that changes, the strongest thing you can do is make sure you're
downloading from the right place at all: get every release exclusively
from
[github.com/MRI-Lab-Graz/prism-studio/releases](https://github.com/MRI-Lab-Graz/prism-studio/releases),
never from a mirror, a forwarded link, or a search result claiming to host
the same file. GitHub serves release assets directly from the repository
you can inspect yourself.

## Would rather not click past a security warning?

That's a reasonable position, and PRISM Studio doesn't require the
prebuilt release — the [Source Install](INSTALLATION.md#source-install-advanced)
section runs the same application from a `git clone` of this repository
instead, with nothing unsigned to get past. It runs a short setup script
that installs Python packages into a `.venv` folder *inside* the cloned
repository only — it does not touch anything else on your system, install
anything system-wide, or need administrator/root access.

It does need a terminal (Terminal.app on macOS, PowerShell on Windows) and
Python 3.10 or newer ([python.org/downloads](https://www.python.org/downloads/)
if you don't already have it) — a bigger one-time step than double-clicking
a ZIP, but a terminal here is just a window you paste a handful of exact
commands into, one at a time, waiting for each to finish before the next.
The commands themselves are in [Installation](INSTALLATION.md#source-install-advanced).

## What's next

- [Installation](INSTALLATION.md) — the full install guide this page is
  linked from
- [Getting Started](TUTORIAL_BEGINNER.md) — the hands-on tutorial, Chapter 0
  covers this same ground for a first-time reader
```

- [ ] **Step 2: Verify the page builds and its anchors resolve**

Run:
```bash
cd docs && python3 -m sphinx -b html -W --keep-going . /tmp/prism_docs_build_check && echo BUILD_OK
test -f /tmp/prism_docs_build_check/INSTALLATION_SECURITY.html && echo PAGE_BUILT
```
Expected: `build succeeded.`, `BUILD_OK`, `PAGE_BUILT`. This page is not
yet linked from any toctree, so Sphinx will emit an "document isn't included
in any toctree" warning — under `-W --keep-going` that fails the build.
That's expected and gets fixed in Task 2's toctree edit; if the build fails
with only that one warning, proceed to Task 2 rather than treating it as a
Task 1 defect.

- [ ] **Step 3: Commit**

```bash
git add docs/INSTALLATION_SECURITY.md
git commit -m "docs: add Installing an Unsigned Build reference page

What 'unsigned' means and doesn't, exact per-OS click-through (macOS
Gatekeeper via Prism Studio Installer.app / Open Prism Studio.command /
manual right-click-Open; Windows SmartScreen via More info -> Run
anyway), an honest statement that no checksums are published yet, and the
source-install alternative for anyone who'd rather not click past a
warning. Not yet linked from any toctree -- Task 2 wires it in.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Link the new page from `docs/INSTALLATION.md` and the toctree

**Files:**
- Modify: `docs/INSTALLATION.md` (expand the buried one-liner into a proper
  cross-reference, and add the missing Windows first-launch mention)
- Modify: `docs/index.rst` (Installation toctree)

**Interfaces:**
- Consumes: `docs/INSTALLATION_SECURITY.md` from Task 1.

- [ ] **Step 1: Expand the first-launch bullets in `docs/INSTALLATION.md`**

Find:
```
3. Extract the ZIP and start PRISM Studio from the extracted folder.
   - **macOS first launch**: if the OS blocks the app, use
     `Prism Studio Installer.app` or `Open Prism Studio.command` from the extracted
     folder, or right-click `PrismStudio.app` → Open once.
4. Confirm it worked: the interface should open automatically. If not, go to
   `http://localhost:5001`.
```

Replace with:
```
3. Extract the ZIP and start PRISM Studio from the extracted folder.
   - **macOS first launch**: if the OS blocks the app, use
     `Prism Studio Installer.app` or `Open Prism Studio.command` from the extracted
     folder, or right-click `PrismStudio.app` → Open once.
   - **Windows first launch**: if SmartScreen shows "Windows protected your PC",
     click **More info** then **Run anyway**.
4. Confirm it worked: the interface should open automatically. If not, go to
   `http://localhost:5001`.

```{note}
PRISM Studio's releases aren't code-signed (signing costs money the project
doesn't currently have) — see
[Installing an Unsigned Build](INSTALLATION_SECURITY.md) for exactly what
each OS shows, how to get past it, how to verify your download, and a
gentler alternative if you'd rather not.
```
```

- [ ] **Step 2: Add `INSTALLATION_SECURITY` to the Installation toctree**

Find (in `docs/index.rst`):
```
.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Installation

   INSTALLATION
```

Replace with:
```
.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Installation

   INSTALLATION
   INSTALLATION_SECURITY
```

- [ ] **Step 3: Build and verify**

Run:
```bash
cd docs && python3 -m sphinx -b html -W --keep-going . /tmp/prism_docs_build_check && echo BUILD_OK
grep -c "INSTALLATION_SECURITY" /tmp/prism_docs_build_check/INSTALLATION.html
```
Expected: `build succeeded.`, `BUILD_OK`, and a nonzero count (the note's
link rendered).

- [ ] **Step 4: Commit**

```bash
git add docs/INSTALLATION.md docs/index.rst
git commit -m "docs: link Installing an Unsigned Build from Installation

Also adds the Windows SmartScreen first-launch mention that was entirely
missing -- INSTALLATION.md previously covered only the macOS case.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Write Tutorial Chapter 0 and wire it into the chapter flow

**Files:**
- Create: `docs/TUTORIAL_BEGINNER_0_INSTALL.md`
- Modify: `docs/TUTORIAL_BEGINNER.md` (chapter grid, prerequisites text, toctree)
- Modify: `docs/TUTORIAL_BEGINNER_1_NEW_PROJECT.md:60-64` (its own "Launch
  Studio" step becomes redundant with Chapter 0 — replace it with a forward
  reference)

**Interfaces:**
- Consumes: `docs/INSTALLATION_SECURITY.md` from Task 1; the persona-note
  pattern already established in `docs/TUTORIAL_BEGINNER_1_NEW_PROJECT.md`
  (reused as-is, not redefined).
- Produces: `docs/TUTORIAL_BEGINNER_0_INSTALL.md`, linked as
  `TUTORIAL_BEGINNER_0_INSTALL.html` from the chapter grid.

Chapter 1 currently opens with "From a prebuilt release, open the app" as
if that were a solved, one-line problem
(`docs/TUTORIAL_BEGINNER_1_NEW_PROJECT.md:60-64`). Chapter 0 is the missing
piece before it: download, the OS blocks it, get past it, first launch,
what am I looking at.

- [ ] **Step 1: Write `docs/TUTORIAL_BEGINNER_0_INSTALL.md`**

```markdown
# Chapter 0: Install and First Launch

Chapter 0 of [Getting Started — Your First PRISM Project](TUTORIAL_BEGINNER.md).
Everything from here on assumes PRISM Studio is already open in your
browser — this chapter is what gets you there from nothing installed at
all. If Studio is already running for you, skip straight to
[Chapter 1](TUTORIAL_BEGINNER_1_NEW_PROJECT.md).

**Time:** ~10 minutes. **Outcome:** PRISM Studio open at
`http://localhost:5001`, ready for Chapter 1.

```{mermaid}
flowchart LR
    A["Download the ZIP<br/>for your OS"] --> B["Extract it"]
    B --> C["Start the app<br/>(OS may block it once)"]
    C --> D["Studio opens at<br/>localhost:5001"]
```

## 1. Download

Go to the
[latest release page](https://github.com/MRI-Lab-Graz/prism-studio/releases/latest)
and download the ZIP for your operating system:

| Your computer | Download |
|---|---|
| Mac with Apple Silicon (M1/M2/M3/M4) | `prism-studio-macOS-AppleSilicon.zip` |
| Mac with an Intel chip | `prism-studio-macOS-AppleIntel.zip` |
| Windows | `prism-studio-Windows.zip` |
| Linux | `prism-studio-Linux.zip` |

Not sure which Mac chip you have? Apple menu → **About This Mac** — anything
saying "Apple M..." is Apple Silicon, "Intel" is Intel.

## 2. Extract it

Extract the ZIP to a folder you'll remember — your Desktop or Documents is
fine. You'll start PRISM Studio from inside this extracted folder every
time, so it's worth keeping it somewhere you won't accidentally delete.

## 3. Start it — and get past the security warning

Open the extracted folder and start the app. The first time, your
operating system will very likely show a warning, because this build isn't
code-signed (that costs money the project doesn't have yet — see
[Installing an Unsigned Build](INSTALLATION_SECURITY.md) for the full
explanation if you're curious). This is expected, not a sign anything is
wrong.

**On macOS**, double-click `Prism Studio Installer.app` in the extracted
folder — it finds and opens the app for you. If that doesn't work, try
`Open Prism Studio.command` instead. If neither is present, right-click
`PrismStudio.app` → **Open** → confirm **Open** in the dialog.

**On Windows**, double-click `PrismStudio.exe`. When SmartScreen shows
"Windows protected your PC," click **More info**, then **Run anyway**.

**On Linux**, run the extracted app from a terminal.

This warning only appears on first launch. Once you've gotten past it,
starting PRISM Studio again later is a normal double-click.

## 4. What you're looking at

A browser window opens automatically at `http://localhost:5001` — that's
PRISM Studio itself, running as a small local web server on your own
machine (nothing here is uploaded anywhere). If the browser doesn't open by
itself, open that address manually.

![PRISM Studio landing page](_static/screenshots/prism-studio-landing-create.png)

This is the **Home** screen — every session starts here. From here,
Chapter 1 begins with **Create or Open a Project**.

```{note}
Closing the browser tab does not stop PRISM Studio — it keeps running as a
local server until you close the terminal window it launched (or, on
macOS/Windows, quit the app itself). If you don't see this terminal/console
window, look for it in your taskbar or Dock — some launch paths minimize it.
```

## What's next

[Chapter 1: Create a Project](TUTORIAL_BEGINNER_1_NEW_PROJECT.md) —
everything from here uses the app you just opened.
```

- [ ] **Step 2: Add Chapter 0 to the chapter grid in `docs/TUTORIAL_BEGINNER.md`**

Find:
```
<div class="prism-chapter-grid">
  <a class="prism-chapter-card" href="TUTORIAL_BEGINNER_1_NEW_PROJECT.html">
    <span class="prism-chapter-icon">1</span>
```

Replace with:
```
<div class="prism-chapter-grid">
  <a class="prism-chapter-card" href="TUTORIAL_BEGINNER_0_INSTALL.html">
    <span class="prism-chapter-icon">0</span>
    <span class="prism-chapter-title">Install and First Launch</span>
    <span class="prism-chapter-outcome">PRISM Studio open and ready to use</span>
    <span class="prism-chapter-time">~10 min</span>
  </a>
  <a class="prism-chapter-card" href="TUTORIAL_BEGINNER_1_NEW_PROJECT.html">
    <span class="prism-chapter-icon">1</span>
```

- [ ] **Step 3: Update the Prerequisites section**

Find:
```
## Prerequisites

- PRISM Studio installed and launchable — see [Installation](INSTALLATION.md)
  if you haven't done this yet.
- No prior PRISM knowledge assumed. No prior BIDS knowledge assumed either;
  the chapters explain BIDS-specific terms (`sub-`, sessions, sidecars) as
  they come up.
```

Replace with:
```
## Prerequisites

- Nothing installed yet is fine — [Chapter 0](TUTORIAL_BEGINNER_0_INSTALL.md)
  covers download through first launch. Already have PRISM Studio open?
  Skip to [Chapter 1](TUTORIAL_BEGINNER_1_NEW_PROJECT.md).
- No prior PRISM knowledge assumed. No prior BIDS knowledge assumed either;
  the chapters explain BIDS-specific terms (`sub-`, sessions, sidecars) as
  they come up.
```

- [ ] **Step 4: Add `TUTORIAL_BEGINNER_0_INSTALL` to the toctree**

Find:
```
```{toctree}
:maxdepth: 1
:hidden:

TUTORIAL_BEGINNER_1_NEW_PROJECT
TUTORIAL_BEGINNER_2_PARTICIPANTS
```
```

Replace with:
```
```{toctree}
:maxdepth: 1
:hidden:

TUTORIAL_BEGINNER_0_INSTALL
TUTORIAL_BEGINNER_1_NEW_PROJECT
TUTORIAL_BEGINNER_2_PARTICIPANTS
```
```

- [ ] **Step 5: Make Chapter 1's launch step point back to Chapter 0 instead of duplicating it**

Find (in `docs/TUTORIAL_BEGINNER_1_NEW_PROJECT.md`):
```
### 1. Launch Studio

From a prebuilt release, open the app. From a source checkout:

```bash
source .venv/bin/activate && python prism-studio.py
```

Studio opens at `http://localhost:5001` on its landing page.

![PRISM Studio landing page](_static/screenshots/prism-studio-landing-create.png)

Select **Create or Open a Project** to open the **Projects** page.
```

Replace with:
```
### 1. Launch Studio

Already have PRISM Studio open from [Chapter 0](TUTORIAL_BEGINNER_0_INSTALL.md)?
Skip to step 2. Otherwise, from a source checkout:

```bash
source .venv/bin/activate && python prism-studio.py
```

Studio opens at `http://localhost:5001` on its landing page.

![PRISM Studio landing page](_static/screenshots/prism-studio-landing-create.png)

Select **Create or Open a Project** to open the **Projects** page.
```

- [ ] **Step 6: Build and verify**

Run:
```bash
cd docs && python3 -m sphinx -b html -W --keep-going . /tmp/prism_docs_build_check && echo BUILD_OK
test -f /tmp/prism_docs_build_check/TUTORIAL_BEGINNER_0_INSTALL.html && echo PAGE_BUILT
grep -c "TUTORIAL_BEGINNER_0_INSTALL" /tmp/prism_docs_build_check/TUTORIAL_BEGINNER.html
```
Expected: `build succeeded.`, `BUILD_OK`, `PAGE_BUILT`, and a nonzero count
(the chapter grid card links to it).

- [ ] **Step 7: Commit**

```bash
git add docs/TUTORIAL_BEGINNER_0_INSTALL.md docs/TUTORIAL_BEGINNER.md docs/TUTORIAL_BEGINNER_1_NEW_PROJECT.md
git commit -m "docs: add tutorial Chapter 0 (Install and First Launch)

Chapter 1 previously opened assuming the app was already running.
Chapter 0 covers download, the OS security warning, first launch, and
orientation to the Home screen -- kept as chapter '0' rather than
renumbering the existing six chapters. Links out to Installing an
Unsigned Build for the full explanation rather than duplicating it.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Plan-level verification

After all three tasks:

```bash
cd docs && python3 -m sphinx -b html -W --keep-going . /tmp/prism_docs_build_check && echo BUILD_OK
# Every OS-specific filename mentioned should match a real build artifact name
grep -o "prism-studio-[A-Za-z.-]*\.zip\|PrismStudio\.exe\|PrismStudio\.app\|Prism Studio Installer\.app\|Open Prism Studio\.command" \
  docs/INSTALLATION_SECURITY.md docs/TUTORIAL_BEGINNER_0_INSTALL.md | sort -u
```

Expected: `BUILD_OK`, and every filename printed matches one already
verified in Task 1's research notes above (no invented filenames should
appear). Read through both new pages once as a first-time user would,
start to finish, and confirm the click-path in each matches what a real
unsigned build actually does on that OS — this is the one property no grep
can check.
