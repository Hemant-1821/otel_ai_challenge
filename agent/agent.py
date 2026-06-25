"""Revenue Manager Agent — assembly point.

Creates the deep agent with all tools, skills, subagents, HITL, and memory.
Import `agent` from here to invoke or stream.
"""

from __future__ import annotations

from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

from tools import (
    get_as_of_otb,
    get_block_vs_transient_mix,
    get_otb_summary,
    get_pickup_delta,
    get_segment_mix,
)
from agent.prompts import SYSTEM_PROMPT
from agent.subagents import segment_analyst_subagent

# Resolve paths relative to this file so the agent works regardless of CWD
_PROJECT_ROOT = Path(__file__).parent.parent
_SKILLS_DIR = str(_PROJECT_ROOT / "skills")

# Filesystem backend rooted at the project — gives the agent access to skill
# files and any context documents without exposing the full host filesystem
_backend = FilesystemBackend(root_dir=str(_PROJECT_ROOT), virtual_mode=False)

# Single MemorySaver instance shared across all threads — required for HITL
# (interrupt/resume needs a checkpointer) and for multi-turn conversation memory
_checkpointer = MemorySaver()

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    backend=_backend,
    tools=[
        get_otb_summary,
        get_segment_mix,
        get_pickup_delta,
        get_as_of_otb,
        get_block_vs_transient_mix,
    ],
    system_prompt=SYSTEM_PROMPT,
    skills=[_SKILLS_DIR],
    subagents=[segment_analyst_subagent],
    # HITL: intercepts get_as_of_otb before execution, surfaces params to GM
    # for approval. Requires checkpointer to persist state during the pause.
    interrupt_on={"get_as_of_otb": True},
    checkpointer=_checkpointer,
)
