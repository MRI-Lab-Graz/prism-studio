# File Management

Bulk rename, reorganize, convert, and delete files already inside your project.
Requires an active project. Every action here follows a **preview-first** pattern —
you run a dry preview, then a separate, explicit apply step; nothing mutates on the
first click.

Four tabs:

## Rename Filenames

Three sub-tools:

- **Filename Renamer** — build a rename rule "by example" against selected files or a
  folder, **Preview renames**, then either **Copy to Project** or **Rename & Download**
  (as a ZIP).
- **Rename Subject IDs (Current Project)** — **Preview**, then **Apply Rename**.
  Confirmation dialog: *"Apply this subject ID rewrite mapping to the current project
  and update internal metadata links?"* (with an extra warning if a many-to-one merge
  is enabled).
- **Edit BIDS Filename Parts (Current Project)** — rename or delete one filename
  entity (radio: Rename/Delete), **Preview**, then **Apply Rewrite**. Confirmation:
  *"Apply this rewrite to modality '\<x\>' and delete/rename \<part\>...?"*

## Organize Folders (Copy)

Copy-only reorganization into `sub-<label>/ses-<label>/<modality>/` — the card header
is explicit: **"Folder Organizer (Copy Only)"**. There is no move/delete here, only
**Dry Run** then **Copy to Project**. Your source files are never touched.

## Wide to Long

Upload a CSV/TSV/XLSX file, set the ID column and optional session/run indicators,
**Preview Output**, then **Convert & Save to Project** — writes into
`sourcedata/wide_to_long/`.

## Delete Files

Filter by modality, BIDS entity, and subject, then **Preview**, then **Delete Files**.
Confirmation: *"Permanently delete the previewed files from this project? This action
cannot be undone."* The Delete button is disabled until a preview has been run. The
panel also warns that `participants.tsv` is **not** automatically updated when you
delete subject files, and that DataLad history is updated if the project is tracked.

## Every action is a backend command

Nothing here mutates files client-side — every apply action posts to a Flask API
route (e.g. `/api/file-management/subject-rewrite`, `/api/file-management/entity-rewrite`,
`/api/file-management/wide-to-long`, `/api/file-management/delete`) and the frontend
only renders the result. Long-running rewrites (subject ID rename, entity rewrite) run
as async jobs with status polling and a Cancel option.

## What's next

- [Projects](projects.md)
- [Validator](validator.md) — re-run validation after any rename/delete pass
