---
applyTo: '**'
---
# Repository Instructions

## RULE #1 — Thin Web Layer, Big Backend Engine
- `src/` is the **single canonical backend**. All business logic (validation, scoring, conversion, export) lives there.
- `app/src/` is a **thin adapter layer** only: Flask route parsing, request/response serialisation, and wiring UI to `src/` calls. No business logic may be duplicated here.
- `app/src/` files that mirror `src/` files **must import and delegate** to `src/`, not copy-paste logic. Duplicating a function in `app/src/` when `src/` already owns it is a bug.
- Every change to business logic in `src/` is complete when done there. Do **not** mirror the same change into `app/src/` — fix `app/src/` to call `src/` instead.

prism is a add-on to bids - it does not replace bids
bids-standards should not be changed
we add schmeas (like survey) that are not in bids

it's imporatnt that bids apps still work on prism datasets

Always activate .venv in your terminal before running any scripts.
missing packages should be installed via the setup script NOT manually
prism.py is the main script
Webinterface is BASED on prism.py - not a separate tool!

# runtime / execution standards
- scripts and long-running actions should be executed in the background (non-blocking) and the exact command should be visible in terminal logs
- avoid duplicate implementations between frontend and backend: business logic belongs to backend, frontend is UX only

# making changes to prism
- backend code is in src, frontend code in under app/src !!
- frontend code is always executing backend code - so if you are making changes to the frontend, make sure to check if there are any changes needed in the backend as well
- make sure to run the tests after making changes
- if you are adding a new feature, please add tests for it
- make a roadmap and mark solved issues, add "lessions-learned"

