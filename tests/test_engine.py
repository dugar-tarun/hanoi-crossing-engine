"""Tests for ``initial_state``, ``step``, ``legal_actions``, ``is_terminal``.

Covers counter discipline, every ``IllegalReason``, the DRAW transition,
and structural invariants on returned tuples.
"""

from __future__ import annotations

import pytest

from hanoi.engine import (
    ConfigError,
    GameConfig,
    GameState,
    IllegalReason,
    Lift,
    Place,
    PoleSpec,
    SKIP,
    Status,
    StepResult,
    Terminal,
    build_two_player_config,
    initial_state,
    is_terminal,
    legal_actions,
    step,
)

from conftest import make_state


# ----------------------------------------------------------------------------
# Construction
# ----------------------------------------------------------------------------

def test_initial_state_zero_counters(s0_n3: GameState) -> None:
    assert s0_n3.step_count == 0
    assert s0_n3.attempt_count == 0
    assert s0_n3.status is Status.IN_PROGRESS
    assert s0_n3.winner is None


def test_initial_state_layout_n3(s0_n3: GameState) -> None:
    assert s0_n3.poles["1a"] == (5, 3, 1)
    assert s0_n3.poles["1b"] == (6, 4, 2)
    assert s0_n3.poles["2"] == ()
    assert s0_n3.poles["3a"] == ()
    assert s0_n3.poles["3b"] == ()
    assert all(s0_n3.hands[p] is None for p in s0_n3.config.players)


def test_initial_state_immutable(s0_n1: GameState) -> None:
    """Frozen dataclass + MappingProxyType -> mutation attempts must fail."""
    with pytest.raises(Exception):
        s0_n1.poles["1a"] = (99,)            # type: ignore[index]
    with pytest.raises(Exception):
        s0_n1.hands["A"] = 7                 # type: ignore[index]
    with pytest.raises(Exception):
        s0_n1.step_count = 99                # type: ignore[misc]


def test_initial_state_detects_win_on_construction() -> None:
    """If config places everything in the winning shape, init goes straight to WON."""
    cfg = build_two_player_config(2)
    # Construct an alternative config where A's disks already sit on 3a and
    # B's are on 1b (so A is won at t=0).
    alt_cfg = GameConfig(
        players=cfg.players,
        poles=cfg.poles,
        initial_stacks={"1a": (), "1b": (4, 2), "2": (), "3a": (3, 1), "3b": ()},
        disk_owner=dict(cfg.disk_owner),
        max_turns=cfg.max_turns,
    )
    s = initial_state(alt_cfg)
    assert s.status is Status.WON
    assert s.winner == "A"
    # Stepping in a terminal state is rejected.
    s2, r = step(s, "A", SKIP)
    assert r.legal is False
    assert r.illegality is IllegalReason.GAME_OVER


# ----------------------------------------------------------------------------
# legal_actions structure
# ----------------------------------------------------------------------------

def test_legal_actions_terminal_is_empty(s0_n1: GameState) -> None:
    s, _ = step(s0_n1, "A", Lift("1a"))
    s, _ = step(s, "A", Place("3a"))    # A wins (B never got a chance).
    assert is_terminal(s)
    assert legal_actions(s, "A") == ()
    assert legal_actions(s, "B") == ()


def test_legal_actions_non_terminal_contains_skip(s0_n3: GameState) -> None:
    la = legal_actions(s0_n3, "A")
    assert SKIP in la
    assert len(la) >= 1


def test_legal_actions_unknown_player_returns_empty(s0_n1: GameState) -> None:
    assert legal_actions(s0_n1, "Z") == ()


def test_legal_actions_lift_only_when_hand_empty(s0_n3: GameState) -> None:
    la = legal_actions(s0_n3, "A")
    assert all(not isinstance(a, Place) for a in la)
    # A sees 1a (top=1), 2 (empty), 3a (empty); only 1a yields a Lift.
    lifts = tuple(a for a in la if isinstance(a, Lift))
    assert lifts == (Lift("1a"),)


def test_legal_actions_place_only_when_holding(s0_n1: GameState) -> None:
    s, _ = step(s0_n1, "A", Lift("1a"))
    la = legal_actions(s, "A")
    # Holding disk 1 -> can place on any visible pole (all three are valid since
    # 1a/2/3a are all empty after the lift).
    assert all(not isinstance(a, Lift) for a in la)
    placements = sorted(a.pole for a in la if isinstance(a, Place))
    assert placements == ["1a", "2", "3a"]


def test_legal_actions_deterministic_order(s0_n3: GameState) -> None:
    """Same state queried twice -> identical tuple, sorted by pole id."""
    a1 = legal_actions(s0_n3, "A")
    a2 = legal_actions(s0_n3, "A")
    assert a1 == a2
    pole_keys = [a.pole for a in a1 if isinstance(a, (Lift, Place))]
    assert pole_keys == sorted(pole_keys)


# ----------------------------------------------------------------------------
# Step: legal moves and counter discipline
# ----------------------------------------------------------------------------

def test_legal_lift_increments_both_counters(s0_n3: GameState) -> None:
    s, r = step(s0_n3, "A", Lift("1a"))
    assert r.legal and r.illegality is None
    assert s.step_count == 1
    assert s.attempt_count == 1
    assert s.poles["1a"] == (5, 3)
    assert s.hands["A"] == 1


def test_legal_skip_increments_both_counters_and_keeps_state(s0_n1: GameState) -> None:
    s, r = step(s0_n1, "A", SKIP)
    assert r.legal
    assert s.step_count == 1
    assert s.attempt_count == 1
    # Skip never produces a WON terminal.
    assert s.status is Status.IN_PROGRESS
    assert s.winner is None
    assert s.poles == s0_n1.poles
    assert s.hands == s0_n1.hands


def test_legal_place_drops_disk_and_clears_hand(s0_n2: GameState) -> None:
    s, _ = step(s0_n2, "A", Lift("1a"))         # A picks up disk 1.
    s, r = step(s, "A", Place("2"))             # places on shared pole.
    assert r.legal
    assert s.poles["2"] == (1,)
    assert s.hands["A"] is None


# ----------------------------------------------------------------------------
# Step: every illegal reason
# ----------------------------------------------------------------------------

def test_illegal_pole_not_visible(s0_n3: GameState) -> None:
    """A cannot lift from B's private pole 1b."""
    s, r = step(s0_n3, "A", Lift("1b"))
    assert r == StepResult(
        legal=False,
        illegality=IllegalReason.POLE_NOT_VISIBLE,
        terminal=None,
        winner=None,
    )
    # State unchanged on the game-state fields, attempt_count bumped.
    assert s.step_count == 0
    assert s.attempt_count == 1
    assert s.poles == s0_n3.poles
    assert s.hands == s0_n3.hands


def test_illegal_unknown_pole_id_treated_as_not_visible(s0_n1: GameState) -> None:
    s, r = step(s0_n1, "A", Lift("does_not_exist"))
    assert r.illegality is IllegalReason.POLE_NOT_VISIBLE
    assert s.attempt_count == 1
    assert s.step_count == 0


def test_illegal_hand_occupied(s0_n3: GameState) -> None:
    s, _ = step(s0_n3, "A", Lift("1a"))         # A picks up disk 1.
    s, r = step(s, "A", Lift("1a"))             # tries to lift again.
    assert r.illegality is IllegalReason.HAND_OCCUPIED
    assert s.step_count == 1
    assert s.attempt_count == 2
    assert s.hands["A"] == 1


def test_illegal_hand_empty_on_place(s0_n3: GameState) -> None:
    s, r = step(s0_n3, "A", Place("3a"))
    assert r.illegality is IllegalReason.HAND_EMPTY
    assert s.attempt_count == 1
    assert s.step_count == 0


def test_illegal_pole_empty_on_lift(s0_n3: GameState) -> None:
    s, r = step(s0_n3, "A", Lift("3a"))         # 3a is empty initially.
    assert r.illegality is IllegalReason.POLE_EMPTY
    assert s.attempt_count == 1
    assert s.step_count == 0


def test_illegal_placement_rule(s0_n3: GameState) -> None:
    """Placing a larger disk onto a smaller one violates Hanoi."""
    s, _ = step(s0_n3, "A", Lift("1a"))         # disk 1 in hand.
    s, _ = step(s, "A", Place("3a"))            # 3a = (1,)
    s, _ = step(s, "A", Lift("1a"))             # disk 3 in hand.
    s, r = step(s, "A", Place("3a"))            # 3 onto 1 -> illegal.
    assert r.illegality is IllegalReason.PLACEMENT_RULE
    # All prior legal actions counted; this one bumped only attempt_count.
    assert s.step_count == 3
    assert s.attempt_count == 4
    assert s.hands["A"] == 3
    assert s.poles["3a"] == (1,)


def test_illegal_unknown_player(s0_n1: GameState) -> None:
    s, r = step(s0_n1, "Z", SKIP)
    assert r.illegality is IllegalReason.UNKNOWN_PLAYER
    assert s.attempt_count == 1
    assert s.step_count == 0


def test_illegal_game_over_does_not_bump_counters() -> None:
    """Once status is terminal, further step() calls are no-ops on counters."""
    cfg = build_two_player_config(1)
    s = initial_state(cfg)
    s, _ = step(s, "A", Lift("1a"))
    s, r = step(s, "A", Place("3a"))
    assert r.terminal is Terminal.WON
    pre_attempt = s.attempt_count
    pre_step = s.step_count

    s2, r2 = step(s, "A", SKIP)
    assert r2.illegality is IllegalReason.GAME_OVER
    assert s2.attempt_count == pre_attempt
    assert s2.step_count == pre_step
    # The state is identical (same tuple references would be ideal; equality is
    # what we promise).
    assert s2.status is Status.WON


# ----------------------------------------------------------------------------
# DRAW transition
# ----------------------------------------------------------------------------

def test_skip_only_run_terminates_in_draw() -> None:
    """All skips, exhaust max_turns -> DRAW (no winner)."""
    cfg = build_two_player_config(3, max_turns=10)
    s = initial_state(cfg)
    last_result: StepResult | None = None
    for i in range(10):
        s, last_result = step(s, "A" if i % 2 == 0 else "B", SKIP)
    assert last_result is not None
    assert last_result.legal is True
    assert last_result.terminal is Terminal.DRAW
    assert s.status is Status.DRAW
    assert s.winner is None
    assert s.step_count == 10
    assert s.attempt_count == 10


def test_illegal_actions_can_drive_draw() -> None:
    """attempt_count is what the cap pins on; illegal actions still consume budget."""
    cfg = build_two_player_config(3, max_turns=3)
    s = initial_state(cfg)
    # Three illegal lifts in a row -> DRAW on the third call.
    s, r1 = step(s, "A", Lift("1b"))   # illegal: not visible.
    assert r1.illegality is IllegalReason.POLE_NOT_VISIBLE
    s, r2 = step(s, "A", Lift("1b"))
    assert r2.illegality is IllegalReason.POLE_NOT_VISIBLE
    s, r3 = step(s, "A", Lift("1b"))
    # On the third illegal attempt we hit max_turns -> StepResult reports BOTH.
    assert r3.legal is False
    assert r3.illegality is IllegalReason.POLE_NOT_VISIBLE
    assert r3.terminal is Terminal.DRAW
    assert s.status is Status.DRAW
    assert s.step_count == 0
    assert s.attempt_count == 3


def test_legal_action_on_max_turns_boundary_reports_both_legal_and_draw() -> None:
    cfg = build_two_player_config(3, max_turns=1)
    s = initial_state(cfg)
    s, r = step(s, "A", Lift("1a"))
    # The single allowed turn was legal; also exactly hit the cap.
    assert r.legal is True
    assert r.terminal is Terminal.DRAW
    assert s.status is Status.DRAW
    assert s.step_count == 1
    assert s.attempt_count == 1


def test_winning_step_at_cap_prefers_won_over_draw() -> None:
    """A win on the same call that hits the cap should report Terminal.WON."""
    cfg = build_two_player_config(1, max_turns=2)
    s = initial_state(cfg)
    s, r1 = step(s, "A", Lift("1a"))
    assert r1.legal and r1.terminal is None
    s, r2 = step(s, "A", Place("3a"))   # A wins on attempt #2 (== max_turns).
    assert r2.legal is True
    assert r2.terminal is Terminal.WON
    assert r2.winner == "A"
    assert s.status is Status.WON
    assert s.attempt_count == 2


# ----------------------------------------------------------------------------
# Skip never transitions to WON
# ----------------------------------------------------------------------------

def test_skip_does_not_check_win_predicate(cfg_n2: GameConfig) -> None:
    """Per TRD: only Place can transition to WON.

    Construct a state that already satisfies is_won_for(A) but with status
    IN_PROGRESS (you can't reach this by legal play, but the engine must not
    promote it on a Skip).
    """
    s = make_state(
        cfg_n2,
        poles={"1a": (), "1b": (4, 2), "2": (), "3a": (3, 1), "3b": ()},
        hands={"A": None, "B": None},
    )
    assert s.status is Status.IN_PROGRESS

    s2, r = step(s, "A", SKIP)
    assert r.legal is True
    assert r.terminal is None
    assert s2.status is Status.IN_PROGRESS
    assert s2.winner is None


def test_lift_does_not_check_win_predicate(cfg_n2: GameConfig) -> None:
    s = make_state(
        cfg_n2,
        # All A disks on 3a, but B's disk 4 sits on 1b (visible to B only),
        # disk 2 sits on shared pole 2 (blocks A from winning).
        poles={"1a": (), "1b": (4,), "2": (2,), "3a": (3, 1), "3b": ()},
        hands={"A": None, "B": None},
    )
    # A lifts the blocking disk off pole 2 -> ends up holding disk 2 (a B disk).
    s2, r = step(s, "A", Lift("2"))
    assert r.legal is True
    assert r.terminal is None        # Win not checked on Lift even if the
    assert s2.status is Status.IN_PROGRESS  # state would now satisfy the
    # predicate (which it doesn't here — A is now holding a disk).
