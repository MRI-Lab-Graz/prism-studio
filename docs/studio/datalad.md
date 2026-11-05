# DataLad

The DataLad page keeps snapshots of the open project and shares them with your team through the lab
server. Open it from the **DataLad** item in the navbar; it is always there, also before a project is
open. The yellow number next to it counts the changes that are not saved yet.

The page shows **one next step** for the project and puts everything else under **More**. Which step that
is, is decided by the backend: `prism_tools.py datalad status --project <root>` prints the same advice
(`--json` gives what the page reads). Every button runs a `prism_tools.py datalad ...` command; the page only
starts it and shows the result.

## The next step

| What the project looks like | The page offers | CLI |
|---|---|---|
| No project open | **Open from server...** | `datalad open-from-server` |
| DataLad is not installed | **Check this computer** | `datalad doctor` |
| DataLad is off | **Enable DataLad** (and *Open from server...* if you are joining a team project) | `datalad enable --yes` |
| DataLad is on, but subject datasets are not registered yet | **Finish enabling DataLad** | `datalad enable --yes` |
| DataLad is on, no server yet | **Put on server...**, and *Save* | `datalad put-on-server`, `datalad save` |
| Unsaved changes, server known | **Save**, then *Sync now* | `datalad save`, `datalad sync` |
| Everything saved, server known | **Sync now** | `datalad sync` |

The page counts the subject datasets that are not registered yet (`datalad status --check-nested`; it takes about a
second, so the navbar's count does not ask for it). If some are left, for example after an interrupted enable, the
page offers **Finish enabling DataLad**, which registers them all.

No server yet is not an error: your snapshots stay on this computer until you put the project on a server.
A server that cannot be reached is a plain notice; you can keep working and saving, and sync when it is back.

## The buttons

- **Enable DataLad** switches DataLad on for the project and saves a first snapshot. If your name and email are
  not set yet, a pop-up asks for them once (they are stored in your computer's git settings, never in the
  project; see [DataLad](../DATALAD.md#who-signs-your-snapshots)).
- **Save** asks for a short description and saves a snapshot of the project.
- **Sync now** first gets what others have saved on the server, then sends your saved changes. Nothing is ever
  merged: if you and someone else both changed the project, Sync stops and changes nothing.
- **Put on server...** asks for a location (a folder on the lab server as `user@host:/path`, `ssh://host/path`,
  or a local or network folder) and creates the project there. *Browse...* only looks at folders on an SSH server
  (type `user@host:` first); a local or network folder has to be typed in. A
  location that already holds a project is refused: open it from the server instead.
- **Open from server...** asks for the location and a new or empty folder on this computer, copies the project
  there and opens it. The subject data is not copied yet; use *Get data* for what you need.
- Long steps (sync, put on server, open from server, get data) show a progress bar with **Cancel**.

## More

- **Get latest** brings in what others have saved on the server, without sending anything
  (`datalad update`). The page also does this once when it opens a project, in the background.
- **Get data...** fetches the content of the files you choose from the server (`datalad get-data`). The
  choices are the same as the export's: top-level folders (derivatives, sourcedata, code, analysis) and
  subjects, sessions and modalities. It starts with the command's defaults: everything except `sourcedata/`
  and `analysis/`. Uncheck what you do not need.
- **Check this computer** tests Git, git-annex, DataLad, your SSH key and, if a location is filled in, the
  login to the server (`datalad doctor`).
- **Your name and email (Settings)** opens Settings, where the name and email that sign your snapshots are set.

## Validation errors: Save anyway, Send anyway

Only a valid dataset is saved or sent. If the project has validation errors:

- **Save** lists them and asks *Save anyway?*. If you say yes, the snapshot is saved and its message ends
  with `[saved with N validation error(s)]`, so the history shows it (`datalad save --allow-invalid`).
- **Sync now** and **Put on server...** stop and list the errors, with a button *Send anyway, I understand this
  dataset has N errors*. It repeats the same step with the acknowledgement (`--allow-invalid`); the push is
  recorded in the audit log as `pushed_with_errors` with the error count.

Fix the errors where you can; the acknowledgement is for the cases where a known error must not block the team.

## Joining a team project, step by step

1. The first person opens the project, clicks **Enable DataLad**, then **Put on server...** and enters the
   lab server location.
2. Everybody else clicks **Open from server...** (no project needs to be open), enters the same location and a
   new folder on their computer, and then **Get data...** for the subjects they work on.
3. From then on: work, **Save**, **Sync now**.

`sourcedata/` (raw data, possibly with names or emails) travels with every push: use the internal lab server
only, never a public host. Web addresses are refused.

## CLI equivalents

```bash
python prism_tools.py datalad status --project /path/to/project --check-server --check-nested --validate
python prism_tools.py datalad enable --project /path/to/project --yes
python prism_tools.py datalad save --project /path/to/project --message "After pilot week 1"
python prism_tools.py datalad put-on-server --project /path/to/project --location user@host:/srv/datalad/study
python prism_tools.py datalad open-from-server --location user@host:/srv/datalad/study --target /path/to/new-folder
python prism_tools.py datalad sync --project /path/to/project
python prism_tools.py datalad update --project /path/to/project
python prism_tools.py datalad get-data --project /path/to/project --exclude-session 2
python prism_tools.py datalad doctor --url user@host:/srv/datalad/study
```

See [DataLad](../DATALAD.md) for how snapshots, the save gate and the server work together.
