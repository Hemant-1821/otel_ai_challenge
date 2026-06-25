# Agent Architecture — LangChain Deep Agents

## Required Harness

The agent MUST be built using **LangChain Deep Agents**. This is not optional.

```bash
pip install -qU deepagents langchain-anthropic   # or langchain-openai
```

Set: `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`) + Postgres connection string.

**Docs:** https://docs.langchain.com/oss/python/deepagents/overview

---

## What We Build

A single `create_deep_agent(...)` call assembled from the framework's building blocks:
- The LLM model
- Custom tools (our 5 required tools)
- System prompt (sharp revenue-manager persona)
- Skills (≥6 skill files)
- Filesystem backend
- Memory / HITL machinery

**Working out how these fit together from docs is part of the test** — the wiring is not handed to us.

---

## Building Blocks We MUST Use (All Required)

| Concept | What It Is | What's Required |
|---------|-----------|----------------|
| **Tools** | Custom `@tool` functions | Deliberately designed tool surface — correct grain, cancellations, right date/revenue fields |
| **Skills** | On-demand `SKILL.md` files (progressive disclosure) | ≥6 skills; ≥3 encode judgment (thresholds + recommended actions); ≥1 with numeric threshold + recommended action |
| **Subagents** | Specialized agents spawned via built-in task tool | **Required:** route segment-mix or block-mix work to a focused subagent (or document equivalent isolated skill routing in tests) |
| **Planning** | Built-in todo/planning tooling | Let agent decompose multi-part questions into ordered steps before tool calls |
| **Memory / Filesystem** | Virtual filesystem + long-term store | **Required:** persist multi-turn GM conversation — NOT stateless single-shot chat |
| **Human-in-the-loop** | Approval interrupts | **Required:** gate `get_as_of_otb` (and expensive point-in-time rebuilds) behind approval |
| **Model & system prompt** | `model=...`, `system_prompt=...` | Sharp revenue-manager persona holding the answer style |
| **MCP** | External tool servers via MCP | Optional (bonus) |

> **The bar:** a single `create_deep_agent()` call with one SQL tool is a **fail**. Must use all building blocks and explain why each was chosen.

---

## Skills Architecture

### Progressive Disclosure

Each skill is a `SKILL.md` file with YAML frontmatter:
```yaml
---
name: skill_name
description: precise description the agent uses to decide when to load this skill
---
```

Loaded **on demand** — agent reads the skill file when it decides it needs it.

### Skill Requirements

| Requirement | Count |
|-------------|-------|
| Total skills | ≥ 6 |
| Skills encoding **judgment** (thresholds + recommended actions) | ≥ 3 |
| Skills with numeric threshold + recommended action | ≥ 1 |
| `skills/CHALLENGE_SKILL.md` with `otel-rm-v2` in YAML description | 1 (required) |

### What "Judgment" Means in Skills

**Not enough:** skill that just defines metrics (makes agent accurate, not insightful)

**Required:** skills that encode **judgment of an experienced revenue manager**:
- Not what the numbers are, but how to **interpret** them
- What to **compare against**
- What **trap** to avoid
- What to actually **recommend**

Examples of judgment-encoded skills:
- OTA dependency: if OTA > 35% of segment mix → flag concentration risk → recommend direct booking promotion
- ADR thresholds: if room type ADR is below floor → recommend rate floor adjustment
- Cancellation pace: if cancellation rate accelerates in 30-day window → flag and recommend overbooking adjustment
- Pickup delta: if pickup rate for a future month is below prior-year pace → flag demand risk

---

## Required Subagent Routing

At minimum, **route segment-mix or block-mix work to a focused subagent**. This must be:
- Implemented in code, OR
- Documented as equivalent isolated skill routing with tests proving the behavior

---

## Human-in-the-Loop (HITL)

### Required: Gate `get_as_of_otb` Behind Approval

`get_as_of_otb` is a **point-in-time OTB rebuild** — heavy and parameter-sensitive.

Why HITL is required:
- LLM could hallucinate parameters (`as_of_utc`, date ranges) even with safeguards
- It's a computationally expensive operation
- The user should confirm: "Is this the right as-of date? Is this what you're asking for?"

This must be demonstrable in `tests/test_agent.py`.

---

## Memory / Filesystem

**Required:** persist multi-turn GM conversation. The agent must NOT be stateless.

Use the Deep Agents virtual filesystem + long-term store to:
- Remember prior questions in the session
- Build context across turns (e.g., "following up on what you said about July...")
- Persist GM preferences or previously surfaced insights

---

## Model & System Prompt

The system prompt must establish a **sharp revenue-manager persona** that:
- Answers like a revenue manager in a morning briefing (not a dashboard)
- Drives to commercial judgment and recommendations
- Maintains consistent answer style (see `docs/03_business_concepts.md`)
- Uses correct terminology and framing

---

## Tool Design Principle: Own Your Correctness

> Do NOT hand the model a single `run_sql(query)` tool

Risks of raw SQL approach:
- Model silently gets grain wrong (rows vs reservations)
- Forgets to exclude cancellations
- Picks wrong date field
- Picks wrong revenue field

**Strong solution:** put correctness in YOUR code:
- Deliberately designed tool layer with business rules baked in
- Tools return trustworthy, pre-validated data
- Model **composes answers from trustworthy building blocks** instead of improvising SQL
- Tools are **tested** to prove correctness

---

## ARCHITECTURE.md Requirements

`ARCHITECTURE.md` must be ≤1 page and include:
- Skill → tool routing matrix (which skills call which tools)
- Required: subagent routing documentation
- Required: HITL on `get_as_of_otb` documentation

See `ARCHITECTURE.example.md` for the template.

---

## What Scores Well

1. Correct, deliberate use of **all** building blocks — and ability to justify every choice
2. **Depth and quality of skills** — the single biggest differentiator
3. Tool layer that makes wrong answers hard (correct grain, cancellations, right dates/revenue)
4. Answers that read like a sharp revenue manager, not a dashboard

### How They Test Depth

- **Structural skill tests:** check thresholds, tool routing, adversarial guardrails (no live LLM calls in CI)
- **Agent tests:** assert HITL on `get_as_of_otb`, subagent routing, multi-tool plans
- **Live review:** Tier D/E questions — OTA dependency, block concentration, adversarial filters

---

## Phase 3 Deliverables Summary

| Artifact | Requirement |
|----------|-------------|
| `skills/` directory | ≥6 skills, ≥3 with judgment, ≥1 with numeric threshold+action |
| `ARCHITECTURE.md` | ≤1 page: skill→tool routing matrix + subagent + HITL |
| `skills/CHALLENGE_SKILL.md` | Skill pack version `otel-rm-v2` in YAML `description` frontmatter |
| `tests/test_skills.py` | ≥5 structural/judgment tests per `SKILL_TEST_SCENARIOS.md` |
| `tests/test_agent.py` | ≥4 routing/HITL tests per `AGENT_TEST_SCENARIOS.md` |

---

## Phase 2 Deliverables Summary

| Artifact | Requirement |
|----------|-------------|
| `vw_stay_night_base` view | Applied per `sql/VIEWS.example.sql` |
| `vw_segment_stay_night` view | Applied per `sql/VIEWS.example.sql` |
| 5 required tools | Per `REQUIRED_TOOLS.md` |
| `tools/METRIC_DEFINITIONS.md` | Committed metric definitions |
| No raw SQL tools exposed to model | Design principle |
| `tests/test_tools.py` | ≥10 cases per `TOOL_TEST_SCENARIOS.md` |
| `tests/test_skills.py` | ≥5 cases per `SKILL_TEST_SCENARIOS.md` |
| `tests/test_agent.py` | ≥4 cases per `AGENT_TEST_SCENARIOS.md` |
