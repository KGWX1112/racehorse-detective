# Horse detective v0.1

A clue-based search engine for racehorses. You keep a database of horses, write a case as a list of structured clues, and the engine eliminates, scores, and ranks candidates, then prints the evidence for each one with its sources.

Requires Python 3.9 or later. Standard library only.

## Quick start

```
python -m horsedetective import data/seed_horses.json
python -m horsedetective bench cases/benchmarks.json
python -m horsedetective solve cases/original_sample.json
```

The database defaults to `horses.db` in the current directory. Use `--db path` to choose another file.

## Commands

| Command | Purpose |
|---|---|
| `import FILE` | Add or update horses from JSON |
| `export FILE` | Write the whole database to JSON |
| `list [TEXT]` | List horses, optionally filtered by name or id |
| `show ID` | Print one horse as JSON |
| `add` | Add a horse through prompts |
| `set ID FIELD [VALUE]` | Edit one field; accepts `--source`, `--complete`, `--incomplete`, `--clear` |
| `delete ID` | Remove a horse |
| `solve FILE` | Run every case in a file; `--case NAME` runs one, `--brief` hides evidence |
| `bench FILE` | Compare verdicts against expected answers; exits 1 on any failure |
| `clues` | List clue types and their parameters |

Examples:

```
python -m horsedetective set harbor-lantern-ire-1955 trainers "P. Doyle, M. Keane" --source "Stud book, vol. 3"
python -m horsedetective set harbor-lantern-ire-1955 trainers --complete
python -m horsedetective set old-tempest-gb-1871 starts 30 --source "Racing calendar 1875"
```

## How data is interpreted

A field set to `null` is unknown. The engine never counts unknown data against a horse.

A field listed in `complete_fields` is the horse's full record for that field. Only a complete field can produce a contradiction from absence. If Silver Comet's `major_titles` is marked complete and does not include the Kentucky Derby, a Kentucky Derby clue contradicts. If the list is not marked complete, the clue returns unknown.

Race results use three codes, in career order: `W` for a win, `DH` for a dead heat for first (counted as a win), and `L` for any other finish. `D` is rejected because it is ambiguous.

Career starts and wins come from `summary`, or are counted from `results` or `races` when that list is complete. The summary and the lists must agree when both are present.

International status comes from `raced_countries` and the countries in `races`, compared with `country`, when available, and from the `international` flag otherwise.

`sources` maps a field name to a citation. `"*"` is the fallback for fields without their own entry, and all summary counts share the key `"summary"`. The report prints the source next to each piece of evidence.

Ids are built from name, country suffix, and foaling year, e.g. `silver-comet-jpn-2001`. The id does not change if you later edit those fields.

## Race records

`races` lists a horse's starts in career order. Each race is an object, and every field is optional.

| Field | Meaning |
|---|---|
| `date` | ISO 8601. Partial dates are allowed: `"1875"`, `"1875-06"`, `"1875-06-12"` |
| `race` | Race name as published |
| `venue` | Racecourse |
| `country` | Country of the race, stored as a suffix code |
| `grade` | Grade as published, e.g. `"G1"`, `"Grade 1"`, `"Listed"` |
| `distance_m` | Distance in metres |
| `distance_text` | Distance as published, e.g. `"1m 2f"` |
| `surface` | Racing surface |
| `finish` | Official finishing position; 1 means won |
| `outcome` | `finished`, `dead_heat`, `walkover`, `disqualified`, `promoted`, `fell`, `pulled_up`, `unseated`, `refused`, `brought_down`, `ran_out`, or `did_not_finish` |
| `field_size`, `jockey`, `trainer`, `notes`, `source` | As named |

Each race gets a W, DH, or L code from its official result. A dead heat for first is `DH`. A walkover counts as a win and as a start. A horse disqualified from first counts as a loss, and a horse promoted to first counts as a win. Any outcome where the horse did not finish is a loss. A race with no finish and no deciding outcome has an unknown result.

Race records cannot be entered with `set`. Put them in a JSON file and use `import`. Mark the list complete with `set ID races --complete`.

Validation rejects races whose dates go backwards. A partial date conflicts with another date only when their ranges cannot overlap, so `"1875"` may follow `"1875-06-12"`. When a horse has both `results` and `races`, the two must have the same length, and every known race result must match its code in `results`. A complete race list must match `summary.starts`, and a partial list cannot show more races or wins than the summary.

When `results` is absent, the streak, unbeaten, and career clues use the codes derived from `races`. Starts and wins are counted only from a complete race list. A race abroad shows that the horse raced internationally even when the race list is partial.

Grades compare through a normalized form, so "G1", "Group 1", "Grade 1", and "Grade I" are equal. The published text is kept.

## How cases are scored

Each clue is hard or soft and has a weight (default 10).

A hard clue that contradicts eliminates the horse. A match adds the weight, a soft contradiction subtracts it, and unknown adds nothing.

The verdict is one of four codes. `NO_MATCH` means no horse survived the hard clues. `TIE` means two or more survivors share the top score. `SOLVED` means one horse matched every clue and every other survivor contradicts at least one clue. `LEADING` covers every other case where one horse has the top score, and the report says what keeps it from `SOLVED`: its own unknowns or contradictions, or other survivors that nothing has ruled out.

## Case file format

```json
{
  "name": "kentucky-monarch",
  "clues": [
    {"description": "Won the Kentucky Derby", "type": "title",
     "params": {"text": "Kentucky Derby"}, "hard": true},
    {"description": "Nickname contains 'Monarch'", "type": "nickname",
     "params": {"text": "Monarch"}, "weight": 8}
  ],
  "expected": {"verdict": "SOLVED", "answer": "crimson-monarch-usa-1998"}
}
```

A file can hold one case or `{"cases": [...]}`. `expected` is only read by `bench`.

Text clues match whole words after lowercasing and stripping punctuation, so "Monarch" matches "The Monarch" and does not match "Monarchy". Titles default to exact matching; nicknames, records, and people default to `contains`. Set `"mode"` in `params` to override.

## Benchmark

`cases/benchmarks.json` has twelve cases against the eight seed horses. The first nine come from V0.1. They cover the prototype case in soft and hard form (both end in a tie, because Crimson Monarch's longest streak is six), elimination by title and date, inference from a summary-only career, a sparse-data horse that stays unresolved, a no-match case, counts derived from a complete race list, international status derived from venues, and word-boundary matching. The other three cover race records: a career derived from a complete race list, racing abroad shown by a partial race list, and a streak that stays unknown on a partial race list.

All eight seed horses are fictional. Old Tempest and Harbor Lantern were added to test horses with a career summary and no race order. Copper Wren has a complete race list that includes a walkover, a dead heat for first, a disqualification from first, a pulled-up run, and a promotion to first. Juniper Vale has a career summary and a partial race list.

Run the benchmark after every change. Add a case each time you find a behavior you want to keep.

## Unit tests

`tests/` holds `unittest` tests for the career and text helpers, race records, the evaluators, and command-line behavior that the benchmark cannot check. Run them from the repository root with `python -m unittest`. They need no network access.

## Adding a clue type

Write a function in `horsedetective/evaluators.py` that takes a horse and the clue's params and returns a `Finding` with a status, an explanation, and the fields it relied on. Register it with `@evaluator("name", required=(...))`.

## Known limits

Race records store dates, venues, grades, and distances, but no clue type reads those fields yet. The evaluators see only the codes, counts, and countries derived from them.

If any race in a list has an unknown result, the derived code sequence as a whole is unknown. Streak clues then return unknown for that horse, even when the known races would settle them.

Grade matching knows the G, Group, Grade, and Listed forms. Other published grades, such as Japan's Jpn1, compare as plain text.

Title matching has no aliases, so a race that was renamed or sponsored under different names needs each name entered. Synonyms are V0.3.

Weights are set by hand. The score ranks candidates within one case and is not a probability.

If you replace a field that is marked complete, such as `results`, `set` keeps the complete mark and prints a warning. Add `--incomplete` when the new value is partial.
