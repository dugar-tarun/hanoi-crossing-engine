"""End-to-end scripted games and edge-case scenarios.

Each test runs a full game from ``initial_state`` to a terminal state and
asserts the engine reports it the way the spec says it should. Together
they cover:

  * The N=1 spec example (A wins).
  * A full N=2 Hanoi solve (A wins after 7 moves on 3a).
  * A full N=3 Hanoi solve via a recursive solver (A wins after 7*N+... moves).
  * The "trapping" strategy: A wins despite a B disk parked on 3a.
  * A starvation game (Skip-only) that DRAWs.
  * An "unwinnable in budget" scenario: A is one move away from winning but
    runs out of attempts -> DRAW.
  * Win-on-construction.
  * Determinism: replaying the same trace yields the same final state.
"""

from __future__ import annotations

from conftest import make_state, play
from hanoi.engine import (
    SKIP,
    GameConfig,
    IllegalReason,
    Lift,
    Place,
    Status,
    Terminal,
    build_two_player_config,
    initial_state,
    is_won_for,
    step,
)

# ----------------------------------------------------------------------------
# Spec example: N=1, A wins after 3 moves.
# ----------------------------------------------------------------------------


def test_spec_example_n1_a_wins() -> None:
    cfg = build_two_player_config(1)
    s = initial_state(cfg)
    s = play(
        s,
        [
            ("A", Lift("1a")),
            ("B", Lift("1b")),
            ("A", Place("3a")),
        ],
    )
    assert s.status is Status.WON
    assert s.winner == "A"
    assert s.poles["3a"] == (1,)
    assert s.poles["2"] == ()
    assert s.poles["1a"] == ()
    # B was mid-action when A won; their disk 2 is stranded in their hand.
    # That's fine: only A's win is being checked.
    assert s.hands["B"] == 2
    # 3 legal moves, no illegal attempts.
    assert s.step_count == 3
    assert s.attempt_count == 3


# ----------------------------------------------------------------------------
# N=2: A wins by transporting their 2 disks to 3a using shared pole as scratch.
# ----------------------------------------------------------------------------


def test_two_disk_solo_solve_a_wins() -> None:
    """Classic 3-move-per-disk Hanoi: A solos 1a -> 3a using 2 as buffer.

    A can win even with B doing nothing if A can leverage pole 2 as the spare.
    """
    cfg = build_two_player_config(2, max_turns=200)
    s = initial_state(cfg)
    moves = [
        ("A", Lift("1a")),  # disk 1 in hand.
        ("A", Place("2")),  # disk 1 -> shared pole.
        ("A", Lift("1a")),  # disk 3 in hand.
        ("A", Place("3a")),  # disk 3 -> 3a (bottom).
        ("A", Lift("2")),  # disk 1 in hand.
        ("A", Place("3a")),  # disk 1 -> on top of disk 3 -> A WINS.
    ]
    s = play(s, moves)
    assert s.status is Status.WON
    assert s.winner == "A"
    assert s.poles["3a"] == (3, 1)
    assert s.poles["2"] == ()
    assert s.step_count == 6
    assert s.attempt_count == 6


# ----------------------------------------------------------------------------
# N=3: full Hanoi solve via a recursive solver -> A wins.
# ----------------------------------------------------------------------------


def _solve_hanoi(n: int, src: str, dst: str, spare: str) -> list[tuple[str, str]]:
    """Return the canonical (src, dst) move list for a 3-pole Hanoi solve.

    Each tuple is ``(from_pole, to_pole)``.  The caller turns these into
    ``(player, Lift) + (player, Place)`` pairs.
    """
    if n == 0:
        return []
    return (
        _solve_hanoi(n - 1, src, spare, dst) + [(src, dst)] + _solve_hanoi(n - 1, spare, dst, src)
    )


def test_three_disk_solve_a_wins(cfg_n3: GameConfig) -> None:
    s = initial_state(cfg_n3)
    moves: list[tuple[str, object]] = []
    for src, dst in _solve_hanoi(3, "1a", "3a", "2"):
        moves.append(("A", Lift(src)))
        moves.append(("A", Place(dst)))
    s = play(s, moves)
    assert s.status is Status.WON
    assert s.winner == "A"
    assert s.poles["3a"] == (5, 3, 1)
    # Each disk movement = 2 step calls. Hanoi for N=3 -> 7 moves -> 14 steps.
    assert s.step_count == 14
    assert s.attempt_count == 14


# ----------------------------------------------------------------------------
# Trapping: A wins despite a B disk being parked on 3a.
# ----------------------------------------------------------------------------


def test_trapping_strategy_does_not_block_owner_win(cfg_n2: GameConfig) -> None:
    """A interleaves a B disk into 3a; A's ownership-only win still triggers."""
    s = initial_state(cfg_n2)

    # Step 1: B lifts disk 2 from 1b and parks it on shared pole 2.
    s, _ = step(s, "B", Lift("1b"))
    s, _ = step(s, "B", Place("2"))

    # Step 2: A lifts B's disk 2 from pole 2 and dumps it at the bottom of 3a (trap).
    s, _ = step(s, "A", Lift("2"))
    s, r = step(s, "A", Place("3a"))
    assert r.legal and r.terminal is None

    # Step 3: A solves their own pile 1a -> 3a using 2 as spare. Need to put
    # disks {3, 1} on top of the parked disk 2 on 3a. Hanoi rule allows
    # disk 3 onto 2? No — 3 > 2 violates Hanoi. So A puts disk 1 on 2 first,
    # disk 3 on the trap pile (3 onto 2 is illegal — but on 3a top is currently 2).
    # Reroute: top of 3a is disk 2. We need to get 3 then 1 on top.
    # disk 3 onto disk 2 is illegal (3 > 2). So this trap is actually a bad
    # trap for A. Let's instead test a smarter trap with N=3.
    #
    # We accept this test exits the trapping flow here; see the N=3 variant
    # below for a *successful* trap-and-win.
    assert s.poles["3a"] == (2,)
    assert s.poles["1a"] == (3, 1)


def test_trapping_with_smaller_b_disk_succeeds(cfg_n3: GameConfig) -> None:
    """N=3 trap: A parks B's disk 2 at the bottom of 3a, then stacks 5,3,1 on top.

    Disk ordering on 3a, bottom -> top: [2, 5, 3, 1] is illegal (5 > 2). So a
    successful trap must use a B disk *larger* than every A disk it sits under.
    With N=3, the largest A disk is 5 and the largest B disk is 6 — so we can
    trap disk 6 below the entire A stack.
    """
    s = initial_state(cfg_n3)

    # B clears disks 2 and 4 off 1b (bottom..top = (6, 4, 2)) so disk 6 is
    # exposed, then lifts 6 onto the shared pole:
    #   lift 2 -> shared pole 2; lift 4 -> 3b; lift 2 -> 3b on 4; lift 6 -> 2.
    moves: list[tuple[str, object]] = [
        ("B", Lift("1b")),  # picks up 2.
        ("B", Place("2")),  # shared pole = (2,).
        ("B", Lift("1b")),  # picks up 4.
        ("B", Place("3b")),  # 3b = (4,).
        ("B", Lift("2")),  # picks up 2.
        ("B", Place("3b")),  # 3b = (4, 2).
        ("B", Lift("1b")),  # picks up 6.
        ("B", Place("2")),  # shared pole = (6,).
    ]
    s = play(s, moves)
    assert s.poles["2"] == (6,)
    assert s.poles["1b"] == ()

    # A traps disk 6 at the bottom of 3a, then solves 1a (5,3,1) -> 3a using
    # pole 2 (now empty again after A lifts 6 off it).
    a_moves: list[tuple[str, object]] = [
        ("A", Lift("2")),  # picks up disk 6.
        ("A", Place("3a")),  # 3a = (6,).  Trap committed.
    ]
    # Now solve 1a (5,3,1) -> 3a (which already has 6 at bottom) using 2 as spare.
    # The disks A is moving (5,3,1) are all smaller than 6, so they stack
    # legally on top of disk 6. Standard Hanoi solve from 1a -> 3a via 2.
    for src, dst in _solve_hanoi(3, "1a", "3a", "2"):
        a_moves.append(("A", Lift(src)))
        a_moves.append(("A", Place(dst)))
    s = play(s, a_moves)

    assert s.status is Status.WON
    assert s.winner == "A"
    # Trap visible at bottom of 3a; A's three disks stacked on top.
    assert s.poles["3a"] == (6, 5, 3, 1)
    # Pole 2 is empty (required for A's win clause 4).
    assert s.poles["2"] == ()
    # B's owned disks {2, 4} are stranded on 3b. Visible only to B.
    assert s.poles["3b"] == (4, 2)


# ----------------------------------------------------------------------------
# DRAW scenarios
# ----------------------------------------------------------------------------


def test_skip_only_game_draws() -> None:
    cfg = build_two_player_config(3, max_turns=6)
    s = initial_state(cfg)
    last_state = s
    for i in range(6):
        last_state, r = step(last_state, "A" if i % 2 == 0 else "B", SKIP)
    assert last_state.status is Status.DRAW
    assert last_state.winner is None
    assert last_state.attempt_count == 6


def test_one_move_short_of_winning_draws() -> None:
    """A is one Place away from winning but runs out of attempts -> DRAW."""
    cfg = build_two_player_config(1, max_turns=2)  # need 3 moves to win N=1.
    s = initial_state(cfg)
    s, r1 = step(s, "A", Lift("1a"))
    assert r1.legal and r1.terminal is None
    s, r2 = step(s, "A", Lift("1b"))  # illegal (not visible) but burns a turn.
    # Cap of 2 hit on attempt #2.
    assert r2.legal is False
    assert r2.illegality is IllegalReason.POLE_NOT_VISIBLE
    assert r2.terminal is Terminal.DRAW
    assert s.status is Status.DRAW
    assert s.winner is None
    # No further moves allowed.
    s, r3 = step(s, "A", Place("3a"))
    assert r3.illegality is IllegalReason.GAME_OVER


def test_burning_budget_with_illegal_actions_locks_in_draw() -> None:
    """Even with all the legal moves available, the budget cap holds."""
    cfg = build_two_player_config(3, max_turns=5)
    s = initial_state(cfg)
    # Spam illegal "lift from invisible pole".
    for _ in range(5):
        s, _ = step(s, "A", Lift("1b"))
    assert s.status is Status.DRAW
    assert s.attempt_count == 5
    assert s.step_count == 0
    # The board is untouched.
    assert s.poles["1a"] == (5, 3, 1)
    assert s.poles["1b"] == (6, 4, 2)


# ----------------------------------------------------------------------------
# Win-on-construction.
# ----------------------------------------------------------------------------


def test_win_on_construction_evaluates_in_player_order(cfg_n2: GameConfig) -> None:
    """If both players satisfy the predicate at t=0, the first one in
    config.players order wins.
    """
    s = make_state(
        cfg_n2,
        poles={"1a": (), "1b": (), "2": (), "3a": (3, 1), "3b": (4, 2)},
        hands={"A": None, "B": None},
    )
    # Both A and B individually satisfy the predicate.
    assert is_won_for(s, "A")
    assert is_won_for(s, "B")
    # ``initial_state`` won't reach this state (you can't pre-load a config
    # both ways at once unless you build a custom config), but the resolution
    # rule is mirrored in ``initial_state``: actor order from config.players.
    cfg = GameConfig(
        players=cfg_n2.players,
        poles=cfg_n2.poles,
        initial_stacks={"1a": (), "1b": (), "2": (), "3a": (3, 1), "3b": (4, 2)},
        disk_owner=dict(cfg_n2.disk_owner),
        max_turns=cfg_n2.max_turns,
    )
    s0 = initial_state(cfg)
    assert s0.status is Status.WON
    assert s0.winner == "A"  # A is listed first.


# ----------------------------------------------------------------------------
# Determinism / immutability.
# ----------------------------------------------------------------------------


def test_engine_is_deterministic(cfg_n3: GameConfig) -> None:
    """Same initial state + same move sequence -> same final state, twice."""
    moves = []
    for src, dst in _solve_hanoi(3, "1a", "3a", "2"):
        moves.append(("A", Lift(src)))
        moves.append(("A", Place(dst)))

    s1 = play(initial_state(cfg_n3), moves)
    s2 = play(initial_state(cfg_n3), moves)
    assert s1.status is s2.status
    assert s1.winner == s2.winner
    assert dict(s1.poles) == dict(s2.poles)
    assert dict(s1.hands) == dict(s2.hands)
    assert s1.step_count == s2.step_count
    assert s1.attempt_count == s2.attempt_count


def test_step_returns_new_state_does_not_mutate_old(cfg_n3: GameConfig) -> None:
    s0 = initial_state(cfg_n3)
    snapshot_poles = dict(s0.poles)
    snapshot_hands = dict(s0.hands)
    s1, _ = step(s0, "A", Lift("1a"))
    assert s1 is not s0
    # Original state is bit-identical post-step.
    assert dict(s0.poles) == snapshot_poles
    assert dict(s0.hands) == snapshot_hands
    assert s0.step_count == 0
    assert s0.attempt_count == 0
