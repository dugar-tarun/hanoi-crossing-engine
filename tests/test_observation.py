"""Tests for ``project()`` and the ``Observation`` view."""

from __future__ import annotations

from hanoi.engine import (
    SKIP,
    GameState,
    Lift,
    Place,
    Status,
    legal_actions,
    project,
    step,
)


def test_observation_hides_opponent_poles(s0_n3: GameState) -> None:
    obs_a = project(s0_n3, "A")
    obs_b = project(s0_n3, "B")
    assert set(obs_a.visible_poles.keys()) == {"1a", "2", "3a"}
    assert set(obs_b.visible_poles.keys()) == {"1b", "2", "3b"}


def test_observation_hides_opponent_hand(s0_n3: GameState) -> None:
    s, _ = step(s0_n3, "B", Lift("1b"))  # B picks up disk 2.
    obs_a = project(s, "A")
    obs_b = project(s, "B")
    # A's view: own_hand is None (A is empty-handed). B's hand is not exposed.
    assert obs_a.own_hand is None
    assert obs_b.own_hand == 2
    # The Observation dataclass simply doesn't have a field for the opponent's hand.
    assert not hasattr(obs_a, "opponent_hand")


def test_observation_reflects_own_hand(s0_n3: GameState) -> None:
    s, _ = step(s0_n3, "A", Lift("1a"))
    obs = project(s, "A")
    assert obs.own_hand == 1


def test_observation_legal_actions_match_engine(s0_n3: GameState) -> None:
    s, _ = step(s0_n3, "A", Lift("1a"))
    obs = project(s, "A")
    assert obs.legal_actions == legal_actions(s, "A")
    # Holding -> only Place actions + SKIP, no Lifts.
    assert SKIP in obs.legal_actions
    assert all(not isinstance(a, Lift) for a in obs.legal_actions)


def test_observation_legal_actions_empty_at_terminal(s0_n1: GameState) -> None:
    s, _ = step(s0_n1, "A", Lift("1a"))
    s, _ = step(s, "A", Place("3a"))  # A wins.
    obs = project(s, "A")
    assert obs.status is Status.WON
    assert obs.winner == "A"
    assert obs.legal_actions == ()


def test_observation_counters_mirror_state(s0_n3: GameState) -> None:
    s, _ = step(s0_n3, "A", Lift("1b"))  # illegal, bumps attempt only.
    s, _ = step(s, "A", Lift("1a"))  # legal.
    obs = project(s, "A")
    assert obs.step_count == 1
    assert obs.attempt_count == 2


def test_observation_unknown_player_returns_empty_view(s0_n1: GameState) -> None:
    obs = project(s0_n1, "Z")
    assert obs.me == "Z"
    assert obs.visible_poles == {}  # No poles list "Z" in visible_to.
    assert obs.own_hand is None
    assert obs.legal_actions == ()
