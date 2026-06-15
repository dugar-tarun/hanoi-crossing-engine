"""Action sum type for the engine: ``Lift(pole)``, ``Place(pole)``, and the
``SKIP`` singleton (a sentinel of the private ``_Skip`` class).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

PoleId = str  # mirrors config.PoleId; kept here to avoid an import cycle.


@dataclass(frozen=True, slots=True)
class Lift:
    pole: PoleId


@dataclass(frozen=True, slots=True)
class Place:
    pole: PoleId


@dataclass(frozen=True, slots=True)
class _Skip:
    """Private sentinel class; use the ``SKIP`` singleton."""


SKIP: Final[_Skip] = _Skip()

Action = Lift | Place | _Skip
