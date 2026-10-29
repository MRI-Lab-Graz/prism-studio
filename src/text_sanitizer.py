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

import html
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


# LimeSurvey stores numbers as DECIMAL(30,10): "23.0000000000".
_TRAILING_DECIMAL_ZEROS = re.compile(r"-?\d+\.\d*0")


def trim_trailing_decimal_zeros(value):
    """'23.0000000000' -> '23', '44.50' -> '44.5'; same number, other values untouched."""
    if isinstance(value, str) and _TRAILING_DECIMAL_ZEROS.fullmatch(value.strip()):
        return value.strip().rstrip("0").rstrip(".")
    return value


# A tag is "<" + tag name + space, "/" or ">", so "a<3" and "{if(a<b, 1, c>2)}" are text.
_HTML_TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9]*(?=[\s/>])[^<>]*>")
_HTML_BREAK_RE = re.compile(r"<br\s*/?>|</(?:p|div|li|h[1-6]|tr|blockquote)\s*>", re.IGNORECASE)
_HTML_DROP_RE = re.compile(r"<!--.*?-->|<(script|style)\b.*?</\1\s*>", re.IGNORECASE | re.DOTALL)


# Pictographs (incl. flags, skin tones, dingbats like ☺ and ❤) with their variation selector,
# keycap mark and zero-width-joiner sequences; a joiner between letters is not touched.
_EMOJI = "[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B50\u2B55]"
_EMOJI_RE = re.compile(f"{_EMOJI}[\uFE0F\u20E3]?(?:\u200D{_EMOJI}\uFE0F?)*|\uFE0F")


def strip_emoji(text: str) -> str:
    """The text without emoji (they break exports and files on Windows); spaces are not collapsed."""
    return _EMOJI_RE.sub("", text)


def html_to_text(value: Optional[str]) -> str:
    """Plain text from HTML as LimeSurvey stores it: tags removed, line and paragraph
    breaks kept as line breaks, entities decoded (after the tags, so ``&lt;b&gt;``
    stays text), spaces collapsed and blank lines dropped."""
    if not value:
        return ""
    text = _HTML_DROP_RE.sub("", value)
    text = _HTML_TAG_RE.sub("", _HTML_BREAK_RE.sub("\n", text))
    text = strip_emoji(html.unescape(text).replace("\xa0", " "))
    lines = (re.sub(r"[ \t\f\v]+", " ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


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




# Characters XML 1.0 (and so .docx and .lss files) cannot hold; text pasted from Word/PDF often has them.
INVALID_XML_CHARS = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


def strip_invalid_xml_chars(value):
    """The same value with the characters XML forbids removed (strings inside lists/dicts too)."""
    if isinstance(value, str):
        return INVALID_XML_CHARS.sub("", value)
    if isinstance(value, list):
        return [strip_invalid_xml_chars(v) for v in value]
    if isinstance(value, dict):
        return {strip_invalid_xml_chars(k): strip_invalid_xml_chars(v) for k, v in value.items()}
    return value
