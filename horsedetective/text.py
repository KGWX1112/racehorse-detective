"""Text normalization and matching shared by the model and the evaluators."""

import re

MATCH_MODES = ("exact", "contains")

# Keys are normalized (see normalize()). Values are racing country suffixes.
# Unlisted values fall back to the uppercased input.
COUNTRY_ALIASES = {
    "japan": "JPN", "jpn": "JPN",
    "united states": "USA", "usa": "USA", "us": "USA",
    "united kingdom": "GB", "great britain": "GB", "uk": "GB", "gb": "GB",
    "ireland": "IRE", "ire": "IRE",
    "france": "FR", "fr": "FR",
    "australia": "AUS", "aus": "AUS",
    "new zealand": "NZ", "nz": "NZ",
    "canada": "CAN", "can": "CAN",
    "germany": "GER", "ger": "GER",
    "hungary": "HUN", "hun": "HUN",
}


def normalize(text: str) -> str:
    """Casefold, turn punctuation into spaces, collapse whitespace."""
    return re.sub(r"[\W_]+", " ", str(text).casefold()).strip()


def normalize_country(value: str) -> str:
    key = normalize(value)
    return COUNTRY_ALIASES.get(key, str(value).strip().upper())


def text_matches(target: str, candidate: str, mode: str) -> bool:
    """
    exact:    normalized strings are equal ("japan cup" == "Japan Cup").
    contains: target appears as whole words inside candidate, so
              "Monarch" matches "The Monarch" but not "Monarchy".
    """
    if mode not in MATCH_MODES:
        raise ValueError(f"Unknown match mode '{mode}'. Use one of {MATCH_MODES}.")
    t, c = normalize(target), normalize(candidate)
    if not t:
        return False
    if mode == "exact":
        return t == c
    return f" {t} " in f" {c} "


_GRADE_NUMBERS = {
    "1": "1", "2": "2", "3": "3",
    "i": "1", "ii": "2", "iii": "3",
    "one": "1", "two": "2", "three": "3",
}
_GRADE_RE = re.compile(r"(?:g|gr|grade|group|jpn) ?(1|2|3|i{1,3}|one|two|three)")


def normalize_grade(text: str) -> str:
    """
    Comparable form of a published grade. "G1", "Group 1", "Grade 1", "Gr. 1",
    "Grade I", and Japan's domestic "Jpn1" all give "G1". "Listed", "LR", and
    "L" give "LISTED". Any other text is normalized, so identical published
    grades still compare equal.
    """
    t = normalize(text)
    m = _GRADE_RE.fullmatch(t)
    if m:
        return "G" + _GRADE_NUMBERS[m.group(1)]
    if t in ("listed", "listed race", "lr", "l"):
        return "LISTED"
    return t


def slugify(text: str) -> str:
    return re.sub(r"[\W_]+", "-", str(text).casefold()).strip("-")
