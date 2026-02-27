"""LSA preprocessing helpers for conversion setup."""

from __future__ import annotations


def _unpack_lsa_read_result(result):
    """Unpack table read result for LSA inputs."""
    if isinstance(result, tuple):
        df, lsa_questions_map = result
    else:
        df = result
        lsa_questions_map = None
    return df, lsa_questions_map


def _resolve_lsa_language_and_strict(
    *,
    input_path,
    df,
    language: str | None,
    strict_levels: bool | None,
    infer_lsa_language_and_tech_fn,
) -> tuple[str | None, dict, bool]:
    """Resolve effective language/technical overrides/strict-level mode for LSA conversion."""
    inferred_lang, inferred_tech = infer_lsa_language_and_tech_fn(
        input_path=input_path,
        df=df,
    )
    effective_language = language
    if not effective_language or effective_language.strip().lower() == "auto":
        effective_language = inferred_lang

    effective_strict_levels = False if strict_levels is None else bool(strict_levels)
    return effective_language, inferred_tech, effective_strict_levels
