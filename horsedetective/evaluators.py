"""
Clues and evaluators.

Each evaluator returns a Finding with one of three statuses:

  MATCH          the recorded data supports the clue
  CONTRADICTION  the recorded data conflicts with the clue
  UNKNOWN        the data needed to decide is missing or incomplete

Absence of data is never a contradiction unless the field is marked complete.
Add a clue type by writing a function and decorating it with @evaluator.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .models import WIN_CODES, Horse
from .text import normalize_country, text_matches


class Status(str, Enum):
    MATCH = "MATCH"
    CONTRADICTION = "CONTRADICTION"
    UNKNOWN = "UNKNOWN"


@dataclass
class Finding:
    status: Status
    explanation: str
    fields: List[str] = field(default_factory=list)


@dataclass
class EvaluatorSpec:
    func: Callable[[Horse, Dict[str, Any]], Finding]
    required: Tuple[str, ...]
    any_of: Tuple[str, ...]
    doc: str


EVALUATORS: Dict[str, EvaluatorSpec] = {}


def evaluator(name: str, required: Tuple[str, ...] = (), any_of: Tuple[str, ...] = ()):
    def register(func):
        EVALUATORS[name] = EvaluatorSpec(func, required, any_of, (func.__doc__ or "").strip())
        return func
    return register


@dataclass
class Clue:
    description: str
    type: str
    params: Dict[str, Any] = field(default_factory=dict)
    hard: bool = False
    weight: int = 10

    def __post_init__(self):
        spec = EVALUATORS.get(self.type)
        if spec is None:
            raise ValueError(
                f"Unknown clue type '{self.type}' in clue '{self.description}'. "
                f"Known types: {sorted(EVALUATORS)}"
            )
        missing = [k for k in spec.required if k not in self.params]
        if missing:
            raise ValueError(f"Clue '{self.description}' ({self.type}) is missing params {missing}")
        if spec.any_of and not any(k in self.params for k in spec.any_of):
            raise ValueError(f"Clue '{self.description}' ({self.type}) needs at least one of {list(spec.any_of)}")
        if self.weight <= 0:
            raise ValueError(f"Clue '{self.description}' needs a positive weight")

    def evaluate(self, horse: Horse) -> Finding:
        return EVALUATORS[self.type].func(horse, self.params)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Clue":
        return cls(**data)


M, X, U = Status.MATCH, Status.CONTRADICTION, Status.UNKNOWN


# ============================================================
# Career helpers
# ============================================================

def longest_win_streak(results: List[str]) -> int:
    longest = current = 0
    for r in results:
        if r in WIN_CODES:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def streak_then_loss(results: List[str], min_len: int) -> bool:
    """True if a run of at least min_len wins is followed directly by a loss."""
    current = 0
    for r in results:
        if r in WIN_CODES:
            current += 1
        else:
            if current >= min_len:
                return True
            current = 0
    return False


def result_sequence(h: Horse) -> Tuple[Optional[List[str]], bool, List[str]]:
    """
    The W/DH/L sequence, whether it covers the whole career, and the fields it
    came from. An explicit results list comes first; otherwise the codes are
    derived from the starts in races, which needs every start's result to be
    known. Validation keeps results and the starts the same length when both
    exist, so either one marked complete makes the sequence complete.
    """
    used = [f for f in ("results", "races") if getattr(h, f) is not None]
    complete = any(h.is_complete(f) for f in used)
    seq = h.results if h.results is not None else h.derived_results()
    return seq, complete, used


def recorded_losses(h: Horse) -> List[str]:
    """Fields that show at least one loss, even in a partial record."""
    out = []
    if h.results is not None and "L" in h.results:
        out.append("results")
    if h.races is not None and any(r.result_code == "L" for r in h.races):
        out.append("races")
    return out


def known_counts(h: Horse) -> Tuple[Optional[int], Optional[int], List[str]]:
    """Career starts and wins from the summary, or from a complete results or race list."""
    starts, wins = h.summary.starts, h.summary.wins
    used = ["summary"] if (starts is not None or wins is not None) else []
    seq, complete, seq_fields = result_sequence(h)
    if complete:
        if starts is None:
            starts = len(seq) if seq is not None else len(h.starts_list())
        if wins is None and seq is not None:
            wins = sum(r in WIN_CODES for r in seq)
        used.extend(seq_fields)
    return starts, wins, used


def known_raced_countries(h: Horse) -> Tuple[Optional[List[str]], bool, List[str]]:
    """
    Countries the horse raced in, whether that list is the full record, and the
    fields used. Race records add to raced_countries, so a race abroad in a
    partial list still shows the horse raced abroad. Race records alone are
    complete only when the race list is complete and every race has a country.
    """
    listed, from_races = h.raced_countries, h.race_countries()
    if listed is None and from_races is None:
        return None, False, []
    countries = list(dict.fromkeys((listed or []) + (from_races or [])))
    used = (["raced_countries"] if listed is not None else []) + (["races"] if from_races else [])
    if listed is not None:
        complete = h.is_complete("raced_countries")
    else:
        complete = h.is_complete("races") and all(r.country for r in h.starts_list())
    return countries, complete, used


# ============================================================
# Evaluators
# ============================================================

@evaluator("win_streak", required=("min",))
def eval_win_streak(h: Horse, p: Dict[str, Any]) -> Finding:
    """Won at least `min` races in a row."""
    need = int(p["min"])
    seq, complete, seq_fields = result_sequence(h)
    longest = None
    if seq is not None:
        longest = longest_win_streak(seq)
        if longest >= need:
            return Finding(M, f"Longest recorded winning streak is {longest}.", seq_fields)
        if complete:
            return Finding(X, f"Complete race record; longest winning streak is {longest}.", seq_fields)

    starts, wins, used = known_counts(h)
    if wins is not None and wins < need:
        return Finding(X, f"Only {wins} career wins, fewer than {need}.", used)
    if starts is not None and starts < need:
        return Finding(X, f"Only {starts} career starts, fewer than {need}.", used)
    if starts is not None and wins is not None and starts == wins:
        return Finding(M, f"Unbeaten in {starts} starts, so the streak is {starts}.", used)
    if longest is not None:
        return Finding(U, f"Partial race record shows a best streak of {longest}; the rest of the career is not recorded.", seq_fields + used)
    return Finding(U, "No race sequence recorded, and the career summary does not settle the streak length.", used)


@evaluator("loss_after_streak", required=("min",))
def eval_loss_after_streak(h: Horse, p: Dict[str, Any]) -> Finding:
    """Lost the race directly after a run of at least `min` wins."""
    need = int(p["min"])
    seq, complete, seq_fields = result_sequence(h)
    if seq is not None:
        if streak_then_loss(seq, need):
            return Finding(M, f"A run of {need}+ wins ends directly in a loss.", seq_fields)
        if complete:
            return Finding(X, f"Complete race record has no run of {need}+ wins ending in a loss.", seq_fields)

    starts, wins, used = known_counts(h)
    if starts is not None and wins is not None and starts == wins:
        return Finding(X, f"Unbeaten in {starts} starts, so never lost.", used)
    if wins is not None and wins < need:
        return Finding(X, f"Only {wins} career wins, fewer than {need}.", used)
    if starts is not None and starts < need + 1:
        return Finding(X, f"Only {starts} starts; the pattern needs at least {need + 1}.", used)
    return Finding(U, "Race order not recorded; cannot tell where the losses fell.", used)


@evaluator("unbeaten", any_of=())
def eval_unbeaten(h: Horse, p: Dict[str, Any]) -> Finding:
    """Never lost. Optional `min_starts` sets a minimum career length."""
    min_starts = int(p.get("min_starts", 1))
    lost_in = recorded_losses(h)
    if lost_in:
        return Finding(X, "Race record includes a loss.", lost_in)
    starts, wins, used = known_counts(h)
    if starts is not None and wins is not None:
        if wins < starts:
            return Finding(X, f"{wins} wins from {starts} starts.", used)
        if starts < min_starts:
            return Finding(X, f"Unbeaten, but only {starts} starts (clue needs {min_starts}).", used)
        return Finding(M, f"Unbeaten in {starts} starts.", used)
    return Finding(U, "Career record not complete enough to confirm an unbeaten career.", used)


_COMPARE = {
    "eq": (lambda a, b: a == b, "exactly"),
    "gte": (lambda a, b: a >= b, "at least"),
    "lte": (lambda a, b: a <= b, "at most"),
}


@evaluator("career", required=("field", "op", "n"))
def eval_career(h: Horse, p: Dict[str, Any]) -> Finding:
    """Career count comparison. field: starts|wins|seconds|thirds, op: eq|gte|lte."""
    f, op, n = p["field"], p["op"], int(p["n"])
    if op not in _COMPARE:
        raise ValueError(f"career clue op must be one of {list(_COMPARE)}")
    if f in ("starts", "wins"):
        starts, wins, used = known_counts(h)
        value = starts if f == "starts" else wins
    elif f in ("seconds", "thirds"):
        value, used = getattr(h.summary, f), ["summary"]
    else:
        raise ValueError("career clue field must be starts, wins, seconds, or thirds")
    if value is None:
        return Finding(U, f"Career {f} not recorded.", used)
    test, words = _COMPARE[op]
    status = M if test(value, n) else X
    return Finding(status, f"Career {f}: {value} (clue: {words} {n}).", used)


@evaluator("international")
def eval_international(h: Horse, p: Dict[str, Any]) -> Finding:
    """Raced outside its country of foaling. `value: false` means never did."""
    want = bool(p.get("value", True))
    raced_abroad = None
    used = []
    countries, complete, country_fields = known_raced_countries(h)
    if country_fields and h.country:
        abroad = [c for c in countries if c != h.country]
        used = country_fields + ["country"]
        if abroad:
            raced_abroad, detail = True, f"Raced in {', '.join(abroad)} (foaled in {h.country})."
        elif complete:
            raced_abroad, detail = False, f"Complete list shows racing only in {h.country}."
    if raced_abroad is None and h.international is not None:
        raced_abroad, used = h.international, ["international"]
        detail = "Recorded as having raced abroad." if raced_abroad else "Recorded as never having raced abroad."
    if raced_abroad is None:
        if used:
            if h.raced_countries is None and h.is_complete("races"):
                return Finding(U, f"Every race with a recorded country was in {h.country}, "
                                  f"but some races have no country.", used)
            return Finding(U, f"Recorded races are all in {h.country}, but the list is not marked complete.", used)
        if country_fields:
            listed = ", ".join(countries) or "none listed"
            return Finding(U, f"Country of foaling is unknown, so the raced countries ({listed}) "
                              f"cannot be compared with it.", country_fields)
        return Finding(U, "No record of where the horse raced.", used)
    return Finding(M if raced_abroad == want else X, detail, used)


@evaluator("country", required=("code",))
def eval_country(h: Horse, p: Dict[str, Any]) -> Finding:
    """Foaled in the given country (name or suffix code)."""
    want = normalize_country(p["code"])
    if not h.country:
        return Finding(U, "Country of foaling not recorded.", [])
    status = M if h.country == want else X
    return Finding(status, f"Foaled in {h.country}.", ["country"])


@evaluator("foaled", any_of=("min", "max"))
def eval_foaled(h: Horse, p: Dict[str, Any]) -> Finding:
    """Foaling year within an inclusive range. Give `min`, `max`, or both."""
    if h.foaled is None:
        return Finding(U, "Foaling year not recorded.", [])
    lo, hi = p.get("min"), p.get("max")
    ok = (lo is None or h.foaled >= int(lo)) and (hi is None or h.foaled <= int(hi))
    return Finding(M if ok else X, f"Foaled {h.foaled}.", ["foaled"])


def _list_match(h: Horse, field_name: str, text: str, mode: str, label: str) -> Finding:
    values = getattr(h, field_name)
    if values:
        hits = [v for v in values if text_matches(text, v, mode)]
        if hits:
            return Finding(M, f"{label} match: {hits[0]}.", [field_name])
    if values is not None and h.is_complete(field_name):
        return Finding(X, f"Complete {label.lower()} list has no entry matching '{text}'.", [field_name])
    if values is None:
        return Finding(U, f"No {label.lower()} data recorded.", [])
    return Finding(U, f"No recorded {label.lower()} matches '{text}', but the list is not marked complete.", [field_name])


@evaluator("nickname", required=("text",))
def eval_nickname(h: Horse, p: Dict[str, Any]) -> Finding:
    """Nickname containing `text` (whole words). mode: contains (default) | exact."""
    return _list_match(h, "nicknames", p["text"], p.get("mode", "contains"), "Nickname")


@evaluator("title", required=("text",))
def eval_title(h: Horse, p: Dict[str, Any]) -> Finding:
    """Won the named race. mode: exact (default) | contains."""
    return _list_match(h, "major_titles", p["text"], p.get("mode", "exact"), "Title")


@evaluator("record", required=("text",))
def eval_record(h: Horse, p: Dict[str, Any]) -> Finding:
    """Holds or held a record described by `text`. mode: contains (default) | exact."""
    return _list_match(h, "records", p["text"], p.get("mode", "contains"), "Record")


@evaluator("person", required=("role", "name"))
def eval_person(h: Horse, p: Dict[str, Any]) -> Finding:
    """Trainer, jockey, or owner. role: trainer|jockey|owner. mode: contains (default) | exact."""
    role = p["role"]
    if role not in ("trainer", "jockey", "owner"):
        raise ValueError("person clue role must be trainer, jockey, or owner")
    return _list_match(h, role + "s", p["name"], p.get("mode", "contains"), role.capitalize())
