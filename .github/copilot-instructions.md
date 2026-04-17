# PRISM AI Instructions

## RULE #1 — Thin Web Layer, Big Backend Engine
- `src/` is the **single canonical backend**. All business logic lives there.
- `app/src/` is a **thin adapter**: Flask route parsing, request/response serialisation, wiring UI to `src/` calls. Nothing else.
- Any `app/src/` file that duplicates logic from `src/` is wrong. It must import and delegate to `src/` instead.
- A change to business logic is **complete when made in `src/`**. Mirroring the same code to `app/src/` is the failure mode to avoid.

## Architecture Direction
- Prefer gradual object-oriented refactors when possible, especially for complex or stateful backend workflows.
- Do not rewrite stable code just to make it object-oriented; preserve behavior and improve structure incrementally.
- Avoid parallel implementations of the same behavior across modules or layers. One backend implementation should own the behavior; other layers should delegate.
- If a refactor is needed, favor introducing or extending a single canonical backend class/service over adding another helper copy elsewhere.

## Project Overview
PRISM is a hybrid dataset validation tool for psychological experiments. It enforces a "PRISM" structure (BIDS-inspired, with additional metadata requirements) while remaining compatible with standard BIDS tools/apps. It consists of a core Python validation library and a Flask-based web interface.

## Web Interface Patterns
- **Backend Single Source of Truth**:
  - Frontend is UX only. Do not duplicate validation/conversion business logic in JS/templates when backend can own it.
  - If frontend behavior changes, verify and update backend logic first, then wire UI to it.

## Key Conventions
- **Cross-Platform**: Always use `src.cross_platform` utilities for path handling.
- **System Files**: Always filter `.DS_Store`, `Thumbs.db` using `system_files.filter_system_files`.

