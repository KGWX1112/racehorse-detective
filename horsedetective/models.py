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
* races is the ordered list of race records. Each record's W/DH/L code comes
  from its official finish and outcome (see Race.result_code). When results
  and races are both recorded, validation requires them to agree.
"""

from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict, List, Optional

from .dates import RacingAge, age_under, date_bounds
from .text import normalize, normalize_country, normalize_grade, slugify

RESULT_CODES = ("W", "DH", "L")
WIN_CODES = ("W", "DH")

# The official result decides the code: a horse demoted from first loses, and
# a horse promoted to first wins. A walkover counts as a win and a start. A void
# race is not a start, so it has no code and counts nowhere a start would.
NON_FINISH_OUTCOMES = (
    "fell", "pulled_up", "unseated", "refused", "brought_down", "ran_out", "did_not_finish",
)
OUTCOMES = ("finished", "dead_heat", "walkover", "disqualified", "promoted") + NON_FINISH_OUTCOMES + ("void",)

LIST_FIELDS = (
    "nicknames", "trainers", "jockeys", "owners",
    "major_titles", "records", "raced_countries",
)
COMPLETABLE_FIELDS = LIST_FIELDS + ("results", "races")
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
class Race:
    """One start. Every field is optional; None means not recorded."""
    date: Optional[str] = None           # ISO 8601, partial allowed: "1875", "1875-06", "1875-06-12"
    race: Optional[str] = None           # name as published
    venue: Optional[str] = None
    country: Optional[str] = None        # normalized suffix
    grade: Optional[str] = None          # as published; compare with grade_key
    distance_m: Optional[float] = None
    distance_text: Optional[str] = None  # as published, e.g. "1m 2f"
    surface: Optional[str] = None
    finish: Optional[int] = None         # official position, 1 = won
    outcome: Optional[str] = None        # one of OUTCOMES
    field_size: Optional[int] = None
    jockey: Optional[str] = None
    trainer: Optional[str] = None
    notes: Optional[str] = None
    source: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.date, int) and not isinstance(self.date, bool):
            self.date = str(self.date)
        if isinstance(self.date, str):
            self.date = self.date.strip() or None
        self.country = normalize_country(self.country) if self.country else None
        if self.outcome is not None:
            self.outcome = normalize(self.outcome).replace(" ", "_")

    @property
    def result_code(self) -> Optional[str]:
        """W, DH, or L from the official result. None for a void race or when the record does not say."""
        if self.outcome == "void":
            return None
        if self.outcome == "walkover":
            return "W"
        if self.outcome == "disqualified" or self.outcome in NON_FINISH_OUTCOMES:
            return "L"
        if self.finish is None:
            return None
        if self.finish != 1:
            return "L"
        return "DH" if self.outcome == "dead_heat" else "W"

    @property
    def is_walkover(self) -> bool:
        return self.outcome == "walkover"

    @property
    def counts_as_start(self) -> bool:
        return self.outcome != "void"

    @property
    def grade_key(self) -> Optional[str]:
        return normalize_grade(self.grade) if self.grade else None

    def describe(self, index: int) -> str:
        parts = [p for p in (self.race, self.date) if p]
        return f"race {index}" + (f" ({', '.join(parts)})" if parts else "")

    def problems(self) -> List[str]:
        out = []
        if self.date is not None:
            try:
                date_bounds(self.date)
            except ValueError as e:
                out.append(str(e))
        if self.outcome is not None and self.outcome not in OUTCOMES:
            out.append(f"unknown outcome '{self.outcome}'; allowed {list(OUTCOMES)}")
        whole = {}
        for name in ("finish", "field_size"):
            v = getattr(self, name)
            if v is None:
                continue
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                out.append(f"{name} must be a whole number of at least 1")
            else:
                whole[name] = v
        d = self.distance_m
        if d is not None and (isinstance(d, bool) or not isinstance(d, (int, float)) or d <= 0):
            out.append("distance_m must be a positive number")
        if "finish" in whole and "field_size" in whole and whole["finish"] > whole["field_size"]:
            out.append(f"finish {self.finish} is outside a field of {self.field_size}")
        if self.outcome == "disqualified" and self.finish == 1:
            out.append("a disqualified horse cannot have an official finish of 1; "
                       "record the placing after the stewards' decision")
        if self.outcome == "walkover" and self.finish not in (None, 1):
            out.append("a walkover must have finish 1 or no finish")
        if self.outcome in NON_FINISH_OUTCOMES and self.finish is not None:
            out.append(f"outcome '{self.outcome}' means the horse did not finish, so finish must be empty")
        if self.outcome == "void" and self.finish is not None:
            out.append("a void race has no official result, so finish must be empty")
        return out

    @classmethod
    def from_dict(cls, data: Any) -> "Race":
        if isinstance(data, Race):
            return data
        if not isinstance(data, dict):
            raise ValueError(f"Each race must be an object, got {type(data).__name__}")
        unknown = set(data) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown race fields {sorted(unknown)} in race '{data.get('race', '?')}'")
        return cls(**data)


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
    races: Optional[List[Race]] = None
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
        if self.races is not None:
            if not isinstance(self.races, list):
                raise ValueError(f"Invalid horse '{self.name}': races must be a list")
            self.races = [Race.from_dict(r) for r in self.races]
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

        if self.races is not None:
            problems.extend(self._race_problems())

        if problems:
            raise ValueError(f"Invalid horse '{self.name}': " + "; ".join(problems))

    def _race_problems(self) -> List[str]:
        problems = []
        latest_start = None  # latest first-possible day among the races so far
        for i, r in enumerate(self.races, start=1):
            own = r.problems()
            problems.extend(f"{r.describe(i)}: {p}" for p in own)
            if r.date is None or any(p.startswith("date") for p in own):
                continue
            first, last = date_bounds(r.date)
            if self.foaled is not None and last.year < self.foaled:
                problems.append(f"{r.describe(i)} is dated before the foaling year {self.foaled}")
            if latest_start is not None and last < latest_start:
                problems.append(f"{r.describe(i)} is dated before an earlier race; races must be in career order")
            latest_start = first if latest_start is None else max(latest_start, first)

        counted = [(i, r) for i, r in enumerate(self.races, start=1) if r.counts_as_start]
        codes = [r.result_code for _, r in counted]
        if self.results is not None:
            if len(self.results) != len(counted):
                problems.append(f"results has {len(self.results)} entries but races has {len(counted)} starts")
            else:
                for code, (i, r) in zip(self.results, counted):
                    if r.result_code is not None and r.result_code != code:
                        problems.append(f"{r.describe(i)}: results says {code} "
                                        f"but the race record gives {r.result_code}")

        s = self.summary
        complete = self.is_complete("races")
        n, unknown = len(codes), codes.count(None)
        known_wins = sum(c in WIN_CODES for c in codes)
        if s.starts is not None and (s.starts != n if complete else s.starts < n):
            listed = "the complete race list has" if complete else "the race list already has"
            problems.append(f"summary.starts={s.starts} but {listed} {n} starts")
        if s.wins is not None and (s.wins < known_wins or (complete and s.wins > known_wins + unknown)):
            extra = f" and {unknown} with unknown results" if unknown else ""
            problems.append(f"summary.wins={s.wins} but the race list shows {known_wins} wins{extra}")

        race_countries = set(self.race_countries())
        if self.raced_countries is not None and self.is_complete("raced_countries"):
            missing = sorted(race_countries - set(self.raced_countries))
            if missing:
                problems.append(f"races include {missing}, which the complete raced_countries list does not")
        if self.international is False and self.country and race_countries - {self.country}:
            problems.append("international is false but the race list includes a race abroad")
        return problems

    # ------------------------------------------------------------------
    def is_complete(self, field_name: str) -> bool:
        return field_name in self.complete_fields

    def source_for(self, field_name: str) -> Optional[str]:
        own = self.sources.get(field_name)
        if own:
            return own
        if field_name == "races" and self.races:
            per_race = list(dict.fromkeys(r.source for r in self.races if r.source))
            if per_race:
                return "; ".join(per_race)
        return self.sources.get("*")

    def starts_list(self) -> Optional[List[Race]]:
        """The race records that count as starts, which leaves out void races."""
        if self.races is None:
            return None
        return [r for r in self.races if r.counts_as_start]

    def derived_results(self) -> Optional[List[str]]:
        """W/DH/L codes from races, or None if races is unrecorded or any start's result is unknown."""
        starts = self.starts_list()
        if starts is None:
            return None
        codes = [r.result_code for r in starts]
        return None if None in codes else codes

    def age_at(self, race: Race) -> Optional[RacingAge]:
        """Racing age on the race date, or None if the foaling year or the race date is unknown."""
        if self.foaled is None or race.date is None:
            return None
        return RacingAge(age_under(self.foaled, self.country, race.date),
                         age_under(self.foaled, race.country, race.date))

    def race_countries(self) -> Optional[List[str]]:
        """Distinct countries of the starts, in order of first appearance."""
        starts = self.starts_list()
        if starts is None:
            return None
        return list(dict.fromkeys(r.country for r in starts if r.country))

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
