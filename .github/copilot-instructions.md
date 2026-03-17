# PRISM AI Instructions

## Project Overview
PRISM is a hybrid dataset validation tool for psychological experiments. It enforces a "PRISM" structure (BIDS-inspired, with additional metadata requirements) while remaining compatible with standard BIDS tools/apps. It consists of a core Python validation library and a Flask-based web interface.

## Web Interface Patterns
- **Backend Single Source of Truth**:
  - Frontend is UX only. Do not duplicate validation/conversion business logic in JS/templates when backend can own it.
  - If frontend behavior changes, verify and update backend logic first, then wire UI to it.

## Key Conventions
- **Cross-Platform**: Always use `src.cross_platform` utilities for path handling.
- **System Files**: Always filter `.DS_Store`, `Thumbs.db` using `system_files.filter_system_files`.

