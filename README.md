# Hanoi Crossing Engine

A deterministic, fully-testable game engine for **Hanoi Crossing** — a two-player
variant of the Tower of Hanoi where each player races to move their disks across
a shared board onto their goal pole.

## Layout

```
src/hanoi/
  engine/        # pure engine: config, state, rules, actions, observation, serialization
  modes/         # CLI frontends (random play, replay)
tests/           # pytest suite
```

## Install

This project uses [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Usage

```bash
# Play a game with random agents
uv run hanoi-random --disks 3 --seed 42

# Replay a recorded game from JSON
uv run hanoi-replay examples/n3_a_wins_optimal.json
```

## Development

```bash
uv run pytest        # run the test suite
uv run ruff check .  # lint
uv run ruff format . # format
```

### Pre-commit hooks

[pre-commit](https://pre-commit.com/) keeps the tree clean automatically. After
`uv sync`, install the git hooks once:

```bash
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
```

- **on commit:** trailing-whitespace / EOF fixers, YAML/TOML checks, and
  `ruff` lint (`--fix`) + format.
- **on push:** the full `pytest` suite.

Run every hook manually with `uv run pre-commit run --all-files`.
