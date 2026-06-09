import re


def extract_terminal_suffix_label(filename: str) -> str | None:
    """Return the terminal BIDS suffix token from a filename, or None."""
    name = str(filename or "").strip()
    if not name:
        return None

    lower_name = name.lower()
    for compound_ext in (".nii.gz", ".tsv.gz"):
        if lower_name.endswith(compound_ext):
            name = name[: -len(compound_ext)]
            break
    else:
        if "." in name:
            name = name.rsplit(".", 1)[0]

    if not name:
        return None

    suffix = name.rsplit("_", 1)[-1]
    if not suffix or "-" in suffix:
        return None
    return suffix


def matches_excluded_acq_label(filename: str, excluded_labels: set[str]) -> bool:
    """Return True when a filename matches one of the excluded acq/suffix labels."""
    normalized_labels = {
        str(label).strip().lower() for label in excluded_labels if str(label).strip()
    }
    if not normalized_labels:
        return False

    suffix_label = extract_terminal_suffix_label(filename)
    acq_match = re.search(r"_acq-([A-Za-z0-9]+)", filename)
    acq_label = acq_match.group(1) if acq_match else None

    normalized_suffix = suffix_label.lower() if suffix_label else ""
    normalized_acq = acq_label.lower() if acq_label else ""

    if normalized_suffix and normalized_suffix in normalized_labels:
        return True
    if normalized_acq and normalized_acq in normalized_labels:
        return True
    if (
        normalized_acq
        and normalized_suffix
        and (
            f"{normalized_acq}-{normalized_suffix}" in normalized_labels
            or f"{normalized_suffix}-{normalized_acq}" in normalized_labels
        )
    ):
        return True

    if normalized_acq and normalized_suffix:
        for label in normalized_labels:
            tokens = [token for token in re.split(r"[-_/]", label) if token]
            if len(tokens) < 2:
                continue
            if tokens[-1] == normalized_suffix and normalized_acq in tokens[:-1]:
                return True

    return False


def extract_export_task_label(filename: str, modality: str | None = None) -> str | None:
    """Return the task label encoded in an export filename, or None."""
    normalized_filename = str(filename or "").strip()
    if not normalized_filename:
        return None

    root_name = normalized_filename
    lower_root_name = root_name.lower()
    for compound_ext in (".nii.gz", ".tsv.gz"):
        if lower_root_name.endswith(compound_ext):
            root_name = root_name[: -len(compound_ext)]
            break
    else:
        if "." in root_name:
            root_name = root_name.rsplit(".", 1)[0]

    if modality:
        modality_match = re.search(
            rf"(?:^|_)task-(.+)_{re.escape(modality)}$",
            root_name,
        )
        if modality_match:
            return modality_match.group(1)

    match = re.search(r"(?:^|_)task-([A-Za-z0-9]+)", root_name)
    if match:
        return match.group(1)

    return None


_extract_terminal_suffix_label = extract_terminal_suffix_label
_matches_excluded_acq_label = matches_excluded_acq_label
_extract_export_task_label = extract_export_task_label