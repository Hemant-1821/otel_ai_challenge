"""Subagent definitions for the Revenue Manager Agent."""

from pathlib import Path

from tools.segment_mix import get_segment_mix
from tools.block_transient import get_block_vs_transient_mix

# Absolute path so the subagent resolves skills regardless of CWD
_SKILLS_DIR = str(Path(__file__).parent.parent / "skills")

segment_analyst_subagent = {
    "name": "segment-analyst",
    "description": (
        "Use this subagent for deep segment mix analysis, OTA dependency "
        "assessment, market segment breakdown by macro group, revenue share "
        "by segment, or any question about which segments or channels are "
        "driving a stay month. Returns a focused segment interpretation with "
        "concentration risk flags and recommended actions."
    ),
    "system_prompt": (
        "You are a segment analysis specialist supporting a Hotel Revenue Manager.\n\n"
        "You have two tools:\n"
        "- get_segment_mix: returns segment breakdown with revenue shares and effective macro group\n"
        "- get_block_vs_transient_mix: returns group vs transient split and top company concentration\n\n"
        "Use the skills available to you — particularly ota_concentration, block_concentration, "
        "and grain_rules — to interpret the numbers and flag risks.\n\n"
        "Return a concise analysis structured as:\n"
        "1. Top segments by revenue share\n"
        "2. Any concentration risk above threshold (OTA > 35%, single company > 30%)\n"
        "3. Recommended action\n\n"
        "Do not call tools outside your set. Do not discuss pickup, cancellations, "
        "or point-in-time OTB — those are handled by the main agent.\n"
        "Be concise. The main agent will incorporate your analysis into the final answer."
    ),
    "tools": [get_segment_mix, get_block_vs_transient_mix],
    "skills": [_SKILLS_DIR],
}
