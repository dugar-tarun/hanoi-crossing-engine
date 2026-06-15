"""Public engine surface.

Importing from ``hanoi.engine`` is the supported way to use the engine; the
submodules are an implementation detail.
"""

from .actions import SKIP, Action, Lift, Place, _Skip
from .config import (
    ConfigError,
    GameConfig,
    PlayerId,
    PoleId,
    PoleSpec,
    build_two_player_config,
)
from .engine import (
    IllegalReason,
    StepResult,
    Terminal,
    initial_state,
    is_terminal,
    legal_actions,
    step,
)
from .observation import Observation, project
from .rules import disks_owned_by, goal_pole_of, hanoi_placement_legal, is_won_for
from .serialization import (
    action_from_dict,
    action_to_dict,
    config_from_dict,
    config_to_dict,
    state_from_dict,
    state_to_dict,
)
from .state import GameState, Status

__all__ = [
    # actions
    "Action",
    "Lift",
    "Place",
    "SKIP",
    "_Skip",
    # config
    "ConfigError",
    "GameConfig",
    "PlayerId",
    "PoleId",
    "PoleSpec",
    "build_two_player_config",
    # state
    "GameState",
    "Status",
    # rules
    "disks_owned_by",
    "goal_pole_of",
    "hanoi_placement_legal",
    "is_won_for",
    # engine
    "IllegalReason",
    "StepResult",
    "Terminal",
    "initial_state",
    "is_terminal",
    "legal_actions",
    "step",
    # observation
    "Observation",
    "project",
    # serialization
    "action_from_dict",
    "action_to_dict",
    "config_from_dict",
    "config_to_dict",
    "state_from_dict",
    "state_to_dict",
]
