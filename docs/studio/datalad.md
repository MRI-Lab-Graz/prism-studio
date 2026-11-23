# DataLad

The DataLad page switches DataLad on for the open project and saves snapshots of it. Open it from the
**DataLad** item in the navbar; it is always there, also before a project is open. The yellow number next
to it counts the changes that are not saved yet.

Sending your saves to a server, getting what others saved, getting the data of a copy and opening a project
from a server are done in Worldline Desktop, the app for
version control of research data. It checks your data with `prism-validator` before every save, and it will
not send a project that tracks `sourcedata/` to a public host. [Install Worldline Desktop](https://worldline-desktop.readthedocs.io/en/latest/install.html) to use it; PRISM does not open it for you.

The page shows **one next step** for the project. Which step that is, is decided by the backend:
`prism_tools.py datalad status --project <root>` prints the same advice (`--json` gives what the page reads).
Every button runs a `prism_tools.py datalad ...` command; the page only starts it and shows the result.

## The next step

| What the project looks like | The page offers | CLI |
|---|---|---|
| No project open | nothing (open a project first) | |
| DataLad is not installed | **Check this computer** | `datalad doctor` |
| DataLad is off | **Enable DataLad** | `datalad enable --yes` |
| DataLad is on, but subject datasets are not registered yet | **Finish enabling DataLad** | `datalad enable --yes` |
| DataLad is on, no server yet | **Save** (sharing is done in Worldline Desktop) | `datalad save` |
| Unsaved changes | **Save** | `datalad save` |
| Everything saved | nothing; use Worldline Desktop to send | |

The page counts the subject datasets that are not registered yet (`datalad status --check-nested`; it takes about a
second, so the navbar's count does not ask for it). If some are left, for example after an interrupted enable, the
page offers **Finish enabling DataLad**, which registers them all.

## The buttons

- **Enable DataLad** switches DataLad on for the project and saves a first snapshot. If your name and email are
  not set yet, a pop-up asks for them once (they are stored in your computer's git settings, never in the
  project; see [DataLad](../DATALAD.md#who-signs-your-snapshots)).
- **Save** asks for a short description and saves a snapshot of the project.
- **Check this computer** runs `datalad doctor` (git, git-annex, DataLad, name and email).
- **Your name and email (Settings)** opens the Settings page.

## Validation errors: Save anyway

Only a valid dataset is saved. If the project has validation errors, **Save** lists them and asks *Save
anyway?*. If you say yes, the snapshot is saved and its message ends with `[saved with N validation error(s)]`,
so the history shows it (`datalad save --allow-invalid`). Fix the errors where you can; the acknowledgement is
for the cases where a known error must not block the team.

## CLI equivalents

```bash
python prism_tools.py datalad status --project /path/to/project --check-nested
python prism_tools.py datalad enable --project /path/to/project --yes
python prism_tools.py datalad save --project /path/to/project --message "After pilot week 1"
python prism_tools.py datalad doctor
python prism_tools.py datalad identity --name "Ada Lovelace" --email ada@example.org
```
