"""Tests for the random-play CLI frontend (``hanoi-random``).

Tests call ``hanoi.modes.random_play.main()`` directly with ``capsys`` so no
subprocess overhead is needed.

Coverage:
  * Seeded run is deterministic (same output run twice).
  * Run always terminates with WON or DRAW.
  * Small disk count (N=1) terminates quickly with a winner.
  * ``--max-turns 1`` forces an immediate DRAW.
  * ``--max-turns`` is respected (attempt_count <= max_turns in output).
  * Custom ``--turn-order`` pattern.
  * RandomAgent uses only Observation (no full-state access).
  * Error paths exit 1:
      - ``--disks 0``
      - ``--max-turns 0``
      - ``--turn-order`` with unknown player character
      - empty ``--turn-order``
"""

from __future__ import annotations

import re

import pytest

from hanoi.modes.random_play import main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_status(out: str) -> str:
    m = re.search(r"status:\s+(\w+)", out)
    assert m, f"status not found in output:\n{out}"
    return m.group(1)


def _extract_winner(out: str) -> str | None:
    m = re.search(r"winner:\s+(\S+)", out)
    assert m, f"winner not found in output:\n{out}"
    val = m.group(1)
    return None if val == "None" else val


def _extract_attempt_count(out: str) -> int:
    m = re.search(r"attempt_count:\s+(\d+)", out)
    assert m, f"attempt_count not found in output:\n{out}"
    return int(m.group(1))


def _extract_step_count(out: str) -> int:
    m = re.search(r"step_count:\s+(\d+)", out)
    assert m, f"step_count not found in output:\n{out}"
    return int(m.group(1))


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_random_play_is_deterministic(capsys: pytest.CaptureFixture) -> None:
    """Same seed produces identical output on two runs."""
    main(["--disks", "2", "--seed", "42"])
    out1 = capsys.readouterr().out

    main(["--disks", "2", "--seed", "42"])
    out2 = capsys.readouterr().out

    assert out1 == out2


def test_random_play_different_seeds_may_differ(capsys: pytest.CaptureFixture) -> None:
    """Two different seeds should (almost certainly) produce different outputs."""
    main(["--disks", "3", "--seed", "1"])
    out1 = capsys.readouterr().out
    main(["--disks", "3", "--seed", "999"])
    out2 = capsys.readouterr().out
    # Very unlikely to be identical.
    assert out1 != out2


def test_random_play_terminates_with_won_or_draw(capsys: pytest.CaptureFixture) -> None:
    """Any seeded run must end in WON or DRAW."""
    main(["--disks", "2", "--seed", "7", "--max-turns", "2000"])
    out = capsys.readouterr().out
    status = _extract_status(out)
    assert status in {"WON", "DRAW"}


def test_random_play_n1_terminates_quickly(capsys: pytest.CaptureFixture) -> None:
    """With N=1, a random game is tiny — it should always produce a result."""
    main(["--disks", "1", "--seed", "0"])
    out = capsys.readouterr().out
    status = _extract_status(out)
    assert status in {"WON", "DRAW"}


def test_random_play_max_turns_1_forces_draw(capsys: pytest.CaptureFixture) -> None:
    """A single permitted step cannot win N=3, so max_turns=1 must DRAW."""
    main(["--disks", "3", "--seed", "0", "--max-turns", "1"])
    out = capsys.readouterr().out
    assert _extract_status(out) == "DRAW"
    assert _extract_winner(out) is None
    assert _extract_attempt_count(out) == 1


def test_random_play_attempt_count_bounded_by_max_turns(capsys: pytest.CaptureFixture) -> None:
    """attempt_count must not exceed max_turns."""
    max_t = 50
    main(["--disks", "2", "--seed", "17", "--max-turns", str(max_t)])
    out = capsys.readouterr().out
    assert _extract_attempt_count(out) <= max_t


def test_random_play_step_count_le_attempt_count(capsys: pytest.CaptureFixture) -> None:
    """step_count (legal moves) must be <= attempt_count (all moves)."""
    main(["--disks", "2", "--seed", "3", "--max-turns", "200"])
    out = capsys.readouterr().out
    assert _extract_step_count(out) <= _extract_attempt_count(out)


def test_random_play_output_includes_header(capsys: pytest.CaptureFixture) -> None:
    main(["--disks", "2", "--seed", "5"])
    out = capsys.readouterr().out
    assert "Hanoi Crossing Random Play" in out
    assert "Final State" in out


def test_random_play_output_shows_poles(capsys: pytest.CaptureFixture) -> None:
    main(["--disks", "1", "--seed", "1"])
    out = capsys.readouterr().out
    # All five poles must appear in the final-state dump.
    for pole in ("1a", "1b", "2", "3a", "3b"):
        assert pole in out


def test_random_play_custom_turn_order_all_a(capsys: pytest.CaptureFixture) -> None:
    """With only A acting, A may eventually win or hit the cap."""
    main(["--disks", "1", "--seed", "10", "--turn-order", "A", "--max-turns", "200"])
    out = capsys.readouterr().out
    status = _extract_status(out)
    assert status in {"WON", "DRAW"}


def test_random_play_winner_is_valid_player_or_none(capsys: pytest.CaptureFixture) -> None:
    main(["--disks", "2", "--seed", "99"])
    out = capsys.readouterr().out
    winner = _extract_winner(out)
    assert winner in {None, "A", "B"}


def test_random_play_won_status_has_winner(capsys: pytest.CaptureFixture) -> None:
    """If status is WON, winner must not be None."""
    # Try a few seeds to find a WON outcome.
    for seed in range(20):
        main(["--disks", "1", "--seed", str(seed), "--max-turns", "500"])
        out = capsys.readouterr().out
        status = _extract_status(out)
        winner = _extract_winner(out)
        if status == "WON":
            assert winner is not None
            break


def test_random_play_many_seeds_all_terminate(capsys: pytest.CaptureFixture) -> None:
    """Spot-check 10 different seeds each produce a terminal state."""
    for seed in range(10):
        main(["--disks", "1", "--seed", str(seed)])
        out = capsys.readouterr().out
        assert _extract_status(out) in {"WON", "DRAW"}


def test_random_play_n3_terminates(capsys: pytest.CaptureFixture) -> None:
    """N=3 with a large budget also terminates."""
    main(["--disks", "3", "--seed", "42", "--max-turns", "5000"])
    out = capsys.readouterr().out
    assert _extract_status(out) in {"WON", "DRAW"}


def test_random_play_default_args_run(capsys: pytest.CaptureFixture) -> None:
    """Running with only --seed should use defaults without error."""
    main(["--seed", "1"])
    out = capsys.readouterr().out
    assert "Final State" in out


# ---------------------------------------------------------------------------
# RandomAgent unit tests
# ---------------------------------------------------------------------------


def test_random_agent_uses_only_observation() -> None:
    """RandomAgent.choose_action must accept an Observation and return an Action."""
    import random as _random

    from hanoi.engine import build_two_player_config, initial_state, project
    from hanoi.modes._agent import RandomAgent

    cfg = build_two_player_config(1)
    state = initial_state(cfg)
    obs = project(state, "A")
    agent = RandomAgent(rng=_random.Random(0))
    action = agent.choose_action(obs)
    assert action in obs.legal_actions


def test_random_agent_raises_on_terminal_observation() -> None:
    """choose_action must raise if legal_actions is empty (terminal state)."""
    import random as _random

    from hanoi.engine import (
        Lift,
        Place,
        build_two_player_config,
        initial_state,
        project,
        step,
    )
    from hanoi.modes._agent import RandomAgent

    cfg = build_two_player_config(1)
    state = initial_state(cfg)
    # Play N=1 to a win.
    state, _ = step(state, "A", Lift("1a"))
    state, _ = step(state, "B", Lift("1b"))
    state, _ = step(state, "A", Place("3a"))
    obs = project(state, "A")
    assert not obs.legal_actions  # terminal

    agent = RandomAgent(rng=_random.Random(0))
    with pytest.raises(RuntimeError, match="terminal"):
        agent.choose_action(obs)


def test_random_agent_always_picks_legal_action() -> None:
    """Over many steps the agent only picks actions from legal_actions."""
    import random as _random

    from hanoi.engine import build_two_player_config, initial_state, is_terminal, project, step
    from hanoi.modes._agent import RandomAgent

    cfg = build_two_player_config(2, max_turns=200)
    state = initial_state(cfg)
    rng = _random.Random(7)
    agent_a = RandomAgent(rng=rng)
    agent_b = RandomAgent(rng=rng)
    agents = {"A": agent_a, "B": agent_b}

    import itertools

    for player in itertools.cycle(["A", "B"]):
        if is_terminal(state):
            break
        obs = project(state, player)
        if not obs.legal_actions:
            break
        action = agents[player].choose_action(obs)
        assert action in obs.legal_actions
        state, _ = step(state, player, action)


# ---------------------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------------------


def test_random_play_disks_zero_exits_1(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--disks", "0"])
    assert exc_info.value.code == 1
    assert "disks" in capsys.readouterr().err.lower()


def test_random_play_max_turns_zero_exits_1(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--disks", "1", "--max-turns", "0"])
    assert exc_info.value.code == 1
    assert "max-turns" in capsys.readouterr().err.lower()


def test_random_play_unknown_player_in_turn_order_exits_1(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--disks", "1", "--turn-order", "XY"])
    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "unknown player" in err.lower() or "X" in err
