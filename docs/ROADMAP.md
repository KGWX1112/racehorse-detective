# Roadmap

Each version keeps every earlier benchmark case passing and adds its own.

## V0.1 (done)

Manual horse database in SQLite. Structured clues with a registry of evaluators. Tri-state findings (match, contradiction, unknown) with completeness flags. Hard and soft clues. Scoring, ranking, and verdicts with tie and no-match reporting. Sources stored per field and printed with each piece of evidence. Benchmark file with nine cases.

## V0.2 (current)

Race records replace the W/DH/L list as the primary career data. Career timelines, streak detection over race records, and race-result pattern matching (won at a given age, lost on first start abroad, unbeaten at a given grade). A single-article Wikipedia importer that fills infobox fields and records the article as the source. Unit tests. Plan: `docs/v0.2-plan.md`.

## V0.3

Fuzzy and poetic clue interpretation. The interpreter turns free text into the same structured clues V0.1 uses, states the reading it chose, and scores each reading when a clue has more than one. Synonyms and aliases, including renamed and sponsored race names. Number and date extraction from clue text.

## V0.4

Relationship graph linking horses to trainers, jockeys, owners, sires, and dams. Clue types that follow those links (a sire's other winners, a jockey's partners).

## V0.5

Web research layer that gathers primary-source evidence for horses already in the database. Source citations attached to individual findings.

## V0.6

Candidate discovery. Use the hard clues of a new case to search for horses that are not in the database, import them, then investigate. V0.5 verifies known candidates; V0.6 finds new ones.

## V1.0

Given a new four-clue puzzle, the engine generates candidates, investigates them, shows evidence, rejects alternatives, and produces a final case report.
