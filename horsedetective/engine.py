"""
Investigation engine.

Scoring:
  hard clue, CONTRADICTION  -> candidate eliminated
  MATCH                     -> +weight
  soft clue, CONTRADICTION  -> -weight
  UNKNOWN                   -> 0

Verdicts:
  NO_MATCH  no candidate survives the hard clues
  TIE       two or more survivors share the top score
  SOLVED    unique top candidate matches every clue, and every other
            survivor contradicts at least one clue
  LEADING   unique top candidate, but it has unknowns or contradictions,
            or another survivor has not been ruled out
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .evaluators import Clue, Finding, Status
from .models import Horse


@dataclass
class Evidence:
    index: int
    clue: Clue
    finding: Finding

    @property
    def eliminates(self) -> bool:
        return self.clue.hard and self.finding.status == Status.CONTRADICTION

    @property
    def points(self) -> int:
        s = self.finding.status
        if s == Status.MATCH:
            return self.clue.weight
        if s == Status.CONTRADICTION and not self.clue.hard:
            return -self.clue.weight
        return 0


@dataclass
class Candidate:
    horse: Horse
    evidence: List[Evidence]

    @property
    def score(self) -> int:
        return sum(e.points for e in self.evidence)

    @property
    def max_possible(self) -> int:
        return sum(e.clue.weight for e in self.evidence)

    def count(self, status: Status) -> int:
        return sum(e.finding.status == status for e in self.evidence)

    @property
    def eliminated_by(self) -> List[Evidence]:
        return [e for e in self.evidence if e.eliminates]

    @property
    def all_matched(self) -> bool:
        return self.count(Status.MATCH) == len(self.evidence)


@dataclass
class Case:
    name: str
    clues: List[Clue]
    notes: str = ""
    expected: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Case":
        if not data.get("clues"):
            raise ValueError(f"Case '{data.get('name', '?')}' has no clues")
        return cls(
            name=data.get("name", "Unnamed case"),
            clues=[Clue.from_dict(c) for c in data["clues"]],
            notes=data.get("notes", ""),
            expected=data.get("expected"),
        )


@dataclass
class Verdict:
    code: str
    answer_id: Optional[str]
    summary: str


@dataclass
class Investigation:
    case: Case
    survivors: List[Candidate]
    eliminated: List[Candidate]
    verdict: Verdict
    tied_ids: List[str] = field(default_factory=list)


def investigate(horses: List[Horse], case: Case) -> Investigation:
    candidates = [
        Candidate(h, [Evidence(i, c, c.evaluate(h)) for i, c in enumerate(case.clues, start=1)])
        for h in horses
    ]
    survivors = [c for c in candidates if not c.eliminated_by]
    eliminated = [c for c in candidates if c.eliminated_by]

    # Score first, then fewer contradictions, then fewer unknowns, then name.
    # Name ordering keeps output deterministic; ties are still reported as ties.
    survivors.sort(key=lambda c: (
        -c.score, c.count(Status.CONTRADICTION), c.count(Status.UNKNOWN), c.horse.name.casefold()
    ))
    eliminated.sort(key=lambda c: c.horse.name.casefold())

    verdict, tied = _verdict(survivors, len(horses))
    return Investigation(case, survivors, eliminated, verdict, tied)


def _verdict(survivors: List[Candidate], total: int):
    if not survivors:
        return Verdict("NO_MATCH", None,
                       f"None of the {total} horses in the database satisfies every hard clue."), []

    top = survivors[0]
    tied = [c for c in survivors if c.score == top.score]
    if len(tied) > 1:
        names = ", ".join(c.horse.label for c in tied)
        return Verdict("TIE", None, f"{len(tied)} candidates share the top score of {top.score:+}: {names}."), \
            [c.horse.id for c in tied]

    not_ruled_out = [c for c in survivors[1:] if c.count(Status.CONTRADICTION) == 0]
    if top.all_matched and not not_ruled_out:
        return Verdict("SOLVED", top.horse.id,
                       f"{top.horse.label} matches all {len(top.evidence)} clues; "
                       f"every other candidate is eliminated or contradicted."), []

    reasons = []
    u, x = top.count(Status.UNKNOWN), top.count(Status.CONTRADICTION)
    if u:
        reasons.append(f"{u} clue(s) unverified")
    if x:
        reasons.append(f"{x} clue(s) contradicted")
    if not_ruled_out:
        reasons.append("not ruled out: " + ", ".join(c.horse.label for c in not_ruled_out))
    return Verdict("LEADING", top.horse.id, f"{top.horse.label} leads; " + "; ".join(reasons) + "."), []
