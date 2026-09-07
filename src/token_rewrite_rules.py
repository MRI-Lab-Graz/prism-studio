from __future__ import annotations

"""Shared "example_keep" / "last3" rule logic for BIDS entity token rewriters.

Extracted so `SubjectCodeRewriter` (sub-XXX) and `SessionCodeRewriter`
(ses-XXX) share one tested implementation of the strip/add rule instead of
two independently-maintained copies -- the exact "dual implementation
drift" failure mode this repo's CLAUDE.md warns about elsewhere. This
module is pure string logic with no filesystem access; each rewriter still
owns its own directory traversal, collision detection, and DataLad-aware
apply, since subjects and sessions nest differently (subjects are top-level
project directories, sessions nest one level inside each subject).
"""


def build_example_keep_rule(
    tokens: list[str],
    example_token: str | None,
    keep_fragment: str | None,
    token_prefix: str,
    add_text: str | None = None,
    add_position: str | None = None,
    id_noun: str = "ID",
) -> dict[str, str | int]:
    if not tokens:
        raise ValueError(f"No {id_noun}s were found in this project.")

    raw_example = (example_token or "").strip()
    if not raw_example:
        raise ValueError(
            f"Select one current {id_noun} as example before previewing this rule."
        )

    normalized_example = (
        raw_example if raw_example.startswith(token_prefix) else f"{token_prefix}{raw_example}"
    )
    if normalized_example not in tokens:
        raise ValueError(
            f"The selected example {id_noun} was not found in this project. "
            f"Choose a different example {id_noun} and retry."
        )

    raw_keep = (keep_fragment or "").strip()
    raw_add = (add_text or "").strip()
    if not raw_keep and not raw_add:
        raise ValueError(
            f"Enter a part to keep and/or a part to add for the selected example {id_noun}."
        )
    if raw_add and not raw_add.isalnum():
        raise ValueError("Text to add can only contain letters and numbers.")

    example_label = normalized_example[len(token_prefix):]

    if raw_keep:
        keep_value = (
            raw_keep[len(token_prefix):]
            if raw_keep.startswith(token_prefix)
            else raw_keep
        )

        occurrence_count = example_label.count(keep_value)
        if occurrence_count == 0:
            raise ValueError(f"'{keep_value}' is not part of {normalized_example}.")
        if occurrence_count > 1:
            raise ValueError(
                "Pattern is not unique in the selected example "
                f"(e.g. {token_prefix}103103 -> 103). "
                "Choose a different example or a more specific kept part."
            )

        start_index = example_label.find(keep_value)
        end_index = start_index + len(keep_value)

        if start_index == 0 and end_index == len(example_label):
            strategy = "full"
        elif end_index == len(example_label):
            strategy = "suffix"
        elif start_index == 0:
            strategy = "prefix"
        else:
            strategy = "slice"
    else:
        # Add-only: nothing is stripped, the whole existing label is kept
        # as-is before add_text is applied.
        keep_value = example_label
        start_index = 0
        end_index = len(example_label)
        strategy = "full"

    rule: dict[str, str | int] = {
        "type": "example_keep",
        "example_token": normalized_example,
        "keep_fragment": keep_value,
        "strategy": strategy,
        "length": len(keep_value),
        "start": start_index,
        "end": end_index,
    }
    if strategy == "slice":
        # Anchor on the literal text surrounding the kept fragment rather
        # than fixed character positions, so tokens of different lengths
        # still resolve correctly instead of relying on a positional slice
        # derived from the one example.
        rule["prefix_anchor"] = example_label[:start_index]
        rule["suffix_anchor"] = example_label[end_index:]
    if raw_add:
        rule["add_text"] = raw_add
        rule["add_position"] = "append" if add_position == "append" else "prepend"
    return rule


def rewrite_token(
    token: str,
    mode: str,
    rule: dict[str, str | int] | None,
    token_prefix: str,
) -> str:
    if mode == "last3":
        label = token[len(token_prefix):] if token.startswith(token_prefix) else token
        digits = "".join(ch for ch in label if ch.isdigit())
        if not digits:
            return token
        return f"{token_prefix}{digits[-3:]}"

    if mode != "example_keep" or not rule:
        return token

    label = token[len(token_prefix):] if token.startswith(token_prefix) else token
    strategy = str(rule.get("strategy") or "")
    length = int(rule.get("length") or 0)

    if strategy == "suffix":
        if len(label) < length:
            return token
        rewritten_label = label[-length:]
    elif strategy == "prefix":
        if len(label) < length:
            return token
        rewritten_label = label[:length]
    elif strategy == "slice":
        prefix_anchor = str(rule.get("prefix_anchor") or "")
        suffix_anchor = str(rule.get("suffix_anchor") or "")
        if not label.startswith(prefix_anchor) or not label.endswith(suffix_anchor):
            return token
        if len(label) < len(prefix_anchor) + len(suffix_anchor):
            return token
        rewritten_label = label[len(prefix_anchor) : len(label) - len(suffix_anchor)]
    elif strategy == "full":
        rewritten_label = label
    else:
        return token

    add_text = str(rule.get("add_text") or "")
    if add_text:
        if rule.get("add_position") == "append":
            rewritten_label = f"{rewritten_label}{add_text}"
        else:
            rewritten_label = f"{add_text}{rewritten_label}"

    if not rewritten_label:
        return token
    return f"{token_prefix}{rewritten_label}"
