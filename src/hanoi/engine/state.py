"""``GameState`` (frozen) and ``Status``.

A ``GameState`` is fully immutable: ``poles``/``hands`` are read-only
``MappingProxyType`` and each per-pole stack is a tuple. ``step()`` returns a
new state that may share unchanged stack tuples by reference.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, auto
from types import MappingProxyType

from .config import GameConfig, PlayerId, PoleId


class Status(Enum):
    IN_PROGRESS = auto()
    WON = auto()
    DRAW = auto()  # max_turns reached without a winner.


@dataclass(frozen=True, slots=True)
class GameState:
    """Snapshot of the game at a single point in time.

    Attributes:
        config:        Static game definition (shared across all states of a game).
        poles:         pole_id -> tuple of disk sizes, bottom-to-top.
        hands:         player_id -> held disk size, or ``None`` if empty-handed.
        status:        Current termination status.
        winner:        Player id that won, or ``None``.
        step_count:    Number of legal actions executed (game progress).
        attempt_count: Number of ``step()`` calls (legal + illegal); bounded
                       by ``config.max_turns``.
    """

    config: GameConfig
    poles: Mapping[PoleId, tuple[int, ...]]
    hands: Mapping[PlayerId, int | None]
    status: Status
    winner: PlayerId | None
    step_count: int
    attempt_count: int


def _freeze_poles(poles: Mapping[PoleId, tuple[int, ...]]) -> Mapping[PoleId, tuple[int, ...]]:
    """Wrap a poles mapping read-only for storage on a ``GameState``."""
    return MappingProxyType(dict(poles))


def _freeze_hands(hands: Mapping[PlayerId, int | None]) -> Mapping[PlayerId, int | None]:
    return MappingProxyType(dict(hands))
