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


def slugify(text: str) -> str:
    return re.sub(r"[\W_]+", "-", str(text).casefold()).strip("-")
