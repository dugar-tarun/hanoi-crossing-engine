"""Shared test helpers: fixtures, manual state builders, action shorthands."""

from __future__ import annotations

from typing import Iterable, Mapping

import pytest

from hanoi.engine import (
    GameConfig,
    GameState,
    Lift,
    Place,
    PoleSpec,
    SKIP,
    Status,
    build_two_player_config,
    initial_state,
    step,
)
from hanoi.engine.state import _freeze_hands, _freeze_poles


@pytest.fixture
def cfg_n1() -> GameConfig:
    return build_two_player_config(1)


@pytest.fixture
def cfg_n2() -> GameConfig:
    return build_two_player_config(2)


@pytest.fixture
def cfg_n3() -> GameConfig:
    return build_two_player_config(3)


@pytest.fixture
def s0_n1(cfg_n1: GameConfig) -> GameState:
    return initial_state(cfg_n1)


@pytest.fixture
def s0_n2(cfg_n2: GameConfig) -> GameState:
    return initial_state(cfg_n2)


@pytest.fixture
def s0_n3(cfg_n3: GameConfig) -> GameState:
    return initial_state(cfg_n3)


def make_state(
    config: GameConfig,
    *,
    poles: Mapping[str, tuple[int, ...]],
    hands: Mapping[str, int | None],
    status: Status = Status.IN_PROGRESS,
    winner: str | None = None,
    step_count: int = 0,
    attempt_count: int = 0,
) -> GameState:
    """Build a ``GameState`` directly without going through ``step()``.

    Useful for testing predicates and edge cases (e.g., win-condition states
    that never arise via legal play).
    """
    full_poles = {spec.id: poles.get(spec.id, ()) for spec in config.poles}
    full_hands = {p: hands.get(p) for p in config.players}
    return GameState(
        config=config,
        poles=_freeze_poles(full_poles),
        hands=_freeze_hands(full_hands),
        status=status,
        winner=winner,
        step_count=step_count,
        attempt_count=attempt_count,
    )


def play(state: GameState, moves: Iterable[tuple[str, object]]) -> GameState:
    """Run a sequence of ``(player, action)`` pairs through ``step``.

    Asserts every step is legal; raises ``AssertionError`` on the first
    illegal step, surfacing the offending index for fast debugging.
    """
    s = state
    for i, (player, action) in enumerate(moves):
        s, r = step(s, player, action)
        assert r.legal, f"move #{i} illegal: player={player} action={action} reason={r.illegality}"
    return s
