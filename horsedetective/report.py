"""Plain-text case report."""

from typing import List

from .engine import Candidate, Investigation
from .evaluators import Status

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
