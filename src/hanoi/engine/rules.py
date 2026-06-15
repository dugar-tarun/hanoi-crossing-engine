"""Pure rule predicates: ownership lookups, Hanoi placement, win check.

Every function here is a pure function of ``GameState`` / ``GameConfig`` — no
I/O, mutation, or random state.
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
    """Win predicate for ``player``, total over any state.

    ``player`` wins iff their hand is empty, every disk they own sits on their
    goal pole (and nowhere else, including hands), and every other pole visible
    to them is completely empty.
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
