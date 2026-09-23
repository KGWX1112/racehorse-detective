"""Racehorse detective engine, v0.1."""

__version__ = "0.1.0"

from .engine import Case, Investigation, investigate
from .evaluators import EVALUATORS, Clue, Finding, Status
from .models import CareerSummary, Horse
from .store import HorseStore
