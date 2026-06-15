"""Per-player projection of ``GameState`` for agent consumption.

An ``Observation`` contains exactly what an agent is allowed to see: their own
visible poles, their own hand, the public counters, and the precomputed list
of legal actions. The opponent's hand and any non-visible poles are hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .actions import Action
from .config import PlayerId, PoleId
from .engine import legal_actions
from .state import GameState, Status


@dataclass(frozen=True, slots=True)
class Observation:
    me: PlayerId
    visible_poles: Mapping[PoleId, tuple[int, ...]]
    own_hand: int | None
    step_count: int
    attempt_count: int
    status: Status
    winner: PlayerId | None
    legal_actions: tuple[Action, ...]


def project(state: GameState, player: PlayerId) -> Observation:
    """Build ``player``'s observation of ``state``.

    Hidden by construction:
      * Other players' hands.
      * Disk stacks on poles where ``player`` is not in ``visible_to``.
    """
    visible = {
        spec.id: state.poles[spec.id]
        for spec in state.config.poles
        if player in spec.visible_to
    }
    own_hand = state.hands.get(player) if player in state.config.players else None

    return Observation(
        me=player,
        visible_poles=MappingProxyType(visible),
        own_hand=own_hand,
        step_count=state.step_count,
        attempt_count=state.attempt_count,
        status=state.status,
        winner=state.winner,
        legal_actions=legal_actions(state, player),
    )
