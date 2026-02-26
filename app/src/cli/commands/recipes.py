"""Recipe-related prism_tools command handlers."""

from __future__ import annotations

import sys
from pathlib import Path

from src.config import get_effective_library_paths
from src.recipes_surveys import compute_survey_recipes


_APP_ROOT = Path(__file__).resolve().parents[3]


def _resolve_default_repo_root() -> Path:
    return _APP_ROOT.parent if _APP_ROOT.name == "app" else _APP_ROOT


def cmd_recipes_surveys(args):
    prism_root = Path(args.prism).resolve()
    if not prism_root.exists() or not prism_root.is_dir():
        print(f"Error: --prism is not a directory: {prism_root}")
        sys.exit(1)

    if hasattr(args, "repo") and args.repo:
        repo_root = Path(args.repo).resolve()
    else:
        lib_paths = get_effective_library_paths(app_root=str(_APP_ROOT))
        if lib_paths["global_library_root"]:
            repo_root = Path(lib_paths["global_library_root"]).resolve()
            print(f"ℹ️  Using global library: {repo_root}")
        else:
            repo_root = _resolve_default_repo_root().resolve()
            print(f"ℹ️  Using default repository root: {repo_root}")

    if not repo_root.exists() or not repo_root.is_dir():
        print(f"Error: --repo is not a directory: {repo_root}")
        sys.exit(1)

    out_format = str(getattr(args, "format", "flat") or "flat").strip().lower()
    recipe_dir = (
        str(args.recipes).strip() if getattr(args, "recipes", None) else ""
    ) or None
    survey_filter = (
        str(args.survey).strip() if getattr(args, "survey", None) else ""
    ) or None
    sessions_filter = (
        str(args.sessions).strip() if getattr(args, "sessions", None) else ""
    ) or None
    lang = str(getattr(args, "lang", "en") or "en").strip().lower()
    layout = str(getattr(args, "layout", "long") or "long").strip().lower()
    include_raw = bool(getattr(args, "include_raw", False))

    try:
        result = compute_survey_recipes(
            prism_root=prism_root,
            repo_root=repo_root,
            recipe_dir=recipe_dir,
            survey=survey_filter,
            sessions=sessions_filter,
            out_format=out_format,
            modality="survey",
            lang=lang,
            layout=layout,
            include_raw=include_raw,
        )
        print(
            f"✅ Survey recipe scoring complete: {result.written_files} file(s) written"
        )
        if result.flat_out_path:
            print(f"   Flat output: {result.flat_out_path}")
        if result.fallback_note:
            print(f"   Note: {result.fallback_note}")
        if result.nan_report:
            print("   Columns with all n/a:")
            for key, cols in result.nan_report.items():
                joined = ", ".join(sorted(cols))
                print(f"     - {key}: {joined}")

        if getattr(args, "boilerplate", False):
            try:
                from src.readme_generator import generate_methods_for_dataset

                text = generate_methods_for_dataset(
                    prism_root=prism_root,
                    repo_root=repo_root,
                    surveys=survey_filter,
                    sessions=sessions_filter,
                    modality="survey",
                    lang=lang,
                )
                out = prism_root / "derivatives" / "survey" / "methods_survey.md"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(text, encoding="utf-8")
                print(f"📝 Methods boilerplate written: {out}")
            except Exception as e:
                print(f"⚠️  Could not generate methods boilerplate: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def cmd_recipes_biometrics(args):
    prism_root = Path(args.prism).resolve()
    if not prism_root.exists() or not prism_root.is_dir():
        print(f"Error: --prism is not a directory: {prism_root}")
        sys.exit(1)

    if hasattr(args, "repo") and args.repo:
        repo_root = Path(args.repo).resolve()
    else:
        lib_paths = get_effective_library_paths(app_root=str(_APP_ROOT))
        if lib_paths["global_library_root"]:
            repo_root = Path(lib_paths["global_library_root"]).resolve()
            print(f"ℹ️  Using global library: {repo_root}")
        else:
            repo_root = _resolve_default_repo_root().resolve()
            print(f"ℹ️  Using default repository root: {repo_root}")

    if not repo_root.exists() or not repo_root.is_dir():
        print(f"Error: --repo is not a directory: {repo_root}")
        sys.exit(1)

    out_format = str(getattr(args, "format", "flat") or "flat").strip().lower()
    recipe_dir = (
        str(args.recipes).strip() if getattr(args, "recipes", None) else ""
    ) or None
    biometric_filter = (
        str(args.biometric).strip() if getattr(args, "biometric", None) else ""
    ) or None
    sessions_filter = (
        str(args.sessions).strip() if getattr(args, "sessions", None) else ""
    ) or None
    lang = str(getattr(args, "lang", "en") or "en").strip().lower()
    layout = str(getattr(args, "layout", "long") or "long").strip().lower()

    try:
        result = compute_survey_recipes(
            prism_root=prism_root,
            repo_root=repo_root,
            recipe_dir=recipe_dir,
            survey=biometric_filter,
            sessions=sessions_filter,
            out_format=out_format,
            modality="biometrics",
            lang=lang,
            layout=layout,
        )
        print(
            f"✅ Biometric recipe scoring complete: {result.written_files} file(s) written"
        )
        if result.flat_out_path:
            print(f"   Flat output: {result.flat_out_path}")
        if result.fallback_note:
            print(f"   Note: {result.fallback_note}")
        if result.nan_report:
            print("   Columns with all n/a:")
            for key, cols in result.nan_report.items():
                joined = ", ".join(sorted(cols))
                print(f"     - {key}: {joined}")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
