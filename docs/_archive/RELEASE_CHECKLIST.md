# PRISM Release Checklist (Minimum Quality Bar)

Use this checklist before merging to `main` or creating a release tag.

## 1) Core quality gates

- [ ] `source .venv/bin/activate`
- [ ] `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest-modularity,linting,ruff,mypy --no-fix`
- [ ] `bash scripts/ci/run_runtime_gate.sh`

## 2) Manual web smoke test (10 minutes)

- [ ] Open `/` and verify homepage renders (no 500)
- [ ] Open Projects page and set/select a project
- [ ] Verify navbar links: Home, Projects, Validator, Converter, Tools
- [ ] Tools → Template Editor opens correctly
- [ ] Projects flows: participants, sessions, study metadata, sourcedata, methods (load + save once)
- [ ] Tools flows: converter, recipes, file browser, LimeSurvey conversion, save-to-project
- [ ] Browser DevTools Network: no new 404/500 for `/api/projects/*`, `/api/limesurvey-*`, `/api/recipes-*`

## 3) Security hygiene (lightweight)

- [ ] No credentials, tokens, API keys, or personal secrets in changed files
- [ ] New file/path inputs are validated (no unsafe path traversal)
- [ ] New uploads use safe filename handling and type checks
- [ ] No shell command execution from raw user input

## 4) Documentation hygiene

- [ ] Update docs for user-visible behavior changes
- [ ] Add brief changelog/roadmap note for non-trivial refactors
- [ ] Keep error messages actionable for non-programmers

## 5) Merge readiness

- [ ] CI is green on PR
- [ ] Reviewer can follow the change scope from PR description
- [ ] If behavior changed, include "how to test" notes in PR

---

This project is research software for the community. The goal is reliability, clarity, and reproducibility over complexity.
