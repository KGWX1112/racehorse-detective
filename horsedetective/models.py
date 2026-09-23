"""
Horse data model.

Conventions that the evaluators rely on:

* None means "not recorded". An empty list means "recorded, and there are none"
  only when the field is also listed in complete_fields.
* A field in complete_fields is the horse's full record for that field. Only a
  complete field can produce a CONTRADICTION from absence ("no title matching X").
* sources maps a field name to a citation. The key "*" is the fallback for any
  field without its own entry. Career summary fields share the key "summary".
* results is the ordered race sequence: W = win, DH = dead heat for first
  (counts as a win), L = any non-winning finish.
"""

from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict, List, Optional

from .text import normalize_country, slugify

RESULT_CODES = ("W", "DH", "L")
WIN_CODES = ("W", "DH")

LIST_FIELDS = (
    "nicknames", "trainers", "jockeys", "owners",
    "major_titles", "records", "raced_countries",
)
COMPLETABLE_FIELDS = LIST_FIELDS + ("results",)
SUMMARY_FIELDS = ("starts", "wins", "seconds", "thirds")


def make_horse_id(name: str, country: Optional[str], foaled: Optional[int]) -> str:
    return "-".join([
        slugify(name),
        slugify(country) if country else "unk",
        str(foaled) if foaled else "unk",
    ])


@dataclass
class CareerSummary:
    starts: Optional[int] = None
    wins: Optional[int] = None
    seconds: Optional[int] = None
    thirds: Optional[int] = None

    def is_empty(self) -> bool:
        return all(getattr(self, f) is None for f in SUMMARY_FIELDS)


@dataclass
class Horse:
    name: str
    country: Optional[str] = None
    foaled: Optional[int] = None
    id: str = ""
    sex: Optional[str] = None

    nicknames: Optional[List[str]] = None
    trainers: Optional[List[str]] = None
    jockeys: Optional[List[str]] = None
    owners: Optional[List[str]] = None
    major_titles: Optional[List[str]] = None
    records: Optional[List[str]] = None

    # Countries the horse raced in. International = raced outside `country`.
    raced_countries: Optional[List[str]] = None
    # Fallback when raced_countries is unknown but the fact itself is recorded.
    international: Optional[bool] = None

    results: Optional[List[str]] = None
    summary: CareerSummary = field(default_factory=CareerSummary)

    complete_fields: List[str] = field(default_factory=list)
    sources: Dict[str, str] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self):
        if isinstance(self.summary, dict):
            self.summary = CareerSummary(**self.summary)
        if self.country:
            self.country = normalize_country(self.country)
        if self.raced_countries is not None:
            self.raced_countries = [normalize_country(c) for c in self.raced_countries]
        if self.results is not None:
            self.results = [str(r).strip().upper() for r in self.results]
        if not self.id:
            self.id = make_horse_id(self.name, self.country, self.foaled)
        self.validate()

    # ------------------------------------------------------------------
    def validate(self) -> None:
        problems = []

        if not str(self.name).strip():
            problems.append("name is empty")

        if self.results is not None:
            bad = sorted({r for r in self.results if r not in RESULT_CODES})
            if bad:
                hint = " ('D' is ambiguous: use DH for a dead heat for first, L otherwise)" if "D" in bad else ""
                problems.append(f"unknown result codes {bad}; allowed {list(RESULT_CODES)}{hint}")

        for f in self.complete_fields:
            if f not in COMPLETABLE_FIELDS:
                problems.append(f"'{f}' cannot be marked complete; allowed {list(COMPLETABLE_FIELDS)}")
            elif getattr(self, f) is None:
                problems.append(f"'{f}' is marked complete but has no data")

        s = self.summary
        for f in SUMMARY_FIELDS:
            v = getattr(s, f)
            if v is not None and v < 0:
                problems.append(f"summary.{f} is negative")
        placed = [v for v in (s.wins, s.seconds, s.thirds) if v is not None]
        if s.starts is not None and sum(placed) > s.starts:
            problems.append("summary wins + seconds + thirds exceed starts")

        if self.results is not None and self.is_complete("results"):
            seq_starts = len(self.results)
            seq_wins = sum(r in WIN_CODES for r in self.results)
            if s.starts is not None and s.starts != seq_starts:
                problems.append(f"summary.starts={s.starts} but complete results list has {seq_starts} races")
            if s.wins is not None and s.wins != seq_wins:
                problems.append(f"summary.wins={s.wins} but complete results list has {seq_wins} wins")

        if problems:
            raise ValueError(f"Invalid horse '{self.name}': " + "; ".join(problems))

    # ------------------------------------------------------------------
    def is_complete(self, field_name: str) -> bool:
        return field_name in self.complete_fields

    def source_for(self, field_name: str) -> Optional[str]:
        return self.sources.get(field_name) or self.sources.get("*")

    @property
    def label(self) -> str:
        return f"{self.name} ({self.country or '?'}) {self.foaled or '?'}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Horse":
        allowed = {f.name for f in fields(cls)}
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"Unknown horse fields {sorted(unknown)} in '{data.get('name', '?')}'")
        return cls(**data)
