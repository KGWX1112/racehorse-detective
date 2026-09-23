"""
Partial dates and racing ages.

Race dates are ISO 8601 and may be partial: "1875", "1875-06", "1875-06-12".

A racing age counts official birthdays. Each country in RACING_BIRTHDAYS gives
every horse foaled there the same birthday, and the horse is treated as born on
that day of its foaling year. A country not in the table gives an unknown age.
"""

import calendar
import re
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

# Month and day of the official birthday, from the owner's answer to question 3
# in docs/v0.2-plan.md. Add a country only when the owner confirms its date.
RACING_BIRTHDAYS: Dict[str, Tuple[int, int]] = {
    "GB": (1, 1), "IRE": (1, 1), "FR": (1, 1), "USA": (1, 1), "CAN": (1, 1),
    "JPN": (1, 1), "GER": (1, 1), "HUN": (1, 1),
    "AUS": (8, 1), "NZ": (8, 1),
}

_DATE_RE = re.compile(r"(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?")


def date_bounds(text: str) -> Tuple[date, date]:
    """First and last day a partial ISO 8601 date can mean. "1875" covers the whole year."""
    m = _DATE_RE.fullmatch(str(text))
    if not m:
        raise ValueError(f"date '{text}' is not YYYY, YYYY-MM, or YYYY-MM-DD")
    year, month, day = (int(g) if g else None for g in m.groups())
    try:
        if month is None:
            return date(year, 1, 1), date(year, 12, 31)
        if day is None:
            return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
        return date(year, month, day), date(year, month, day)
    except ValueError:
        raise ValueError(f"date '{text}' is not a calendar date") from None


def birthday_text(country: str) -> Optional[str]:
    """The official birthday for a country, e.g. "1 January", or None if it is not in the table."""
    birthday = RACING_BIRTHDAYS.get(country)
    return f"{birthday[1]} {calendar.month_name[birthday[0]]}" if birthday else None


def age_under(foaled: int, country: Optional[str], when: str) -> Optional[int]:
    """
    Racing age on the date `when` under `country`'s official birthday. None if
    the country is not in the table, if a partial date spans the birthday so
    the age could be either of two values, or if the date is before the
    horse's first official birthday.
    """
    birthday = RACING_BIRTHDAYS.get(country) if country else None
    if birthday is None:
        return None
    # Age never decreases with the date, so the first and last day settle the whole range.
    ages = {d.year - foaled - ((d.month, d.day) < birthday) for d in date_bounds(when)}
    if len(ages) != 1:
        return None
    age = ages.pop()
    return age if age >= 0 else None


@dataclass(frozen=True)
class RacingAge:
    """Age on race day under the foaling country's birthday and under the race country's birthday."""
    by_foaling_country: Optional[int]
    by_race_country: Optional[int]

    @property
    def known(self) -> List[int]:
        """The distinct ages that could be known, smallest first."""
        return sorted({a for a in (self.by_foaling_country, self.by_race_country) if a is not None})

    def __str__(self) -> str:
        """The foaling-country age, then the race-country age after a slash when it differs or fills a gap."""
        f, r = self.by_foaling_country, self.by_race_country
        if f is not None and (r is None or r == f):
            return str(f)
        if f is None and r is None:
            return "?"
        return f"{'?' if f is None else f}/{'?' if r is None else r}"
