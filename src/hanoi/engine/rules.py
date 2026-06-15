"""Pure rule predicates: ownership lookups, Hanoi placement, win check.

Everything in this module is a pure function of ``GameState`` (or
``GameConfig``) — no I/O, no mutation, no random state. The functions are
re-used by both ``engine.step`` (to evaluate legality and detect wins) and by
tests (to assert predicates directly).
"""

from __future__ import annotations

from .config import GameConfig, PlayerId, PoleId
from .state import GameState


def goal_pole_of(config: GameConfig, player: PlayerId) -> PoleId:
    """Unique pole id that ``player`` must stack their owned disks on to win."""
    return config.goal_pole_of(player)


def disks_owned_by(config: GameConfig, player: PlayerId) -> frozenset[int]:
    """All disk sizes (= disk identities) that belong to ``player``."""
    return frozenset(d for d, owner in config.disk_owner.items() if owner == player)


def hanoi_placement_legal(stack: tuple[int, ...], disk: int) -> bool:
    """Standard Hanoi rule: place onto an empty stack or onto a strictly larger disk."""
    return not stack or stack[-1] > disk


def is_won_for(state: GameState, player: PlayerId) -> bool:
    """Ownership-only win predicate, evaluated against full state.

    ``player`` wins iff:

    1. ``state.hands[player] is None`` (their hand is empty).
    2. Every disk owned by ``player`` sits on ``player``'s designated goal pole.
    3. No disk owned by ``player`` exists anywhere else (other poles, or any hand).
    4. Every pole visible to ``player`` other than their goal pole is *completely*
       empty — including disks owned by other players. In the 2-player layout
       this reduces to: the shared pole must be empty.

    The check is total over the state — illegal-looking states (e.g. an empty
    pole that should be empty) do not raise; the predicate just returns the
    answer.
    """
    if state.hands[player] is not None:
        return False

    owned = disks_owned_by(state.config, player)
    goal = goal_pole_of(state.config, player)

    on_goal = {d for d in state.poles[goal] if state.config.disk_owner[d] == player}
    if on_goal != owned:
        return False

    for pid, stack in state.poles.items():
        if pid == goal:
            continue
        if any(state.config.disk_owner[d] == player for d in stack):
            return False

    for held in state.hands.values():
        if held is not None and state.config.disk_owner[held] == player:
            return False

    for spec in state.config.poles:
        if spec.id == goal:
            continue
        if player in spec.visible_to and state.poles[spec.id]:
            return False

    return True
