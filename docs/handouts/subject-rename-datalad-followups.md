# Subject rename on DataLad datasets: follow-ups

Found 2026-11-20 renaming 116 subjects in a cloned dataset (`DAB`, every `sub-*` a subdataset).
The save-gate part is fixed (`fix/save-gate-renamed-subject-dataset`). Open:

1. **Resumable rename.** A rename that fails partway leaves the subdataset and the superproject
   half-moved (old path removed from the index, new one unregistered). A retry then fails
   (`git rm sub-134001: pathspec did not match`). Make `apply_subject_rewrite`
   (`src/repo_rewrite_datalad_runner.py`) pick up where it stopped. Failing test first.
2. **Speed.** Per subject group: `get -n`, `get`, `unlock`, scoped `save -r` = 4-5 datalad processes
   (about 500 for 116 subjects), each paying Python startup plus a hierarchy walk. The save gate is not
   the cost (full check on DAB: 0.5 s). Not measured further: add per-step timing to the log first, then
   consider batching (one `get -n` for all subjects, one superproject commit at the end).
3. **Misleading log text.** "Verifying all affected content is actually downloaded" (lines ~451, 872,
   1058) suggests a full download. The code runs `get -n` (installs subdatasets, no data) and fetches only
   the small text files it rewrites. Reword, with a test.
4. **`.gitmodules` URL after a rename.** The new path keeps the old server URL
   (`.../sub-134001`). Fine while the server repo keeps its name; decide whether Studio should say so.
5. **Terminal saves need `PRISM_TOOLS`.** The hook blocks the commit when `prism_tools` is not on PATH
   (by design). Consider documenting it in `docs/DATALAD.md`.
