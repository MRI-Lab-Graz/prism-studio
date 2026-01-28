import re


def sanitize_id(id_str: str) -> str:
    """Sanitize IDs by replacing German umlauts and special characters."""
    if not id_str:
        return id_str
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
    }
    for char, repl in replacements.items():
        id_str = id_str.replace(char, repl)
    return id_str


def sanitize_task_name(name: str) -> str:
    """Normalize task names for BIDS/PRISM filenames."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "", str(name).strip())
    return cleaned.lower() or "survey"


def norm_key(s: str) -> str:
    """Normalize a string for key matching (lowercase, no spaces/underscores)."""
    return str(s).replace(" ", "").replace("_", "").lower()
