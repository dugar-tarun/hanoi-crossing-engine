"""Action sum type for the engine.

Three concrete actions form a closed sum:

  * ``Lift(pole)``  — pop the top disk off ``pole`` into the actor's hand.
  * ``Place(pole)`` — push the held disk onto ``pole`` (Hanoi-legal placement).
  * ``SKIP``        — singleton; consume a turn without changing pole/hand state.

``SKIP`` is exposed as a single sentinel of the private ``_Skip`` class so
callers compare with ``is`` (or ``==``) rather than constructing fresh skips.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Union

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

Action = Union[Lift, Place, _Skip]
