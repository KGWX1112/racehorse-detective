"""
Command-line interface.

  python -m horsedetective import data/seed_horses.json
  python -m horsedetective list
  python -m horsedetective show silver-comet-jpn-2001
  python -m horsedetective add
  python -m horsedetective set silver-comet-jpn-2001 trainers "M. Hale" --source "Racing annual, 2005"
  python -m horsedetective set silver-comet-jpn-2001 results --complete
  python -m horsedetective solve cases/original_sample.json
  python -m horsedetective bench cases/benchmarks.json
  python -m horsedetective clues
"""

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

from .engine import Case, investigate
from .evaluators import EVALUATORS
from .models import COMPLETABLE_FIELDS, LIST_FIELDS, SUMMARY_FIELDS, Horse, make_horse_id
from .report import render
from .store import HorseStore

STR_FIELDS = ("name", "country", "sex", "notes")
SETTABLE = STR_FIELDS + ("foaled", "international", "results") + LIST_FIELDS + SUMMARY_FIELDS


# ============================================================
# Helpers
# ============================================================

def _load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_cases(path: str) -> List[Case]:
    data = _load_json(path)
    raw = data["cases"] if isinstance(data, dict) and "cases" in data else [data]
    return [Case.from_dict(c) for c in raw]


def _parse_bool(raw: str) -> bool:
    v = raw.strip().casefold()
    if v in ("true", "yes", "y", "1"):
        return True
    if v in ("false", "no", "n", "0"):
        return False
    raise ValueError(f"Expected true or false, got '{raw}'")


def _parse_value(field: str, raw: str) -> Any:
    if field in LIST_FIELDS:
        return [s.strip() for s in raw.split(",") if s.strip()]
    if field == "results":
        return [s for s in re.split(r"[\s,]+", raw.strip()) if s]
    if field == "international":
        return _parse_bool(raw)
    if field == "foaled" or field in SUMMARY_FIELDS:
        return int(raw)
    return raw


def _source_key(field: str) -> str:
    return "summary" if field in SUMMARY_FIELDS else field


def _ask(prompt: str) -> str:
    try:
        return input(f"{prompt}: ").strip()
    except EOFError:
        return ""


def _ask_yes(prompt: str) -> bool:
    return _ask(f"{prompt} [y/N]").casefold() in ("y", "yes")


def _require_horse(store: HorseStore, horse_id: str) -> Horse:
    horse = store.get(horse_id)
    if horse is None:
        matches = store.find(horse_id)
        hint = ("\nDid you mean: " + ", ".join(h.id for h in matches[:5])) if matches else ""
        raise SystemExit(f"No horse with id '{horse_id}'.{hint}")
    return horse


# ============================================================
# Commands
# ============================================================

def cmd_import(store: HorseStore, args) -> None:
    data = _load_json(args.file)
    rows = data["horses"] if isinstance(data, dict) else data
    horses = [Horse.from_dict(r) for r in rows]  # validate everything before writing
    for h in horses:
        store.upsert(h)
    print(f"Imported {len(horses)} horses into {args.db}.")


def cmd_export(store: HorseStore, args) -> None:
    rows = [h.to_dict() for h in store.all()]
    with open(args.file, "w", encoding="utf-8") as f:
        json.dump({"horses": rows}, f, indent=2, ensure_ascii=False)
    print(f"Exported {len(rows)} horses to {args.file}.")


def cmd_list(store: HorseStore, args) -> None:
    horses = store.find(args.filter) if args.filter else store.all()
    if not horses:
        print("No horses found.")
        return
    for h in horses:
        s = h.summary
        record = f"{s.starts}-{s.wins}" if s.starts is not None and s.wins is not None else ""
        seq = f"{len(h.results)} races{' (complete)' if h.is_complete('results') else ''}" if h.results else ""
        print(f"{h.id:<34} {h.label:<34} {record:<8} {seq}")


def cmd_show(store: HorseStore, args) -> None:
    print(json.dumps(_require_horse(store, args.id).to_dict(), indent=2, ensure_ascii=False))


def cmd_add(store: HorseStore, args) -> None:
    print("Add a horse. Leave any field blank if it is not known.\n")
    name = _ask("Name")
    if not name:
        raise SystemExit("A name is required.")
    country = _ask("Country of foaling (name or suffix, e.g. GB, USA, JPN)") or None
    foaled_raw = _ask("Foaling year")
    foaled = int(foaled_raw) if foaled_raw else None

    d: Dict[str, Any] = {"name": name, "country": country, "foaled": foaled,
                         "complete_fields": [], "sources": {}, "summary": {}}
    preview = Horse(name=name, country=country, foaled=foaled)
    if store.get(preview.id):
        raise SystemExit(f"'{preview.id}' already exists. Use 'set' to edit it.")

    source = _ask("Source for the facts you enter now (blank if none)")
    entered: List[str] = []

    for f in LIST_FIELDS:
        raw = _ask(f"{f.replace('_', ' ').capitalize()} (comma-separated)")
        if raw:
            d[f] = _parse_value(f, raw)
            entered.append(f)
            if _ask_yes(f"  Is that the complete {f.replace('_', ' ')} list?"):
                d["complete_fields"].append(f)

    raw = _ask("Race results in order (W, DH, L separated by spaces)")
    if raw:
        d["results"] = _parse_value("results", raw)
        entered.append("results")
        if _ask_yes("  Is that the whole career?"):
            d["complete_fields"].append("results")

    for f in SUMMARY_FIELDS:
        raw = _ask(f"Career {f}")
        if raw:
            d["summary"][f] = int(raw)
            if "summary" not in entered:
                entered.append("summary")

    if "raced_countries" not in d:
        raw = _ask("Raced outside its home country? (y/n, blank = unknown)")
        if raw:
            d["international"] = _parse_bool(raw)
            entered.append("international")

    if source:
        for f in entered + ["name", "country", "foaled"]:
            d["sources"][f] = source

    horse = Horse.from_dict(d)
    store.upsert(horse)
    print(f"\nSaved {horse.label} as '{horse.id}'.")


def cmd_set(store: HorseStore, args) -> None:
    field = args.field.removeprefix("summary.")
    if field not in SETTABLE:
        raise SystemExit(f"Cannot set '{args.field}'. Settable fields: {', '.join(SETTABLE)}")
    horse = _require_horse(store, args.id)
    d = horse.to_dict()

    if args.clear:
        if field in SUMMARY_FIELDS:
            d["summary"][field] = None
        elif field == "name":
            raise SystemExit("Name cannot be cleared.")
        else:
            d[field] = None
        d["complete_fields"] = [f for f in d["complete_fields"] if f != field]
    elif args.value is not None:
        value = _parse_value(field, args.value)
        if field in SUMMARY_FIELDS:
            d["summary"][field] = value
        else:
            d[field] = value

    if args.complete or args.incomplete:
        if field not in COMPLETABLE_FIELDS:
            raise SystemExit(f"'{field}' cannot be marked complete. Completable: {', '.join(COMPLETABLE_FIELDS)}")
        d["complete_fields"] = [f for f in d["complete_fields"] if f != field]
        if args.complete:
            d["complete_fields"].append(field)

    if args.source:
        d["sources"][_source_key(field)] = args.source

    updated = Horse.from_dict(d)  # re-validates; the id stays fixed even if name/country/foaled change
    store.upsert(updated)
    print(f"Updated {updated.label}: {field}.")
    replaced = getattr(updated, field, None) != getattr(horse, field, None)
    if replaced and updated.is_complete(field) and not args.complete:
        print(f"Warning: '{field}' is still marked complete. If the new value is not the full record, "
              f"remove the mark with --incomplete.", file=sys.stderr)
    if field in ("name", "country", "foaled"):
        new_id = make_horse_id(updated.name, updated.country, updated.foaled)
        if new_id != updated.id:
            print(f"Note: id stays '{updated.id}' (a fresh entry would be '{new_id}').")


def cmd_delete(store: HorseStore, args) -> None:
    horse = _require_horse(store, args.id)
    if not args.yes and not _ask_yes(f"Delete {horse.label}?"):
        print("Cancelled.")
        return
    store.delete(horse.id)
    print(f"Deleted {horse.label}.")


def cmd_solve(store: HorseStore, args) -> None:
    horses = store.all()
    if not horses:
        raise SystemExit("The database is empty. Run 'import data/seed_horses.json' first.")
    cases = _load_cases(args.file)
    if args.case:
        cases = [c for c in cases if c.name == args.case]
        if not cases:
            raise SystemExit(f"No case named '{args.case}' in {args.file}.")
    for case in cases:
        print(render(investigate(horses, case), verbose=not args.brief))
        print()


def cmd_bench(store: HorseStore, args) -> None:
    horses = store.all()
    if not horses:
        raise SystemExit("The database is empty. Run 'import data/seed_horses.json' first.")
    cases = [c for c in _load_cases(args.file) if c.expected]
    failures = 0
    for case in cases:
        inv = investigate(horses, case)
        want_verdict = case.expected.get("verdict")
        want_answer = case.expected.get("answer")
        ok = inv.verdict.code == want_verdict and inv.verdict.answer_id == want_answer
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {case.name}")
        if not ok:
            print(f"      expected {want_verdict} / {want_answer}")
            print(f"      got      {inv.verdict.code} / {inv.verdict.answer_id}")
            print(f"      {inv.verdict.summary}")
            if args.verbose:
                print(render(inv))
    print(f"\n{len(cases) - failures} of {len(cases)} benchmark cases passed.")
    if failures:
        sys.exit(1)


def cmd_clues(store: Optional[HorseStore], args) -> None:
    for name, spec in sorted(EVALUATORS.items()):
        params = list(spec.required) + ([f"one of {list(spec.any_of)}"] if spec.any_of else [])
        print(f"{name}")
        print(f"    {spec.doc}")
        print(f"    required params: {params or 'none'}")


# ============================================================
# Entry point
# ============================================================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="horsedetective", description="Racehorse detective engine, v0.1")
    p.add_argument("--db", default="horses.db", help="SQLite database path (default: horses.db)")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("import", help="Add or update horses from a JSON file")
    s.add_argument("file")
    s.set_defaults(func=cmd_import)

    s = sub.add_parser("export", help="Write every horse to a JSON file")
    s.add_argument("file")
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("list", help="List horses, optionally filtered by name or id")
    s.add_argument("filter", nargs="?")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("show", help="Print one horse as JSON")
    s.add_argument("id")
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("add", help="Add a horse interactively")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("set", help="Edit one field of a horse")
    s.add_argument("id")
    s.add_argument("field", help="e.g. trainers, results, starts, foaled, international")
    s.add_argument("value", nargs="?", help="Lists are comma-separated; results are space-separated")
    s.add_argument("--source", help="Citation for this field")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--complete", action="store_true", help="Mark the field as the full record")
    g.add_argument("--incomplete", action="store_true", help="Remove the complete mark")
    s.add_argument("--clear", action="store_true", help="Set the field back to unknown")
    s.set_defaults(func=cmd_set)

    s = sub.add_parser("delete", help="Remove a horse")
    s.add_argument("id")
    s.add_argument("--yes", action="store_true", help="Skip confirmation")
    s.set_defaults(func=cmd_delete)

    s = sub.add_parser("solve", help="Run the case(s) in a JSON file and print reports")
    s.add_argument("file")
    s.add_argument("--case", help="Run only the case with this name")
    s.add_argument("--brief", action="store_true", help="Omit per-candidate evidence")
    s.set_defaults(func=cmd_solve)

    s = sub.add_parser("bench", help="Run benchmark cases and compare verdicts")
    s.add_argument("file")
    s.add_argument("--verbose", action="store_true", help="Print full reports for failures")
    s.set_defaults(func=cmd_bench)

    s = sub.add_parser("clues", help="List supported clue types")
    s.set_defaults(func=cmd_clues, uses_db=False)
    return p


def _run(args) -> None:
    try:
        if getattr(args, "uses_db", True):
            with HorseStore(args.db) as store:
                args.func(store, args)
        else:
            args.func(None, args)
    except ValueError as e:
        raise SystemExit(f"Error: {e}")


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    try:
        try:
            _run(args)
        finally:
            sys.stdout.flush()
    except BrokenPipeError:
        # The reader closed the pipe early, as `| head` does. Point stdout at
        # devnull so the flush at interpreter exit cannot raise a second time.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(1)


if __name__ == "__main__":
    main()
