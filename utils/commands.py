"""Minimal input cleanup shared by text command entry points."""


def normalize_command(text: str) -> str:
    """Trim surrounding whitespace and balanced wrappers, preserving payload text.

    Do not rewrite spelling, repeated words, punctuation, or internal whitespace:
    commands can contain messages, paths, code, and case-sensitive search terms.
    """
    if not isinstance(text, str):
        return ""
    cleaned = text.strip()
    wrappers = {"'": "'", '"': '"', "`": "`", "‘": "’", "“": "”"}
    while len(cleaned) > 1 and wrappers.get(cleaned[0]) == cleaned[-1]:
        cleaned = cleaned[1:-1].strip()
    return cleaned
