"""Revenue Manager Agent — tool surface.

All five required tools are exported here. The agent is assembled from this
list; no raw SQL tool is ever exposed to the model.
"""

from .otb_summary import get_otb_summary
from .segment_mix import get_segment_mix
from .pickup_delta import get_pickup_delta
from .as_of_otb import get_as_of_otb
from .block_transient import get_block_vs_transient_mix

__all__ = [
    "get_otb_summary",
    "get_segment_mix",
    "get_pickup_delta",
    "get_as_of_otb",
    "get_block_vs_transient_mix",
]
