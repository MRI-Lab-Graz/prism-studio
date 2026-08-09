"""
Text sanitization utilities for cleaning survey content before export.

This module provides centralized handling of embedded annotations, scoring markers,
and other metadata that should not be displayed to survey participants.

The patterns here handle content from various sources:
- PsyToolkit: {score=N}, {reverse}, {optional}
- LimeSurvey: Assessment codes, expression placeholders
- Custom: Any future annotation formats

Usage:
    from src.text_sanitizer import sanitize_display_text

    # Clean answer text before export
    clean_text = sanitize_display_text("{score=1} Strongly agree")
    # Result: "Strongly agree"
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# =============================================================================
# ANNOTATION PATTERNS
# =============================================================================
# Each pattern is a tuple of (compiled_regex, description)
# Add new patterns here as they are discovered from various survey tools
#
# Pattern format: The regex should match the ENTIRE annotation including any
# trailing whitespace, so the replacement with "" leaves clean text.
# =============================================================================

ANNOTATION_PATTERNS = [
    # PsyToolkit scoring annotations: {score=0}, {score=1}, {score=-1}, etc.
    (
        re.compile(r"\{score\s*=\s*-?\d+\}\s*", re.IGNORECASE),
        "PsyToolkit score annotation",
    ),
    # PsyToolkit reverse scoring marker: {reverse}
    (re.compile(r"\{reverse\}\s*", re.IGNORECASE), "PsyToolkit reverse marker"),
    # PsyToolkit optional marker: {optional}
    (re.compile(r"\{optional\}\s*", re.IGNORECASE), "PsyToolkit optional marker"),
    # Generic key=value annotations: {key=value}, {key = value}
    # This is a catch-all for future PsyToolkit-style annotations
    # Matches: {anything=anything} but NOT LimeSurvey expressions like {TOKEN:FIRSTNAME}
    (
        re.compile(r"\{[a-z_]+\s*=\s*[^}]+\}\s*", re.IGNORECASE),
        "Generic key=value annotation",
    ),
    # Bracketed annotations: [score:1], [reverse], etc. (some tools use brackets)
    (
        re.compile(r"\[score\s*[=:]\s*-?\d+\]\s*", re.IGNORECASE),
        "Bracketed score annotation",
    ),
    # HTML comments that might have leaked: <!-- scoring info -->
    (re.compile(r"<!--.*?-->\s*", re.DOTALL), "HTML comment"),
]

# Patterns that should be preserved (not stripped) - for validation
# These look like annotations but are actually LimeSurvey expression syntax
PRESERVE_PATTERNS = [
    re.compile(r"\{[A-Z0-9_]+\.NAOK\}", re.IGNORECASE),  # {Q1.NAOK}
    re.compile(r"\{TOKEN:[A-Z_]+\}", re.IGNORECASE),  # {TOKEN:FIRSTNAME}
    re.compile(r"\{INSERTANS:[^}]+\}", re.IGNORECASE),  # {INSERTANS:123X456X789}
]


def sanitize_display_text(text: Optional[str], strip_html: bool = False) -> str:
    """
    Remove embedded annotations from text intended for display to participants.

    This function strips scoring annotations, metadata markers, and other
    embedded information that should not be visible in the final survey.

    Args:
        text: Text that may contain embedded annotations
        strip_html: If True, also strip HTML tags (default: False)

    Returns:
        Cleaned text with annotations removed and whitespace normalized

    Examples:
        >>> sanitize_display_text("{score=0} very rarely")
        'very rarely'
        >>> sanitize_display_text("{score=1} often")
        'often'
        >>> sanitize_display_text("{reverse} I feel sad")
        'I feel sad'
        >>> sanitize_display_text("Normal text without annotations")
        'Normal text without annotations'
    """
    if not text:
        return text if text is not None else ""

    result = text

    # Check if text contains LimeSurvey expressions that should be preserved
    has_ls_expressions = any(p.search(result) for p in PRESERVE_PATTERNS)

    # Apply each annotation pattern
    for pattern, description in ANNOTATION_PATTERNS:
        # Skip generic pattern if we have LS expressions (to avoid breaking them)
        if has_ls_expressions and "generic" in description.lower():
            continue

        original = result
        result = pattern.sub("", result)
        if result != original:
            logger.debug("Stripped %s from text", description)

    # Optionally strip HTML tags
    if strip_html:
        result = re.sub(r"<[^>]+>", "", result)

    # Normalize whitespace: collapse multiple spaces, trim
    result = re.sub(r"\s+", " ", result).strip()

    return result


def sanitize_answer_text(text: Optional[str]) -> str:
    """
    Sanitize answer/level text for export to survey tools.

    This is the primary function to use when exporting answer options.
    It removes all embedded annotations while preserving the actual answer text.

    Args:
        text: Answer text that may contain scoring or other annotations

    Returns:
        Clean answer text suitable for display to participants
    """
    return sanitize_display_text(text, strip_html=False)


