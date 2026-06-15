"""Tests for the replay CLI frontend (``hanoi-replay``).

Tests call ``hanoi.modes.replay.main()`` directly with ``capsys`` to capture
output, so no subprocess overhead is needed. ``pytest.raises(SystemExit)`` is
used when non-zero exit is expected.

Coverage (happy paths):
  * N=1 spec example — A wins.
  * N=2 A solo optimal solve (shared pole as buffer) — A wins in 6 steps.
  * N=2 B solo solve — B wins in 6 steps.
  * N=3 full optimal Hanoi solve — A wins in 14 steps.
  * A traps B's largest disk on 3a, then still wins (N=2).
  * All-legal replay up to DRAW (skip spam).
  * Terminal fires before all turns consumed — driver stops early.
  * Replay with one illegal move — step_count != attempt_count, exits 0.
  * Multiple consecutive illegal moves — step_count much less than attempt_count.
  * Unknown player in turn_order triggers ILLEGAL(UNKNOWN_PLAYER), exits 0.
  * Shared-pole usage round-trip (lift from 2, place on 2, lift again).
  * Using example fixture files directly.

Coverage (error paths — all exit 1 before engine is called):
  * Each malformed-input branch exits with code 1 before engine is called:
      - file not found
      - malformed JSON
      - wrong schema_version
      - missing / bad config field
      - num_disks out of range
      - max_turns out of range
      - turn_order not a list / empty
      - moves not a list
      - turn_order / moves length mismatch
      - unknown action type
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from hanoi.modes.replay import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_game(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "game.json"
    p.write_text(json.dumps(data))
    return p


def _n1_win_game() -> dict:
    """N=1: A lifts 1a, B lifts 1b, A places 3a -> A wins."""
    return {
        "schema_version": 1,
        "config": {"num_disks": 1},
        "turn_order": ["A", "B", "A"],
        "moves": [
            {"type": "lift", "pole": "1a"},
            {"type": "lift", "pole": "1b"},
            {"type": "place", "pole": "3a"},
        ],
    }


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

def test_replay_n1_a_wins(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    path = _write_game(tmp_path, _n1_win_game())
    main([str(path)])
    out = capsys.readouterr().out
    assert "WON" in out
    assert "winner:        A" in out
    assert "step_count:    3" in out
    assert "attempt_count: 3" in out


def test_replay_output_includes_per_step_log(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    path = _write_game(tmp_path, _n1_win_game())
    main([str(path)])
    out = capsys.readouterr().out
    assert "Step   1" in out
    assert "Step   2" in out
    assert "Step   3" in out
    # Each step labelled OK or ILLEGAL
    assert "-> OK" in out


def test_replay_early_stop_on_terminal(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Replay halts printing once a terminal is reached, ignoring later turns."""
    # N=1: A wins on step 3. Append extra (unused) turns that won't be printed.
    game = _n1_win_game()
    game["turn_order"].append("B")
    game["moves"].append({"type": "skip"})
    path = _write_game(tmp_path, game)
    main([str(path)])
    out = capsys.readouterr().out
    # Step 4 should not appear because the driver stops after the terminal.
    assert "Step   4" not in out


def test_replay_with_skip_draw(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """All-skip game should reach DRAW when max_turns is exhausted."""
    n = 4
    game = {
        "schema_version": 1,
        "config": {"num_disks": 2, "max_turns": n},
        "turn_order": ["A", "B", "A", "B"],
        "moves": [{"type": "skip"}] * n,
    }
    path = _write_game(tmp_path, game)
    main([str(path)])
    out = capsys.readouterr().out
    assert "DRAW" in out
    assert "winner:        None" in out


def test_replay_illegal_moves_are_valid_content(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Illegal moves in a replay must not cause a non-zero exit."""
    game = {
        "schema_version": 1,
        "config": {"num_disks": 1},
        # A tries to lift from B's invisible pole — illegal but valid replay.
        "turn_order": ["A"],
        "moves": [{"type": "lift", "pole": "1b"}],
    }
    path = _write_game(tmp_path, game)
    # Should not raise SystemExit
    main([str(path)])
    out = capsys.readouterr().out
    assert "ILLEGAL" in out
    assert "IN_PROGRESS" in out


def test_replay_with_explicit_max_turns(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    game = {
        "schema_version": 1,
        "config": {"num_disks": 2, "max_turns": 500},
        "turn_order": ["A", "B"],
        "moves": [{"type": "skip"}, {"type": "skip"}],
    }
    path = _write_game(tmp_path, game)
    main([str(path)])
    out = capsys.readouterr().out
    assert "max_turns=500" in out


def test_replay_skip_action(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    game = {
        "schema_version": 1,
        "config": {"num_disks": 1},
        "turn_order": ["A"],
        "moves": [{"type": "skip"}],
    }
    path = _write_game(tmp_path, game)
    main([str(path)])
    out = capsys.readouterr().out
    assert "IN_PROGRESS" in out
    assert "step_count:    1" in out


def test_replay_n2_a_solos_win(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """N=2: A solos 1a -> 3a using shared pole 2 as buffer."""
    game = {
        "schema_version": 1,
        "config": {"num_disks": 2},
        "turn_order": ["A"] * 6,
        "moves": [
            {"type": "lift", "pole": "1a"},
            {"type": "place", "pole": "2"},
            {"type": "lift", "pole": "1a"},
            {"type": "place", "pole": "3a"},
            {"type": "lift", "pole": "2"},
            {"type": "place", "pole": "3a"},
        ],
    }
    path = _write_game(tmp_path, game)
    main([str(path)])
    out = capsys.readouterr().out
    assert "WON" in out
    assert "winner:        A" in out
    assert "step_count:    6" in out


# ---------------------------------------------------------------------------
# Error-path tests (malformed input -> exit 1)
# ---------------------------------------------------------------------------

def test_replay_file_not_found(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["/nonexistent/path/game.json"])
    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "not found" in err.lower() or "ERROR" in err


def test_replay_malformed_json(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{this is not valid json")
    with pytest.raises(SystemExit) as exc_info:
        main([str(p)])
    assert exc_info.value.code == 1
    assert "JSON" in capsys.readouterr().err


def test_replay_wrong_schema_version(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    data = {**_n1_win_game(), "schema_version": 2}
    path = _write_game(tmp_path, data)
    with pytest.raises(SystemExit) as exc_info:
        main([str(path)])
    assert exc_info.value.code == 1
    assert "schema_version" in capsys.readouterr().err


def test_replay_missing_schema_version(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    data = _n1_win_game()
    del data["schema_version"]
    path = _write_game(tmp_path, data)
    with pytest.raises(SystemExit) as exc_info:
        main([str(path)])
    assert exc_info.value.code == 1


def test_replay_missing_config(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    data = _n1_win_game()
    del data["config"]
    path = _write_game(tmp_path, data)
    with pytest.raises(SystemExit) as exc_info:
        main([str(path)])
    assert exc_info.value.code == 1
    assert "config" in capsys.readouterr().err


def test_replay_missing_num_disks(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    data = _n1_win_game()
    del data["config"]["num_disks"]
    path = _write_game(tmp_path, data)
    with pytest.raises(SystemExit) as exc_info:
        main([str(path)])
    assert exc_info.value.code == 1
    assert "num_disks" in capsys.readouterr().err


def test_replay_num_disks_zero(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    data = _n1_win_game()
    data["config"]["num_disks"] = 0
    path = _write_game(tmp_path, data)
    with pytest.raises(SystemExit) as exc_info:
        main([str(path)])
    assert exc_info.value.code == 1


def test_replay_max_turns_zero(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    data = _n1_win_game()
    data["config"]["max_turns"] = 0
    path = _write_game(tmp_path, data)
    with pytest.raises(SystemExit) as exc_info:
        main([str(path)])
    assert exc_info.value.code == 1
    assert "max_turns" in capsys.readouterr().err


def test_replay_turn_order_not_list(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    data = _n1_win_game()
    data["turn_order"] = "ABAB"   # string, not list
    path = _write_game(tmp_path, data)
    with pytest.raises(SystemExit) as exc_info:
        main([str(path)])
    assert exc_info.value.code == 1


def test_replay_turn_order_empty(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    data = _n1_win_game()
    data["turn_order"] = []
    data["moves"] = []
    path = _write_game(tmp_path, data)
    with pytest.raises(SystemExit) as exc_info:
        main([str(path)])
    assert exc_info.value.code == 1


def test_replay_moves_not_list(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    data = _n1_win_game()
    data["moves"] = "not a list"
    path = _write_game(tmp_path, data)
    with pytest.raises(SystemExit) as exc_info:
        main([str(path)])
    assert exc_info.value.code == 1


def test_replay_length_mismatch(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    data = _n1_win_game()
    data["moves"].append({"type": "skip"})  # one extra move
    path = _write_game(tmp_path, data)
    with pytest.raises(SystemExit) as exc_info:
        main([str(path)])
    assert exc_info.value.code == 1
    assert "length" in capsys.readouterr().err


def test_replay_unknown_action_type(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    data = _n1_win_game()
    data["moves"][0] = {"type": "teleport", "pole": "3a"}
    path = _write_game(tmp_path, data)
    with pytest.raises(SystemExit) as exc_info:
        main([str(path)])
    assert exc_info.value.code == 1
    assert "invalid" in capsys.readouterr().err.lower()


def test_replay_move_missing_pole(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    data = _n1_win_game()
    data["moves"][0] = {"type": "lift"}  # pole missing
    path = _write_game(tmp_path, data)
    with pytest.raises(SystemExit) as exc_info:
        main([str(path)])
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Extended happy-path scenarios
# ---------------------------------------------------------------------------

def _n2_a_solo_game() -> dict:
    """N=2: A solos 1a -> 3a using pole 2 as buffer. 6 legal steps, A wins."""
    return {
        "schema_version": 1,
        "config": {"num_disks": 2},
        "turn_order": ["A"] * 6,
        "moves": [
            {"type": "lift", "pole": "1a"},
            {"type": "place", "pole": "2"},
            {"type": "lift", "pole": "1a"},
            {"type": "place", "pole": "3a"},
            {"type": "lift", "pole": "2"},
            {"type": "place", "pole": "3a"},
        ],
    }


def _n2_b_solo_game() -> dict:
    """N=2: B solos 1b -> 3b using pole 2 as buffer. 6 legal steps, B wins."""
    return {
        "schema_version": 1,
        "config": {"num_disks": 2},
        "turn_order": ["B"] * 6,
        "moves": [
            {"type": "lift", "pole": "1b"},
            {"type": "place", "pole": "2"},
            {"type": "lift", "pole": "1b"},
            {"type": "place", "pole": "3b"},
            {"type": "lift", "pole": "2"},
            {"type": "place", "pole": "3b"},
        ],
    }


def _n3_a_optimal_game() -> dict:
    """N=3: canonical Hanoi solve 1a -> 3a via 2. 14 legal steps, A wins."""
    return {
        "schema_version": 1,
        "config": {"num_disks": 3},
        "turn_order": ["A"] * 14,
        "moves": [
            {"type": "lift", "pole": "1a"}, {"type": "place", "pole": "3a"},
            {"type": "lift", "pole": "1a"}, {"type": "place", "pole": "2"},
            {"type": "lift", "pole": "3a"}, {"type": "place", "pole": "2"},
            {"type": "lift", "pole": "1a"}, {"type": "place", "pole": "3a"},
            {"type": "lift", "pole": "2"},  {"type": "place", "pole": "1a"},
            {"type": "lift", "pole": "2"},  {"type": "place", "pole": "3a"},
            {"type": "lift", "pole": "1a"}, {"type": "place", "pole": "3a"},
        ],
    }


def _n2_trap_game() -> dict:
    """N=2: B exposes disk 4 on pole 2; A traps it on 3a then solves. A wins."""
    return {
        "schema_version": 1,
        "config": {"num_disks": 2},
        "turn_order": ["B", "B", "B", "B", "A", "A", "A", "A", "A", "A", "A", "A"],
        "moves": [
            {"type": "lift", "pole": "1b"},  # B clears disk 2 to 3b
            {"type": "place", "pole": "3b"},
            {"type": "lift", "pole": "1b"},  # B puts disk 4 on shared pole
            {"type": "place", "pole": "2"},
            {"type": "lift", "pole": "2"},   # A traps disk 4 on 3a
            {"type": "place", "pole": "3a"},
            {"type": "lift", "pole": "1a"},  # A moves disk 1 to buffer
            {"type": "place", "pole": "2"},
            {"type": "lift", "pole": "1a"},  # A moves disk 3 on top of 4 on 3a
            {"type": "place", "pole": "3a"},
            {"type": "lift", "pole": "2"},   # A places disk 1 on 3a -> A wins
            {"type": "place", "pole": "3a"},
        ],
    }


# --- N=2 A solo ---

def test_replay_n2_a_solo_wins(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    path = _write_game(tmp_path, _n2_a_solo_game())
    main([str(path)])
    out = capsys.readouterr().out
    assert "WON" in out
    assert "winner:        A" in out
    assert "step_count:    6" in out
    assert "attempt_count: 6" in out
    # Board: A's disks {3,1} stacked on 3a, pole 2 cleared.
    assert "3a: [3, 1]" in out
    assert "2: []" in out


# --- N=2 B solo ---

def test_replay_n2_b_solo_wins(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    path = _write_game(tmp_path, _n2_b_solo_game())
    main([str(path)])
    out = capsys.readouterr().out
    assert "WON" in out
    assert "winner:        B" in out
    assert "step_count:    6" in out
    assert "3b: [4, 2]" in out
    assert "2: []" in out


def test_replay_b_solo_a_undisturbed(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """When B wins solo, A's disks stay untouched on 1a."""
    path = _write_game(tmp_path, _n2_b_solo_game())
    main([str(path)])
    out = capsys.readouterr().out
    assert "1a: [3, 1]" in out


# --- N=3 optimal ---

def test_replay_n3_a_wins_in_14_steps(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    path = _write_game(tmp_path, _n3_a_optimal_game())
    main([str(path)])
    out = capsys.readouterr().out
    assert "WON" in out
    assert "winner:        A" in out
    assert "step_count:    14" in out
    assert "attempt_count: 14" in out
    assert "3a: [5, 3, 1]" in out
    assert "2: []" in out


def test_replay_n3_all_steps_logged(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Every step (1-14) must appear in the log."""
    path = _write_game(tmp_path, _n3_a_optimal_game())
    main([str(path)])
    out = capsys.readouterr().out
    for i in range(1, 15):
        assert f"Step  {i:2d}" in out or f"Step {i:3d}" in out


def test_replay_n3_step_14_tagged_won(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """The winning step must carry the [WON] tag."""
    path = _write_game(tmp_path, _n3_a_optimal_game())
    main([str(path)])
    out = capsys.readouterr().out
    lines = out.splitlines()
    step14 = next(l for l in lines if "Step  14" in l or "Step  14" in l)
    assert "[WON]" in step14


# --- Trapping ---

def test_replay_trapping_a_wins_with_b_disk_on_3a(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """A traps B's disk 4 at the bottom of 3a and still satisfies the win predicate."""
    path = _write_game(tmp_path, _n2_trap_game())
    main([str(path)])
    out = capsys.readouterr().out
    assert "WON" in out
    assert "winner:        A" in out
    # Trap visible: 3a has B's disk 4 at bottom, then A's disks 3 and 1 on top.
    assert "3a: [4, 3, 1]" in out
    assert "2: []" in out


def test_replay_trapping_step_and_attempt_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    path = _write_game(tmp_path, _n2_trap_game())
    main([str(path)])
    out = capsys.readouterr().out
    assert "step_count:    12" in out
    assert "attempt_count: 12" in out


# --- Illegal moves: step_count vs attempt_count diverge ---

def test_replay_illegal_move_diverges_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """One illegal move makes attempt_count = step_count + 1."""
    game = {
        "schema_version": 1,
        "config": {"num_disks": 1},
        "turn_order": ["A", "A", "B", "A"],
        "moves": [
            {"type": "lift", "pole": "1b"},  # illegal: A can't see 1b
            {"type": "lift", "pole": "1a"},
            {"type": "lift", "pole": "1b"},
            {"type": "place", "pole": "3a"},
        ],
    }
    path = _write_game(tmp_path, game)
    main([str(path)])
    out = capsys.readouterr().out
    assert "WON" in out
    assert "step_count:    3" in out
    assert "attempt_count: 4" in out


def test_replay_illegal_move_reason_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    game = {
        "schema_version": 1,
        "config": {"num_disks": 1},
        "turn_order": ["A", "A", "B", "A"],
        "moves": [
            {"type": "lift", "pole": "1b"},
            {"type": "lift", "pole": "1a"},
            {"type": "lift", "pole": "1b"},
            {"type": "place", "pole": "3a"},
        ],
    }
    path = _write_game(tmp_path, game)
    main([str(path)])
    out = capsys.readouterr().out
    assert "ILLEGAL(POLE_NOT_VISIBLE)" in out


def test_replay_multiple_consecutive_illegals(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Five illegal moves then a legal skip: step_count=1, attempt_count=6."""
    game = {
        "schema_version": 1,
        "config": {"num_disks": 2},
        "turn_order": ["A", "A", "A", "A", "A", "A"],
        "moves": [
            {"type": "lift", "pole": "1b"},  # illegal
            {"type": "lift", "pole": "1b"},  # illegal
            {"type": "lift", "pole": "1b"},  # illegal
            {"type": "lift", "pole": "1b"},  # illegal
            {"type": "lift", "pole": "1b"},  # illegal
            {"type": "skip"},                # legal
        ],
    }
    path = _write_game(tmp_path, game)
    main([str(path)])
    out = capsys.readouterr().out
    assert "step_count:    1" in out
    assert "attempt_count: 6" in out
    assert out.count("ILLEGAL") == 5


def test_replay_hand_occupied_illegal(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Lifting while hand is already full -> ILLEGAL(HAND_OCCUPIED)."""
    game = {
        "schema_version": 1,
        "config": {"num_disks": 1},
        "turn_order": ["A", "A"],
        "moves": [
            {"type": "lift", "pole": "1a"},
            {"type": "lift", "pole": "1a"},  # hand occupied
        ],
    }
    path = _write_game(tmp_path, game)
    main([str(path)])
    out = capsys.readouterr().out
    assert "ILLEGAL(HAND_OCCUPIED)" in out


def test_replay_place_on_empty_hand_illegal(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Placing with empty hand -> ILLEGAL(HAND_EMPTY)."""
    game = {
        "schema_version": 1,
        "config": {"num_disks": 1},
        "turn_order": ["A"],
        "moves": [{"type": "place", "pole": "3a"}],
    }
    path = _write_game(tmp_path, game)
    main([str(path)])
    out = capsys.readouterr().out
    assert "ILLEGAL(HAND_EMPTY)" in out


def test_replay_placement_rule_violated(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Placing a larger disk on a smaller one -> ILLEGAL(PLACEMENT_RULE)."""
    # Put disk 1 on 2, then try to place disk 3 on top of it (3 > 1 violates Hanoi).
    game = {
        "schema_version": 1,
        "config": {"num_disks": 2},
        "turn_order": ["A", "A", "A", "A", "A"],
        "moves": [
            {"type": "lift", "pole": "1a"},   # hand = disk 1
            {"type": "place", "pole": "2"},    # 2 = (1)
            {"type": "lift", "pole": "1a"},   # hand = disk 3
            {"type": "place", "pole": "2"},    # 3 on top of 1 — ILLEGAL
            {"type": "skip"},
        ],
    }
    path = _write_game(tmp_path, game)
    main([str(path)])
    out = capsys.readouterr().out
    assert "ILLEGAL(PLACEMENT_RULE)" in out


def test_replay_lift_from_empty_pole_illegal(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Lifting from an empty pole -> ILLEGAL(POLE_EMPTY)."""
    game = {
        "schema_version": 1,
        "config": {"num_disks": 1},
        "turn_order": ["A"],
        "moves": [{"type": "lift", "pole": "3a"}],  # 3a starts empty
    }
    path = _write_game(tmp_path, game)
    main([str(path)])
    out = capsys.readouterr().out
    assert "ILLEGAL(POLE_EMPTY)" in out


# --- Unknown player is engine-level illegal, not a driver error ---

def test_replay_unknown_player_exits_0(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """An unknown player in turn_order causes ILLEGAL(UNKNOWN_PLAYER), not exit 1."""
    game = {
        "schema_version": 1,
        "config": {"num_disks": 1},
        "turn_order": ["C"],
        "moves": [{"type": "skip"}],
    }
    path = _write_game(tmp_path, game)
    # Must not raise SystemExit
    main([str(path)])
    out = capsys.readouterr().out
    assert "ILLEGAL(UNKNOWN_PLAYER)" in out


# --- Shared-pole round-trip ---

def test_replay_shared_pole_round_trip(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """A lifts from 1a, parks on shared pole 2, lifts again, places on 3a."""
    game = {
        "schema_version": 1,
        "config": {"num_disks": 1},
        "turn_order": ["A", "A", "A"],
        "moves": [
            {"type": "lift", "pole": "1a"},
            {"type": "place", "pole": "2"},
            {"type": "lift", "pole": "2"},
        ],
    }
    path = _write_game(tmp_path, game)
    main([str(path)])
    out = capsys.readouterr().out
    assert "IN_PROGRESS" in out
    assert "step_count:    3" in out
    # After lifting from 2 the shared pole is empty again.
    assert "2: []" in out


def test_replay_b_can_lift_from_shared_pole(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """B lifts A's disk 1 off the shared pole (the only A disk B can ever see)."""
    game = {
        "schema_version": 1,
        "config": {"num_disks": 1},
        "turn_order": ["A", "A", "B"],
        "moves": [
            {"type": "lift", "pole": "1a"},
            {"type": "place", "pole": "2"},
            {"type": "lift", "pole": "2"},   # B lifts A's disk from shared pole
        ],
    }
    path = _write_game(tmp_path, game)
    main([str(path)])
    out = capsys.readouterr().out
    # B now holds disk 1 and 2 is empty.
    assert "B: 1" in out
    assert "2: []" in out


# --- DRAW fires before all moves consumed ---

def test_replay_draw_fires_before_end_of_turns(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """max_turns=3 with 6 turns listed; driver stops at DRAW on turn 3."""
    game = {
        "schema_version": 1,
        "config": {"num_disks": 2, "max_turns": 3},
        "turn_order": ["A", "B", "A", "B", "A", "B"],
        "moves": [{"type": "skip"}] * 6,
    }
    path = _write_game(tmp_path, game)
    main([str(path)])
    out = capsys.readouterr().out
    assert "DRAW" in out
    assert "Step   4" not in out   # halted before step 4
    assert "attempt_count: 3" in out


# --- Output structure ---

def test_replay_final_state_shows_all_five_poles(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    path = _write_game(tmp_path, _n1_win_game())
    main([str(path)])
    out = capsys.readouterr().out
    for pole in ("1a", "1b", "2", "3a", "3b"):
        assert pole in out


def test_replay_final_state_shows_both_hands(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    path = _write_game(tmp_path, _n1_win_game())
    main([str(path)])
    out = capsys.readouterr().out
    assert "A:" in out
    assert "B:" in out


# --- Example fixture files ---

def test_replay_example_n1_a_wins(capsys: pytest.CaptureFixture) -> None:
    main(["examples/n1_a_wins.json"])
    out = capsys.readouterr().out
    assert "winner:        A" in out


def test_replay_example_n2_b_wins(capsys: pytest.CaptureFixture) -> None:
    main(["examples/n2_b_wins.json"])
    out = capsys.readouterr().out
    assert "winner:        B" in out
    assert "3b: [4, 2]" in out


def test_replay_example_n3_a_wins(capsys: pytest.CaptureFixture) -> None:
    main(["examples/n3_a_wins_optimal.json"])
    out = capsys.readouterr().out
    assert "winner:        A" in out
    assert "step_count:    14" in out
    assert "3a: [5, 3, 1]" in out


def test_replay_example_draw(capsys: pytest.CaptureFixture) -> None:
    main(["examples/draw_skip_only.json"])
    out = capsys.readouterr().out
    assert "DRAW" in out


def test_replay_example_illegal_moves(capsys: pytest.CaptureFixture) -> None:
    main(["examples/illegal_moves_valid_replay.json"])
    out = capsys.readouterr().out
    assert "ILLEGAL" in out
    assert "WON" in out   # game still concludes correctly


def test_replay_example_trapping(capsys: pytest.CaptureFixture) -> None:
    main(["examples/trapping_a_traps_b_disk4.json"])
    out = capsys.readouterr().out
    assert "winner:        A" in out
    assert "3a: [4, 3, 1]" in out
