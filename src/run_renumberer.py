from __future__ import annotations

import re
from pathlib import Path

from src.bids_entity_parser import BidsEntityParser
from src.bids_entity_rewriter import BidsEntityRewriter

_NUMERIC_RUN_PATTERN = re.compile(r"^\d+$")


class RunRenumberer:
    """Detects and closes gaps in run-XX sequences (e.g. run-01,03,04 ->
    run-01,02,03 after run-02 was deleted).

    Reuses BidsEntityRewriter's filename token parsing/rewriting rather than
    a third independent parser, and its explicit_renames apply path rather
    than a second file-mutation implementation -- this class only computes
    *which* renames close a gap; BidsEntityRewriter/apply_entity_rewrite
    still do the actual renaming, DataLad handling, and undo integration.

    Renames within a group are only ever proposed in ascending run-value
    order (rank-preserving: the smallest surviving run always lands on 01,
    the next on 02, etc). This matters because closing a gap like
    [01,03,04] -> [01,02,03] is a rename *chain* (04->03 while 03 is also
    being renamed away to 02) -- processing out of order would collide with
    or overwrite the not-yet-renamed original. Ascending order is always
    safe here: a target slot N can only still be occupied by a *smaller*
    original run value, which -- being smaller -- was already vacated by an
    earlier step in the same ascending pass (proven by induction: for a
    strictly increasing sequence, the i-th smallest of N distinct positive
    integers is always >= i+1, so a target of i+1 can't be "from the
    future"). Groups with inconsistent zero-padding are skipped entirely
    (see _scan_groups), which keeps this ascending-value order equivalent
    to BidsEntityRewriter.apply()'s own alphabetical old-path sort -- so no
    extra ordering logic is needed there either.
    """

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self._entity_rewriter = BidsEntityRewriter(self.project_root)

    def preview(self) -> dict:
        groups, skipped_groups = self._scan_groups()
        return self._result_to_dict(groups, skipped_groups)

    def apply(self) -> dict:
        groups, skipped_groups = self._scan_groups()
        renames = [rename for group in groups for rename in group["renames"]]
        if renames:
            self._apply_renames_two_phase(renames)
        result = self._result_to_dict(groups, skipped_groups)
        result["applied"] = True
        return result

    def _apply_renames_two_phase(self, renames: list[dict]) -> None:
        """Apply a batch of renames that may contain chains (e.g. closing
        [01,03,04] -> [01,02,03] needs 04->03 while 03 is also moving to
        02) via an intermediate temp name, so the mutation never depends on
        processing order.

        A direct one-phase apply is only safe if the caller happens to
        process renames in an order where no target is still occupied by
        an original, not-yet-moved file -- true for gap-closing in
        ascending run-value order, but NOT true for undo's reverse of that
        same batch (which needs descending order instead). Rather than
        rely on ordering assumptions that silently flip between forward
        and reverse, route every rename through a guaranteed-unused temp
        name first: phase 1 never collides (temp names are novel), and by
        phase 2 every original has already vacated its slot, so no target
        can still be occupied either. Two BidsEntityRewriter.apply() calls
        (not a hand-rolled Path.rename loop) so IntendedFor-style JSON
        content is still correctly rewritten at each stage.
        """
        temp_suffix = ".prism_run_renumber_tmp"
        to_temp = [
            {"from": item["from"], "to": f"{item['from']}{temp_suffix}"}
            for item in renames
        ]
        self._entity_rewriter.apply(
            modality="", entity="", operation="rename", explicit_renames=to_temp
        )

        from_temp = [
            {"from": f"{item['from']}{temp_suffix}", "to": item["to"]}
            for item in renames
        ]
        self._entity_rewriter.apply(
            modality="", entity="", operation="rename", explicit_renames=from_temp
        )

    def _result_to_dict(self, groups: list[dict], skipped_groups: list[dict]) -> dict:
        return {
            "applied": False,
            "groups": groups,
            "skipped_groups": skipped_groups,
            "rename_count": sum(len(group["renames"]) for group in groups),
        }

    def _scan_groups(self) -> tuple[list[dict], list[dict]]:
        # group_key -> run_value -> list of file paths
        buckets: dict[tuple, dict[str, list[Path]]] = {}

        for file_path in self._entity_rewriter._iter_files():
            rel_dir = file_path.parent.relative_to(self.project_root).as_posix()
            parsed = self._entity_rewriter._parse_filename_tokens(file_path.name)
            if parsed is None:
                continue
            tokens, _stem, extension = parsed
            prefix_tokens = tokens[:-1]
            suffix_token = tokens[-1]

            run_value: str | None = None
            other_tokens: list[str] = []
            for token in prefix_tokens:
                parsed_token = BidsEntityParser.parse_entity_token(token)
                if parsed_token is not None and parsed_token[0] == "run":
                    run_value = parsed_token[1]
                    continue
                other_tokens.append(token)

            if run_value is None:
                continue

            group_key = (rel_dir, tuple(other_tokens), suffix_token, extension)
            buckets.setdefault(group_key, {}).setdefault(run_value, []).append(file_path)

        groups: list[dict] = []
        skipped_groups: list[dict] = []

        for group_key, files_by_run in sorted(buckets.items()):
            rel_dir, other_tokens, suffix_token, extension = group_key
            group_label = "/".join([rel_dir, "_".join([*other_tokens, suffix_token]) + extension])
            run_values = sorted(files_by_run.keys())

            non_numeric = [value for value in run_values if not _NUMERIC_RUN_PATTERN.fullmatch(value)]
            if non_numeric:
                skipped_groups.append({
                    "key": group_label,
                    "reason": f"non-numeric run value(s): {', '.join(non_numeric)}",
                })
                continue

            widths = {len(value) for value in run_values}
            if len(widths) > 1:
                skipped_groups.append({
                    "key": group_label,
                    "reason": f"inconsistent zero-padding across run values: {', '.join(run_values)}",
                })
                continue

            width = widths.pop()
            numeric_sorted = sorted(run_values, key=int)
            proposed = [str(i + 1).zfill(width) for i in range(len(numeric_sorted))]

            if numeric_sorted == proposed:
                continue  # already contiguous from 1, nothing to do

            renames = []
            for old_value, new_value in zip(numeric_sorted, proposed):
                if old_value == new_value:
                    continue
                for file_path in files_by_run[old_value]:
                    new_name = self._entity_rewriter._rewrite_filename_for_entity(
                        file_path.name,
                        entity="run",
                        current_value=old_value,
                        operation="rename",
                        replacement=new_value,
                    )
                    if not new_name:
                        continue
                    renames.append({
                        "from": file_path.relative_to(self.project_root).as_posix(),
                        "to": (file_path.parent / new_name).relative_to(self.project_root).as_posix(),
                    })

            groups.append({
                "key": group_label,
                "current_runs": numeric_sorted,
                "proposed_runs": proposed,
                "renames": renames,
            })

        return groups, skipped_groups
