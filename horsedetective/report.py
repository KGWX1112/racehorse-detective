"""Plain-text case report and career timeline."""

from typing import List, Optional

from .dates import birthday_text
from .engine import Candidate, Investigation
from .evaluators import Status
from .models import NON_FINISH_OUTCOMES, WIN_CODES, Horse, Race

SYMBOL = {Status.MATCH: "+", Status.CONTRADICTION: "x", Status.UNKNOWN: "?"}
RULE = "=" * 72


def _tally(c: Candidate) -> str:
    return (f"{c.count(Status.MATCH)} matched, "
            f"{c.count(Status.CONTRADICTION)} contradicted, "
            f"{c.count(Status.UNKNOWN)} unknown")


def _evidence_block(c: Candidate) -> List[str]:
    lines = [RULE, c.horse.label, f"id: {c.horse.id}", RULE]
    for e in c.evidence:
        tag = "HARD" if e.clue.hard else f"w{e.clue.weight}"
        lines.append(f"  {SYMBOL[e.finding.status]} [{e.finding.status.value}] ({tag}) {e.index}. {e.clue.description}")
        lines.append(f"      {e.finding.explanation}")
        if e.finding.fields:
            srcs = sorted({f"{f}: {c.horse.source_for(f) or 'not recorded'}" for f in e.finding.fields})
            lines.append("      sources: " + "; ".join(srcs))
    status = "ELIMINATED" if c.eliminated_by else f"score {c.score:+} of {c.max_possible}"
    lines.append(f"  RESULT: {status}")
    lines.append("")
    return lines


def render(inv: Investigation, verbose: bool = True) -> str:
    out = [RULE, f"CASE: {inv.case.name}", RULE]
    if inv.case.notes:
        out.append(inv.case.notes)
    out.append("")
    out.append(f"VERDICT: {inv.verdict.code}")
    out.append(f"  {inv.verdict.summary}")
    out.append("")

    out.append("CLUES")
    for i, clue in enumerate(inv.case.clues, start=1):
        tag = "HARD" if clue.hard else f"soft, weight {clue.weight}"
        out.append(f"  {i}. {clue.description}  [{clue.type}; {tag}]")
    out.append("")

    out.append("SURVIVING CANDIDATES")
    if not inv.survivors:
        out.append("  (none)")
    for rank, c in enumerate(inv.survivors, start=1):
        tie = "  [TIED]" if c.horse.id in inv.tied_ids else ""
        out.append(f"  {rank:>2}. {c.horse.label:<34} {c.score:+4} of {c.max_possible:<3} {_tally(c)}{tie}")
    out.append("")

    out.append("ELIMINATED BY HARD CLUES")
    if not inv.eliminated:
        out.append("  (none)")
    for c in inv.eliminated:
        first = c.eliminated_by[0]
        more = f" (+{len(c.eliminated_by) - 1} more)" if len(c.eliminated_by) > 1 else ""
        out.append(f"  - {c.horse.label}: clue {first.index}, {first.finding.explanation}{more}")
    out.append("")

    if verbose:
        out.append("EVIDENCE")
        for c in inv.survivors + inv.eliminated:
            out.extend(_evidence_block(c))

    return "\n".join(out)


# ============================================================
# Timeline
# ============================================================

def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _finish_text(r: Race) -> str:
    if r.outcome in ("void", "walkover") or r.outcome in NON_FINISH_OUTCOMES:
        return r.outcome.replace("_", " ")
    if r.finish is None:
        return "disqualified" if r.outcome == "disqualified" else "?"
    text = _ordinal(r.finish) + (f" of {r.field_size}" if r.field_size else "")
    if r.outcome in ("dead_heat", "disqualified", "promoted"):
        text += f" ({r.outcome.replace('_', ' ')})"
    return text


def _venue_text(r: Race) -> str:
    if r.venue and r.country:
        return f"{r.venue} ({r.country})"
    return r.venue or (f"({r.country})" if r.country else "")


class _Streak:
    """Running count of consecutive wins. After an unknown result it is a lower bound."""

    def __init__(self):
        self.wins, self.exact = 0, True

    def add(self, code: Optional[str]) -> None:
        if code in WIN_CODES:
            self.wins += 1
        else:
            self.wins, self.exact = 0, code is not None

    def __str__(self) -> str:
        if self.exact:
            return str(self.wins)
        return f"{self.wins}+" if self.wins else "?"


def _table(header: List[str], rows: List[List[str]]) -> List[str]:
    widths = [max(len(cell) for cell in col) for col in zip(header, *rows)]
    lines = []
    for cells in [header] + rows:
        first = cells[0].rjust(widths[0])
        rest = [c.ljust(w) for c, w in zip(cells[1:], widths[1:])]
        lines.append("  ".join([first] + rest).rstrip())
    return lines


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _age_note(h: Horse) -> str:
    if h.foaled is None:
        return "Age: unknown, because the foaling year is not recorded."
    if not h.country:
        gap = "the country of foaling is not recorded"
    elif birthday_text(h.country) is None:
        gap = f"{h.country} has no official birthday in the table"
    else:
        return (f"Age: counted from the {h.country} official birthday, {birthday_text(h.country)}. Where the "
                f"race country's birthday gives a different age, that age follows after a slash.")
    return (f"Age: {gap}, so the first figure is unknown. The figure after the slash uses the "
            f"race country's birthday.")


def render_timeline(h: Horse) -> str:
    out = [h.label, f"id: {h.id}"]
    if not h.summary.is_empty():
        s = h.summary
        parts = [f"{getattr(s, f)} {f}" for f in ("starts", "wins", "seconds", "thirds") if getattr(s, f) is not None]
        out.append("Career summary: " + ", ".join(parts) + ".")

    if h.races:
        codes = iter(h.results) if h.results is not None else None
        streak, rows, unknown_seen = _Streak(), [], False
        for i, r in enumerate(h.races, start=1):
            if r.counts_as_start:
                code = next(codes) if codes is not None else r.result_code
                unknown_seen = unknown_seen or code is None
                streak.add(code)
            rows.append([str(i), r.date or "?", str(h.age_at(r) or "?"), r.race or "",
                         _venue_text(r), r.grade or "", _finish_text(r), str(streak)])
        state = "marked complete" if h.is_complete("races") else "not marked complete"
        out.append(f"{_plural(len(h.races), 'race record')}, {state}.")
        out.append(_age_note(h))
        note = "Streak: consecutive wins up to each race. A walkover counts as a win, and a void race is not a start."
        if not h.is_complete("races"):
            note += " The list is partial, so the streak counts only the recorded races."
        if unknown_seen:
            note += " After a race with an unknown result, N+ means at least N."
        out.append(note)
        out.append("")
        out.extend(_table(["#", "date", "age", "race", "venue", "grade", "finish", "streak"], rows))
        source_field = "races"
    elif h.results:
        streak, rows = _Streak(), []
        for i, code in enumerate(h.results, start=1):
            streak.add(code)
            rows.append([str(i), code, str(streak)])
        state = "marked complete" if h.is_complete("results") else "not marked complete"
        out.append(f"{_plural(len(h.results), 'result')}, {state}. Only W/DH/L codes are recorded, "
                   f"so there are no dates or race details.")
        out.append("")
        out.extend(_table(["#", "result", "streak"], rows))
        source_field = "results"
    else:
        out.append("No race records or results recorded.")
        return "\n".join(out)

    out.append("")
    out.append(f"sources: {source_field}: {h.source_for(source_field) or 'not recorded'}")
    return "\n".join(out)
