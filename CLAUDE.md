# Horse detective

A Python tool that identifies historical racehorses from clues. The owner (Kenneth) uses it for personal research; it is not distributed. The owner keeps a manual database of horses, writes a case as structured clues, and the engine eliminates, scores, and ranks candidates, then prints a case report with sources.

Roadmap: `docs/ROADMAP.md`. Current task: `docs/v0.2-plan.md`. Read both at the start of a session that changes code.

## Commands

```
python -m horsedetective import data/seed_horses.json
python -m horsedetective bench cases/benchmarks.json
python -m horsedetective solve cases/original_sample.json
python -m horsedetective clues
```

Python 3.9 or later. The core package uses only the standard library. Any new dependency needs the owner's approval, and it goes in an optional extra so the core stays stdlib-only.

## Layout

| Path | Contents |
|---|---|
| `horsedetective/models.py` | `Horse`, `CareerSummary`, validation, id generation |
| `horsedetective/evaluators.py` | `Clue`, `Finding`, `Status`, the `@evaluator` registry, all clue types |
| `horsedetective/engine.py` | Elimination, scoring, ranking, verdicts |
| `horsedetective/report.py` | Plain-text case report and timeline |
| `horsedetective/dates.py` | Partial dates, the racing-age table, `RacingAge` |
| `horsedetective/store.py` | SQLite storage (validated JSON per row) |
| `horsedetective/text.py` | Normalization, whole-word matching, country suffixes |
| `horsedetective/cli.py` | argparse commands |
| `data/seed_horses.json` | Ten fictional test horses |
| `cases/benchmarks.json` | Cases with expected verdicts |
| `tests/` | `unittest` tests, run with `python -m unittest` |

## Invariants

Do not change any of these without asking the owner first.

1. A field set to `None` is unknown. Missing data produces a contradiction only when the field is listed in `complete_fields`.
2. Every evaluator returns MATCH, CONTRADICTION, or UNKNOWN with an explanation and the fields it used.
3. A hard clue that contradicts eliminates the horse. A match adds the weight, a soft contradiction subtracts it, and unknown adds nothing.
4. Verdicts are `NO_MATCH`, `TIE`, `SOLVED`, and `LEADING`, defined in the `engine.py` docstring. `SOLVED` is strict: every other survivor must contradict at least one clue.
5. Result codes are `W`, `DH` (dead heat for first, counts as a win), and `L`. `D` is rejected as ambiguous.
6. International means raced outside the country of foaling.
7. Horse ids are `name-country-foaled` slugs and never change after creation.
8. Every stored fact should have a source in `sources`. Importers set sources automatically. Importers never add a field to `complete_fields`; only the owner can assert that a record is complete.
9. Stored rows from earlier versions must keep loading. Schema changes need backward-compatible `from_dict` handling, and `export` then `import` must round-trip.
10. Text clues match whole words after normalization, so "Monarch" matches "The Monarch" and not "Monarchy".

## Data integrity

Do not add real horses, or facts about real horses, from model knowledge. Real data enters the database only through an importer that records a source URL, or through the owner. Test data stays fictional unless it comes from a saved fixture with attribution.

## Workflow

1. Work on a branch per version (`v0.2`) and commit at each milestone in the version plan.
2. Run `bench` before every commit. All cases must pass.
3. Never edit an expected verdict to make a failing case pass. If a behavior change is intended, stop and tell the owner which cases change and why.
4. Every new clue type or behavior gets at least one benchmark case. Unit tests go in `tests/` using `unittest` and run with `python -m unittest`.
5. Tests run offline. Network code is tested against saved fixtures.
6. Ask before adding a dependency, changing an invariant, changing verdict codes, or deleting data or case files.
7. Tag each finished version (`v0.2.0`).

## Writing conventions

These apply to the README, docs, report text, comments, and commit messages. No em dashes. Sentence case headings. Active voice. Prose over bullets in narrative sections. No inflated or promotional language, no filler, no praise. State limits and uncertainty plainly.
