# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Memory Management

Keep each file lean — avoid dumping detailed logs or reference tables into CLAUDE.md or CLAUDE.local.md.

| File | Purpose | Rule |
|------|---------|------|
| **CLAUDE.md** | Permanent project guidelines (committed) | Short. Architecture, commands, standards only. No session notes. |
| **CLAUDE.local.md** | Active context: git workflow, TODOs, testing tips | Keep under ~60 lines. Point to memory.md for details. |
| **`.claude/memory.md`** | Detailed reference: API tables, LS XML fields, archived features, session log | Append session summaries here. OK to be long. |
| **CHANGELOG.md** | Public release history | One entry per feature/fix. |

## Project Overview

PRISM (Psychological Research Information System & Management) is a BIDS-compatible validator for psychology/neuroscience datasets. Extends BIDS with survey and biometrics modalities without breaking BIDS compatibility.

## Development Standards

### Scientific Rigor
- This is research software for scientific datasets - correctness is paramount
- Every validation rule must have clear scientific justification
- Schema changes require consideration of backward compatibility
- Error messages must be precise and actionable

### Code Quality
- **Efficiency first**: Choose the most efficient algorithm, avoid unnecessary iterations
- **No premature abstraction**: Only abstract when there's clear reuse
- **Explicit over implicit**: Clear variable names, no magic numbers
- **Fail fast**: Validate inputs early, raise meaningful exceptions
- **Type hints**: Use throughout for clarity and IDE support

### Architecture Principles
- **Single responsibility**: Each module does one thing well
- **BIDS compatibility**: Never break standard BIDS tooling
- **Cross-platform**: All code must work on Windows, macOS, Linux
- Use `src.cross_platform` for paths, `system_files.filter_system_files` for OS artifacts

## Commands

```bash
# Setup
bash setup.sh                    # macOS/Linux
scripts\setup\setup-windows.bat  # Windows

# Run
python prism-studio.py           # Web UI (port 5001)
python prism.py /path/dataset    # CLI validation
python prism_tools.py            # Data conversion

# Quality
pytest                           # All tests
black . && flake8 .              # Format and lint
```

## Architecture

| Entry Point | Purpose |
|-------------|---------|
| `prism-studio.py` | Flask web interface |
| `prism.py` | CLI validator |
| `prism_tools.py` | Data conversion tools |

| Core Module | Responsibility |
|-------------|----------------|
| `src/validator.py` | Filename patterns, schema validation |
| `src/runner.py` | Orchestrates validation pipeline |
| `src/schema_manager.py` | Schema loading by version |
| `src/issues.py` | Error codes (PRISM001-PRISM9xx) |

## Schema Updates Checklist

When modifying modalities:
1. `schemas/` - JSON schema definitions
2. `src/schema_manager.py` - modalities list
3. `src/validator.py` - MODALITY_PATTERNS
4. `prism-studio.py` - restricted_names
5. `templates/index.html` - UI list
