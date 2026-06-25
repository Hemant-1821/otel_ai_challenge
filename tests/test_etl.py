"""
Phase 1 — ETL Tests (≥3 cases required)

Covers scenarios from tests/ETL_TEST_SCENARIOS.md:
  - All reservation IDs captured (no silent page drops)
  - Grain is correct (one row per reservation_id × stay_date, unique constraint holds)
  - Multi-night reservation expands into correct number of stay rows
  - Idempotency (re-running load produces same row count)
  - load_manifest gets one new row per run
"""

import pytest


def test_placeholder():
    """Remove this once real tests are written."""
    pass
