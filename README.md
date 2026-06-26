# Revenue Manager Agent — Build Challenge

## Build an AI Revenue Manager for a hotel GM

Build a **Revenue Manager Agent for a Hotel General Manager** using reservation
data, LangChain Deep Agents, and a Postgres database you populate via ETL.

**Build in your own repository** — do not fork this brief repo.

---

## How to start

1. **Create your own repo** for the solution (do not fork this brief).
2. **Read this README**, [REQUIRED_TOOLS.md](REQUIRED_TOOLS.md), and
   [SUBMISSION.md](SUBMISSION.md).
3. **Scrape the [data site](https://otel-hackathon-data-site.vercel.app)** and build
   ETL → tools → agent → deploy (phases below).
4. **Self-check before submitting:** run
   `scripts/compute_load_fingerprint.py` and reconcile with
   [/verify](https://otel-hackathon-data-site.vercel.app/verify) on scrape day.
5. **Submit** per [SUBMISSION.md](SUBMISSION.md) — repo URL, live agent URL, and
   credentials via the intake channel listed there.

Everything you need is in **this repository** plus the live data site. There is no
separate pack repo and no approval step before you begin building.

---

## How this challenge is gated

Work through the phases in order. Deliverables are checked objectively (tests,
`LOAD_PROOF` vs `/verify`, repo structure) — not via a pre-build approval DM.

| Phase | Deliverable                                                                             | Doc                                              |
| ----- | --------------------------------------------------------------------------------------- | ------------------------------------------------ |
| **0** | `ATTESTATION.md` (comprehension + one-line ETL note)                                    | [ATTESTATION.example.md](ATTESTATION.example.md) |
| **1** | ETL pipeline + `etl/LOAD_PROOF.json` + `etl/SCRAPE_MANIFEST.json`                       | Phase 1 below                                    |
| **2** | Required tools + `tests/test_tools.py` + `tests/test_skills.py` + `tests/test_agent.py` | [REQUIRED_TOOLS.md](REQUIRED_TOOLS.md)           |
| **3** | Skills + `ARCHITECTURE.md`                                                              | Phase 3 below                                    |
| **4** | Live deployed agent + submission                                                        | [SUBMISSION.md](SUBMISSION.md)                   |
| **5** | Engineering interview (by invitation)                                                   | Phase 5 below                                    |

### How we review

- Submissions must reconcile with the **live data site** and the ETL **you** built.
- Understand **grain, dates, and OTB filters** — do not treat the brief as a single
  codegen prompt.
- Coding assistants are fine. Passing `compute_load_fingerprint.py` is necessary
  but not sufficient; we run additional internal checks on submitted repos.
- You will receive a **submission received** acknowledgment only — not scores,
  ranks, or rubric feedback.

---

## Quick start

```bash
docker compose up
```

This starts Postgres on port `5432` with:

- database: `hotel_hackathon`
- user: `hackathon`
- password: `hackathon`

Connection string:

```
postgresql://hackathon:hackathon@localhost:5432/hotel_hackathon
```

> **Important — the database starts empty.** `docker compose up` creates the
> tables (via `schema.sql`) but **there is no data seed.** You do **not** get the
> reservation dataset as a file. Your first job is to **build an ETL that scrapes
> the data from a public website and loads it into this database** — see the
> next section. The schema below tells you exactly what shape to load it into.

### Files

- `schema.sql` — creates the (empty) tables you will load into
- `docker-compose.yml` — boots a local Postgres instance
- `sql/VIEWS.example.sql` — semantic view templates for Phase 2
- `REQUIRED_TOOLS.md` — Phase 2 tool contract
- `ARCHITECTURE.example.md` — Phase 3 architecture template
- `ATTESTATION.example.md` — Phase 0 attestation template
- `scripts/compute_load_fingerprint.py` — generate `etl/LOAD_PROOF.json` after load
- `tests/ETL_TEST_SCENARIOS.md`, `tests/TOOL_TEST_SCENARIOS.md` — published test properties
- `tests/SKILL_TEST_SCENARIOS.md`, `tests/AGENT_TEST_SCENARIOS.md` — skill & agent tests
- `etl/LOAD_PROOF.example.json`, `etl/SCRAPE_MANIFEST.example.json` — proof shapes
- `SUBMISSION.md` — how to submit when done

---

## Phase 0 — Comprehension attestation

Copy [ATTESTATION.example.md](ATTESTATION.example.md) to your solution repo as
`ATTESTATION.md` and answer all comprehension prompts. Include a **one-line ETL
design** (pagination + idempotency + anchor date) in the attestation or your
`ARCHITECTURE.md`.

Commit `ATTESTATION.md` before final submission. There is no pre-build approval
step — start ETL when you are ready, but shallow attestations are flagged during
internal review.

---

## Phase 1 — ETL (scrape → load)

There is **no seed file**. The reservation dataset lives on a **public website**,
and your first deliverable is an **ETL pipeline** that scrapes it and loads it
into your Postgres database. This is a deliberate part of the challenge — we want
to see that your team can build a real ingestion script, not just point an agent
at a database somebody else filled.

> **Data site:** **https://otel-hackathon-data-site.vercel.app**
> It renders the reservation data as HTML pages — a paginated
> [**reservation list**](https://otel-hackathon-data-site.vercel.app/reservations),
> a **detail page per reservation** (`/reservations/<id>`), a
> [**reference page**](https://otel-hackathon-data-site.vercel.app/reference)
> with lookup tables (room types, markets, channels, **rate plans**, and
> market macro-group effective dates), and a
> [**verify page**](https://otel-hackathon-data-site.vercel.app/verify) you can
> use to check your load. The site footer links to a **dataset changelog** —
> read it if your scrape predates a deploy. There is no JSON API and no CSV
> download; scrape the rendered pages. Data is **client-rendered**, so plain
> `curl` returns an empty shell — drive a real browser.

### What "ETL" means here

1. **Extract** — scrape the data site with a browser-automation tool
   (**Playwright** is the expected choice). The pages are client-rendered, so a
   plain `curl` will not see the data — you need to drive a real browser, wait
   for content to render, page through the list (**100 reservations per page**),
   and follow each reservation into its detail page to capture the per-night
   stay rows and the fields that only appear on the detail view.
2. **Transform** — parse the scraped HTML into clean, typed records that match
   `schema.sql`: the **fact table** is one row per **reservation × stay_date**
   (see Section 4 — grain is the whole game), plus **lookup tables** and
   `market_macro_group_history` from the reference page. Detail pages carry
   `financial_status`, `property_date`, and fields not shown on the list view.
3. **Load** — insert into the Postgres tables from the Quick start. Append a row
   to `load_manifest` on every run (`dataset_revision`, `scraped_at`, `source_url`,
   `row_hash`). Make the load **idempotent** (truncate-and-reload or upsert) so you
   can safely re-run without duplicates.

### How often it runs

**Once per build is fine** — you do **not** need a daily cron. However, the data
site regenerates its dataset from **today's date** (the **anchor date**). The
book is stable **within a calendar day** but row counts and OTB aggregates shift
when the anchor changes. **Scrape and reconcile against `/verify` on the same
day** you load and submit. Re-run ETL on demand if you wipe the DB or need a
fresh load. We care that the pipeline is **correct, idempotent, and
reproducible** for a given anchor date, not that it runs on a schedule.

### What scores well

- A **robust scraper** that handles pagination and the list → detail drill-in,
  waits for rendered content, and doesn't silently drop rows.
- A **verification step** — after loading, check your row counts and a few
  aggregates against what the site shows (the site exposes a verify/summary view
  for exactly this). Prove your load is complete and correct.
- **Idempotency and reproducibility** — anyone can run it from scratch and get
  the same database.
- Clean separation of extract / transform / load, with the transform enforcing
  the correct grain and types.

Only once your database is populated does the agent work below make sense — the
agent reads the database **you** built.

### Phase 1 deliverables

#### `etl/SCRAPE_MANIFEST.json`

After scraping, commit a manifest proving you captured the full reservation list.
Shape and fields are documented in [etl/SCRAPE_MANIFEST.example.json](etl/SCRAPE_MANIFEST.example.json).

Required fields include:

```json
{
  "anchor_date": "YYYY-MM-DD",
  "pages_scraped": 3,
  "reservation_ids_count": 254,
  "reservation_ids_sha256": "<sha256 of sorted reservation_id lines>"
}
```

`reservation_ids_sha256` is the SHA-256 of sorted `reservation_id` lines (one ID per
line). It must match `count(distinct reservation_id)` in your DB and
`total_reservations` on `/verify`.

#### `etl/LOAD_PROOF.json`

After ETL, generate a load proof using [scripts/compute_load_fingerprint.py](scripts/compute_load_fingerprint.py):

```bash
pip install 'psycopg[binary]'
python scripts/compute_load_fingerprint.py --output etl/LOAD_PROOF.json
```

Optional cross-check against your manifest:

```bash
python scripts/compute_load_fingerprint.py \
  --manifest etl/SCRAPE_MANIFEST.json \
  --output etl/LOAD_PROOF.json
```

Commit `etl/LOAD_PROOF.json` in your solution repo. It must match your hosted
database and the data site [verify page](https://otel-hackathon-data-site.vercel.app/verify).
Example shape is in [etl/LOAD_PROOF.example.json](etl/LOAD_PROOF.example.json).

**Phase 1 checklist**

- [x] Playwright (or equivalent) scraper with pagination + list → detail drill-in
- [x] Idempotent load into [schema.sql](schema.sql) shape
- [x] `load_manifest` populated on every ETL run
- [x] `etl/SCRAPE_MANIFEST.json` committed
- [x] `etl/LOAD_PROOF.json` committed
- [ ] `tests/test_etl.py` with ≥ 3 cases covering [published ETL scenarios](tests/ETL_TEST_SCENARIOS.md)
- [x] Row counts reconciled with `/verify`

---

## Phase 2 — Tool layer

Implement the five required tools and semantic views exactly as specified in
[REQUIRED_TOOLS.md](REQUIRED_TOOLS.md). Ship:

- `tests/test_tools.py` — **≥ 10** cases covering [tool scenarios](tests/TOOL_TEST_SCENARIOS.md)
- `tests/test_skills.py` — **≥ 5** cases covering [skill scenarios](tests/SKILL_TEST_SCENARIOS.md)
- `tests/test_agent.py` — **≥ 4** cases covering [agent scenarios](tests/AGENT_TEST_SCENARIOS.md)

Skill and agent tests should use **structure mocks and graph introspection** where
possible — not live LLM calls in CI.

**Phase 2 checklist**

- [x] `vw_stay_night_base` and `vw_segment_stay_night` applied (see [sql/VIEWS.example.sql](sql/VIEWS.example.sql))
- [x] All five required tools implemented
- [x] `tools/METRIC_DEFINITIONS.md` committed (see [REQUIRED_TOOLS.md](REQUIRED_TOOLS.md))
- [x] No raw SQL string tools exposed to the model
- [ ] `tests/test_tools.py`, `tests/test_skills.py`, `tests/test_agent.py` pass locally

---

## Phase 3 — Skills and architecture

Build the agent with **LangChain Deep Agents** (details below). Phase 3 artifacts:

| Artifact                    | Requirement                                                                                                                                                                            |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `skills/`                   | Minimum **6** skills; **≥3** encode **judgment** (thresholds + recommended actions), not just metric definitions; **≥1** skill must include a numeric threshold and recommended action |
| `ARCHITECTURE.md`           | ≤1 page: skill→tool routing matrix; **required** subagent + HITL on `get_as_of_otb` (see [ARCHITECTURE.example.md](ARCHITECTURE.example.md))                                           |
| `skills/CHALLENGE_SKILL.md` | Skill pack version `otel-rm-v2` in YAML `description` frontmatter                                                                                                                      |
| `tests/test_skills.py`      | ≥5 structural/judgment tests per [tests/SKILL_TEST_SCENARIOS.md](tests/SKILL_TEST_SCENARIOS.md)                                                                                        |
| `tests/test_agent.py`       | ≥4 routing/HITL tests per [tests/AGENT_TEST_SCENARIOS.md](tests/AGENT_TEST_SCENARIOS.md)                                                                                               |

---

## Phase 2–3 — Build the agent with LangChain Deep Agents (required harness)

Once your ETL has populated the database (Step 1), build your Revenue Manager
Agent on top of it. You must build it using **LangChain Deep Agents**.

> **Read the docs first:** https://docs.langchain.com/oss/python/deepagents/overview

Deep Agents is an opinionated agent harness built on LangChain + LangGraph. It gives you planning, a virtual filesystem, subagents, skills, memory, and human-in-the-loop **out of the box** — you _configure_ these capabilities, you don't hand-roll them. We are using this challenge to confirm that your team can do real agent engineering and that you understand the core concepts of the framework, not just call an LLM in a loop.

**The bar:** a single `create_deep_agent()` call with one SQL tool is a _fail_. We want to see you deliberately use the building blocks below and be able to explain _why_ you reached for each one.

### 0.1 Install

```bash
pip install -qU deepagents langchain-anthropic   # or langchain-openai, etc.
```

Set the relevant API key (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`) and the Postgres connection string from the Quick start above.

### 0.2 What you build

Your entry point is a single `create_deep_agent(...)` call that you assemble from
the framework's building blocks — the model, your tools, a system prompt, your
skills, a filesystem backend, and the memory / human-in-the-loop machinery.
**Working out how these fit together from the documentation is part of the
test**, so we don't hand you the wiring. The [Deep Agents
docs](https://docs.langchain.com/oss/python/deepagents/overview) describe every
parameter — build from those.

### 0.3 Concepts we expect you to use

Use **all** of these building blocks, and be ready to explain _why_ you reached
for each. We are not prescribing _how_ — designing the solution is the point.

| Concept                   | What it is in Deep Agents                                    | What we're looking for                                                                                                                     |
| ------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **Tools**                 | Custom `@tool` functions you pass to the agent               | A deliberately designed tool surface — you decide what the tools are, their arguments, and their return shapes (see the principle in 0.6). |
| **Skills**                | On-demand `SKILL.md` files loaded via progressive disclosure | Skills are the heart of this challenge (see 0.7). We judge their **depth and attention to detail** directly.                               |
| **Subagents**             | Specialised agents spawned via the built-in task tool        | **Required:** route segment-mix or block-mix work to a focused subagent (or document equivalent isolated skill routing in tests).          |
| **Planning**              | Built-in todo / planning tooling                             | Let the agent decompose multi-part questions into ordered steps before tool calls.                                                         |
| **Memory / Filesystem**   | Virtual filesystem + a long-term store                       | **Required:** persist multi-turn GM conversation — not stateless single-shot chat.                                                         |
| **Human-in-the-loop**     | Approval interrupts                                          | **Required:** gate `get_as_of_otb` (and any other expensive point-in-time rebuild) behind approval.                                        |
| **Model & system prompt** | `model=...`, `system_prompt=...`                             | A sharp revenue-manager persona that holds the answer style in Section 12.                                                                 |
| **MCP (bonus)**           | External tool servers via MCP                                | Optional.                                                                                                                                  |

### 0.4 Skills use progressive disclosure

Each skill is a `SKILL.md` file with YAML frontmatter (at minimum `name` and a
precise `description`) that the agent loads on demand — read the docs for the
exact format. How you structure, name, scope, and write your skills is your
decision, and is a large part of what we evaluate.

### 0.5 What scores well

- Correct, deliberate use of **all** the building blocks in 0.3 — and the ability
  to justify every choice.
- **The depth and quality of your skills** (0.7). This is the single biggest
  differentiator, and we probe it directly (see below).
- A tool layer that makes wrong answers hard — correct grain, cancellations, and
  the right date and revenue fields (see Sections 4–8).
- Answers that read like a sharp revenue manager, not a dashboard (Section 12).

**How we test skill and agent depth.**

- **Published test suites:** `tests/test_tools.py` (≥10), `tests/test_skills.py` (≥5),
  `tests/test_agent.py` (≥4) — scenarios in `tests/*_TEST_SCENARIOS.md`
- **Structural skill tests** check thresholds, tool routing, and adversarial guardrails
  without burning API credits
- **Agent tests** assert HITL on `get_as_of_otb`, subagent routing, and multi-tool plans
- **Live review** uses Tier D/E questions (OTA dependency, block concentration, adversarial filters)

A surface-level skill produces a generic or wrong answer; a well-crafted one shows real
revenue-management thinking. **Your skills are graded on what they actually make the
agent capable of.**

### 0.6 Design principle: own your correctness (don't lean on raw `run_sql`)

Handing the model a single `run_sql(query)` tool and letting it write arbitrary
SQL is the easy path and a weak one: **you** lose control of correctness, and the
model can silently get the grain wrong (rows vs reservations), forget to exclude
cancellations, or pick the wrong date or revenue field. Strong solutions put
correctness in **their own code** — a deliberately designed tool layer with the
business rules baked in and **tested** — so the agent composes answers from
trustworthy building blocks instead of improvising SQL. How you design that
surface (what the tools are, their arguments, their return shapes, how you test
them) is yours to decide, and is part of what we evaluate.

### 0.7 The skills are the real test: teach the agent to _think_ like a revenue manager

Most teams will write a skill that defines metrics. That makes the agent
_accurate_, not _insightful_ — and it is not enough. What separates a strong
submission is a set of skills that encode the **judgment of an experienced
revenue manager**: not what the numbers are, but how to interpret them, what to
compare against, what trap to avoid, and what to actually recommend.

We are deliberately **not** giving you the heuristics, the thresholds, or a list
of skills to write. Discovering what an expert revenue manager actually knows —
and encoding it with real attention to detail — _is the challenge._ This is where
we spend most of our judging time, and where the hard questions in 0.5 are aimed.

A team that ships genuine revenue-management reasoning here — so the agent
delivers commercial judgment, not a dashboard read aloud — is demonstrating
exactly what this challenge is testing.

---

## Phase 4 — Deploy and submit

Your final deliverable is a **live URL** where your agent is running and ready to
answer revenue-manager questions. We review submissions internally (repo +
deployed agent). There is no default live eval slot — submit when you are ready.

### What the URL must be

A web page with a **chat box**: we type a revenue-manager question (e.g. _"What's
driving July?"_, _"Are we too dependent on OTA?"_), and your **Deep Agent
answers** — in plain English, with the numbers, like the examples in Section 11.

- The answer must come **from your agent**, reading **your database** (the one
  your ETL filled in Step 1). No hard-coded or pre-written answers.
- The agent must be **live and responsive** when we review. If it sleeps or the
  database is down, there is nothing to evaluate.
- It does **not** need to look pretty. A plain chat box is completely fine.

### Protect it (required)

Put the URL behind **HTTP basic auth** or a simple login screen so it cannot be
spammed publicly.

- **Share the URL** in your submission.
- **Send credentials privately** via the intake channel in [SUBMISSION.md](SUBMISSION.md)
  — never in your README or repo.

### How to submit

See [SUBMISSION.md](SUBMISSION.md) for the checklist and intake details. In short:

1. **Live agent URL**
2. **Username + password** (private intake only)
3. **Link to your solution repo** (public or private with collaborator access)

### Deployment hints

You need three things running and reachable: your **database**, your **agent
backend**, and a **front-end** that talks to it.

- **Database:** a hosted Postgres (e.g. Supabase, Neon, Railway). Run your ETL
  once to fill it; a DB on your laptop won't be reachable by a deployed app.
- **API key:** set your model API key in the deployment environment — never
  commit it.

**Show your work in the UI (required).** For each question we must **see** which
**tools** ran and which **skills** loaded, streamed live. Plain chat-only UIs
without tool/skill visibility are insufficient. (In Deep Agents, loading a skill is
a file-read tool call — surface tool calls and you surface skills.) You do **not**
need raw chain-of-thought.

**Health endpoint (required).** Expose e.g. `GET /health` returning JSON:

```json
{
  "db_fingerprint": "<reservation_stay_status_sha256 from LOAD_PROOF>",
  "dataset_revision": "<from load_manifest /verify>",
  "row_hash": "<load_manifest row_hash>",
  "financial_status_posted_only_rows": "<posted_stay_rows from LOAD_PROOF aggregates>"
}
```

We call this before chat to confirm your live DB matches your submitted proof.

Because Deep Agents runs on **LangGraph**, the easiest path is to serve your agent
as a LangGraph app and connect a ready-made UI that already renders streaming
tool calls and subagent activity (e.g. the **deepagents UI** / **Agent Chat UI**)
rather than hand-build one. A small custom front-end that streams tool/skill
events is also fine. Plain **Streamlit** works but won't surface this detail well,
so prefer a UI that shows tool and skill calls.

### Phase 4 submission checklist

- [x] `ATTESTATION.md`, `etl/SCRAPE_MANIFEST.json`, `etl/LOAD_PROOF.json`, `tools/METRIC_DEFINITIONS.md`, tools, skills, `ARCHITECTURE.md` in my repo
- [x] Database hosted and loaded by my ETL (not on my laptop)
- [x] Agent deployed with streaming tool/skill UI + `GET /health`
- [x] URL protected with username/password
- [x] Separate repo (not a fork of this brief)
- [ ] Submitted per [SUBMISSION.md](SUBMISSION.md) (URL + credentials + repo link)
- [ ] Service stays up for at least 7 days after submission

---

## Phase 5 — Engineering interview (invitation only)

Shortlisted candidates (~15–20 minutes):

1. Explain one tool implementation (grain / cancellation logic)
2. Fix a failing `test_tools.py` case by patching the tool, not the test
3. Extend an existing skill with one new judgment rule live

---

## Reference

Domain reference for Phases 0–4. Read before you build tools and skills.

---

## 1. What this dataset is for

This dataset is designed for a build challenge where you build a **Revenue Manager Agent for a hotel General Manager (GM)**.

Build a **Revenue Manager Agent for a Hotel General Manager**.

Using reservation data, detect what is changing in future business - pickup, cancellations, segment mix, and emerging risks or opportunities - and turn it into clear commercial judgment.

Show the GM what matters most, why it matters, and what action they should take next.

The agent should handle natural-language business questions such as:

- What revenue is on the books by month?
- What is driving July?
- Are we too dependent on OTA?
- How much business was cancelled in June?
- Which room type has the highest ADR?
- How much group business do we have?
- What changed in the last 7 days for future stays?

The agent should be able to:

1. understand the question,
2. query the dataset correctly,
3. return the answer in plain English,
4. explain the main drivers,
5. show numbers clearly,
6. mention assumptions or caveats when needed.

---

## 2. Important business context

This dataset comes from a hotel reservations context, but it has been simplified for the challenge.

You do **not** need to know hotel industry jargon in advance. This guide explains the business concepts and table meanings.

### Core idea

A hotel sells rooms for specific stay dates.

A reservation might be:

- created long before arrival,
- cancelled before arrival,
- direct or OTA,
- transient or group,
- one room or multiple rooms.

This dataset is designed to help a GM understand:

- business on the books,
- booking pace,
- segment mix,
- room type mix,
- cancellations,
- concentration risk,
- group vs transient demand.

---

## 3. Dataset overview

The dataset currently contains:

- **7 tables** (see [schema.sql](schema.sql))
- **stay-date rows** in `reservations_hackathon` — count is **anchor-dependent**;
  reconcile against `/verify` on scrape day (see [§15](#15-dataset-shape))
- lookup tables for room types, rate plans, market segments (with effective-dated macro groups), and channels

### Tables

- `public.reservations_hackathon`
- `public.room_type_lookup`
- `public.rate_plan_lookup`
- `public.market_code_lookup`
- `public.market_macro_group_history`
- `public.channel_code_lookup`
- `public.load_manifest`

---

## 4. The most important concept: table grain

### `reservations_hackathon` is **not** one row per reservation

It is:

**one row per reservation x stay_date**

That means:

- if a reservation stays 3 nights, it creates 3 rows
- if a reservation has multiple rooms, `number_of_spaces` tells you how many rooms are attached
- counting rows is **not** the same as counting reservations

This is the single most important thing to understand.

### Example

A guest books 2 rooms for 3 nights.

That creates:

- 3 rows in `reservations_hackathon`
- each row has `number_of_spaces = 2`

So:

- **reservation count** = 1
- **stay rows** = 3
- **room nights** = 6

---

## 5. Business concepts

### Reservation

A hotel booking.

### Stay date

The actual night being stayed.

### Arrival date

The date the guest checks in.

### Departure date

The date the guest checks out.

### Booking date

When the reservation was created. In this dataset, that is `create_datetime`.

### OTB / On-the-books

Business that currently exists in the reservation data for future stay dates.

### ADR

Average Daily Rate. In simplified terms, revenue per room night.

### Room nights

How many rooms are occupied across nights.  
Example:

- 1 room for 3 nights = 3 room nights
- 2 rooms for 3 nights = 6 room nights

### OTA

Online Travel Agency, such as Booking.com or Expedia.

### Direct

Business that comes directly through the hotel’s own website / reservations / walk-ins.

### Group business

Reservations tied to a conference, corporate group, event, or similar multi-room booking.
For mix analysis, filter on the `is_block` flag in the fact table.

### Transient business

Normal individual bookings, usually not group blocks (non-group rows).

### Lead time

Days between booking creation and arrival date.

---

## 6. Table reference

## 6.1 `public.reservations_hackathon`

This is the main fact table.  
Almost all GM questions will be answered primarily from this table.

### Row grain

**One row per reservation x stay_date**

### Columns

#### `reservation_stay_id`

- Type: `bigint`
- Primary key
- Unique row identifier for this table

#### `reservation_id`

- Type: `text`
- Reservation identifier
- Multiple rows can share the same `reservation_id` if the reservation spans multiple nights

#### `arrival_date`

- Type: `date`
- Guest check-in date

#### `departure_date`

- Type: `date`
- Guest check-out date
- The guest stays up to, but not including, this date

#### `stay_date`

- Type: `date`
- The specific night represented by this row
- This is the most important date for revenue-on-stay analysis

#### `property_date`

- Type: `date`
- Hotel business date attributed to this stay row (from the detail page)
- Usually equals `stay_date`; may differ on night-boundary / audit rows — see Appendix B

#### `reservation_status`

- Type: `text`
- Example values include:
  - `Reserved`
  - `Cancelled`
- Use this carefully in analysis
- Many business questions should exclude cancelled reservations unless explicitly asked

#### `financial_status`

- Type: `text`
- Values: `Posted`, `Provisional`
- See Appendix A for default OTB treatment

#### `create_datetime`

- Type: `timestamptz`
- When the reservation was created (**stored in UTC**)
- Use this for:
  - booking pace
  - pickup analysis
  - “as of” views
  - “what changed recently?”
- Pickup window boundaries: see Appendix B (`Europe/London`)

#### `cancellation_datetime`

- Type: `timestamptz`, nullable
- When the reservation was cancelled
- Only populated for cancelled reservations

#### `guest_country`

- Type: `text`, nullable
- Guest country code / nationality grouping
- Can be used for mix analysis

#### `is_block`

- Type: `boolean`
- Whether this booking is treated as a block / group-style reservation

#### `is_walk_in`

- Type: `boolean`
- Whether the booking was a walk-in

#### `number_of_spaces`

- Type: `integer`
- Number of rooms on this reservation for that stay date
- In hotel language, “spaces” here effectively means rooms
- Important for room-night calculations

#### `space_type`

- Type: `text`
- Room type code
- Join to `room_type_lookup`

#### `market_code`

- Type: `text`
- Market / segment code
- Join to `market_code_lookup`

#### `channel_code`

- Type: `text`
- Booking channel code
- Join to `channel_code_lookup`

#### `source_name`

- Type: `text`
- Human-readable booking source
- Examples:
  - Booking.com
  - Expedia
  - Brand website
  - OCC Central Reservations
  - Walk-in

#### `rate_plan_code`

- Type: `text`
- Rate code / pricing plan attached to the booking
- Examples:
  - `BOOKBAR`
  - `GROUPBB`
  - `DLY1`
  - `FITBB`
- Useful for pricing / commercial analysis, but not required for all questions

#### `daily_room_revenue_before_tax`

- Type: `numeric`
- Room revenue for this row’s stay date before tax
- Use this when the question is specifically about room revenue

#### `daily_total_revenue_before_tax`

- Type: `numeric`
- Total revenue for this row’s stay date before tax
- Includes room revenue and potentially package / breakfast effects in the synthetic dataset
- Use this for broader revenue questions

#### `nights`

- Type: `integer`
- Length of stay of the reservation
- Repeated on each stay-date row belonging to the same reservation

#### `adr_room`

- Type: `numeric`
- Room ADR for the reservation
- Repeated across the stay rows of the reservation

#### `lead_time`

- Type: `integer`
- Number of days between booking creation and arrival
- Useful for pickup and booking-window analysis

#### `company_name`

- Type: `text`, nullable
- Company associated with the reservation, especially for corporate / group business

#### `travel_agent_name`

- Type: `text`, nullable
- Travel agent name when relevant

---

## 6.2 `public.room_type_lookup`

Lookup table for room type codes.

### Grain

One row per room type code.

### Columns

#### `space_type`

- Type: `text`
- Primary key
- Join key from `reservations_hackathon.space_type`

#### `room_class`

- Type: `text`
- Broad class of room
- Example:
  - Standard
  - Executive

#### `display_name`

- Type: `text`
- Human-friendly room type name

#### `number_of_rooms`

- Type: `integer`
- Number of physical rooms of this type in the hotel
- Useful context for supply / mix analysis

---

## 6.3 `public.market_code_lookup`

Lookup table for business segment / market codes.

### Grain

One row per market code.

### Columns

#### `market_code`

- Type: `text`
- Primary key
- Join key from `reservations_hackathon.market_code`

#### `market_name`

- Type: `text`
- Human-readable segment name

#### `macro_group`

- Type: `text`
- Broader grouping of the segment
- Examples:
  - Retail
  - Corporate
  - MICE
  - Leisure
  - Leisure Group

#### `description`

- Type: `text`
- Plain-English description of the market code

### Included market codes

- `OTA` = Online Travel Agency
- `BAR` = Best Available Retail
- `PROM` = Promotional Retail
- `FIT` = Free Independent Traveller
- `CSR` = Corporate Negotiated
- `CNR` = Corporate Room Nights
- `CNI` = Conference / Incentive Group
- `CGR` = Corporate Group
- `EVEN` = Event Demand
- `SMERF` = SMERF Group

---

## 6.4 `public.channel_code_lookup`

Lookup table for booking channels.

### Grain

One row per channel code.

### Columns

#### `channel_code`

- Type: `text`
- Primary key
- Join key from `reservations_hackathon.channel_code`

#### `channel_name`

- Type: `text`
- Human-readable channel name

#### `channel_group`

- Type: `text`
- Broad grouping of the channel
- Examples:
  - Digital
  - Direct
  - Offline

### Included channel codes

- `WEB`
- `REC`
- `EMA`
- `WAL`

---

## 6.5 `public.rate_plan_lookup`

Lookup for `rate_plan_code` (reference page → Rate plans tab).

| Column              | Description                     |
| ------------------- | ------------------------------- |
| `rate_plan_code`    | Primary key; FK from fact table |
| `plan_family`       | e.g. Retail, Group, Corporate   |
| `is_commissionable` | Channel economics flag          |

---

## 6.6 `public.market_macro_group_history`

Effective-dated macro group per `market_code`. Join on `stay_date` between
`valid_from` and `valid_to` (null `valid_to` = open-ended).

---

## 6.7 `public.load_manifest`

One row per ETL execution: `dataset_revision`, `scraped_at`, `source_url`, `row_hash`.

---

## 7. Relationship diagram

### Main joins

#### Room type

`reservations_hackathon.space_type = room_type_lookup.space_type`

#### Rate plan

`reservations_hackathon.rate_plan_code = rate_plan_lookup.rate_plan_code`

#### Market segment

`reservations_hackathon.market_code = market_code_lookup.market_code`

#### Market macro group (effective)

`market_macro_group_history.market_code = reservations_hackathon.market_code`
and `stay_date` overlaps `[valid_from, valid_to)`

#### Channel

`reservations_hackathon.channel_code = channel_code_lookup.channel_code`

---

## 8. Common pitfalls

## 8.1 Do not confuse rows with reservations

Counting rows is not the same as counting bookings. Think about what the correct approach is.

---

## 8.2 Do not confuse reservations with room nights

A reservation can cover multiple rooms. Make sure your room-night calculation accounts for this.

---

## 8.3 Be careful with cancelled bookings

Think about whether cancelled reservations should be included or excluded depending on the question being asked.

---

## 8.4 Know which date you are using

The dataset has multiple date fields. Make sure you use the right one for the question. Using the wrong date can produce a logically wrong answer even if the SQL runs.

---

## 8.5 Know which revenue field you need

There are two revenue columns in the dataset. Understand what each one represents and choose the right one for the question.

---

## 9. Business definitions and semantic clarity

A strong solution will define business metrics explicitly instead of improvising them every time. Your agent should have clear, consistent definitions for concepts like reservation count, room nights, revenue, ADR, and segment groupings.

How you define and group these is part of the challenge.

---

## 10. Why a semantic layer is a strong idea

Direct natural-language to SQL can be error-prone.

A strong team may create a semantic layer that defines:

- business metrics,
- default filters,
- dimension mappings,
- standard business rules.

This is powerful because it reduces common mistakes like:

- counting rows instead of reservations,
- mixing room revenue and total revenue,
- forgetting cancelled rows,
- confusing stay date and booking date.

A semantic layer is **not required**, but it is a strong differentiator and should score well if implemented clearly.

---

## 11. Example questions

These are the kinds of questions the Revenue Manager agent should handle.

### Examples

- What revenue is on the books by month? (sum `daily_room_revenue` by stay month — see [§8.5](#85-know-which-revenue-field-you-need) for column names)
- Which segments are driving July?
- How much of July is group business?
- Are we too dependent on OTA?
- What changed in the last 7 days for future stays?
- Which room type is generating the highest ADR?
- How much business was cancelled in June?
- What share of our future business is corporate?
- Which companies are contributing the most revenue?
- Is our business concentrated in a few large bookings?

---

## 12. Answer style

A good answer is not just raw SQL output. A weak answer names a single metric. A strong answer explains the drivers, quantifies the key numbers, highlights risks or opportunities, and speaks in language a GM would trust.

Think: what would a sharp revenue manager say in a morning briefing?

---

## 13. Final advice for teams

1. Decide whether the question is about stay date or booking date.
2. Be explicit about whether cancelled reservations are included.
3. Prefer clear business definitions for metrics like bookings, room nights, and revenue.
4. Return answers in plain English, not just raw query output.
5. When there is ambiguity, state your assumption.

---

## 14. Quick reference

### Main fact table

`reservations_hackathon`

### Lookup tables

- `room_type_lookup`
- `rate_plan_lookup`
- `market_code_lookup`
- `market_macro_group_history`
- `channel_code_lookup`
- `load_manifest`

---

## 15. Dataset shape

After a full load from the current data site:

- `room_type_lookup`: 3 rows
- `rate_plan_lookup`: 8 rows
- `market_code_lookup`: 10 rows
- `market_macro_group_history`: 11 rows
- `channel_code_lookup`: 4 rows
- `reservations_hackathon`: reconcile `total_stay_rows` with `/verify` on scrape day
- `load_manifest`: ≥ 1 row per ETL run

Reconcile against `/verify` — do not assume static counts from §3.

---

## Appendix A — OTB composition (default filters)

**Default on-the-books (OTB)** for stay-date analysis:

1. Exclude `reservation_status = 'Cancelled'` unless the question is explicitly about cancellations.
2. Exclude `financial_status = 'Provisional'` unless the question asks for tentative / unposted / “all committed” business including provisional rows.

Posted + non-cancelled is the usual GM briefing universe. State your assumption when a question is ambiguous.

---

## Appendix B — Dates, time zones, and property date

| Field                   | Use for                                                          |
| ----------------------- | ---------------------------------------------------------------- |
| `stay_date`             | Revenue-on-stay, monthly OTB, segment mix by stay month          |
| `create_datetime`       | Pickup, booking pace, “what was booked recently” (UTC storage)   |
| `property_date`         | Hotel business-date attribution when it differs from `stay_date` |
| `cancellation_datetime` | Point-in-time OTB (`get_as_of_otb`)                              |

**Pickup windows (`get_pickup_delta`):** interpret `booking_window_days` using **Europe/London** local midnight as window boundaries, then compare against `create_datetime` in UTC.

**Segment macro groups:** join `market_macro_group_history` on `stay_date` overlapping `[valid_from, valid_to)` — do not use a static `macro_group` from `market_code_lookup` alone when history rows exist (e.g. `PROM` reclassified mid-year on the reference page).

---

## 16. Challenge objective

Build a **Revenue Manager Agent for a Hotel General Manager** that uses reservation data to detect what is changing in future business, turn it into clear commercial judgment, and recommend what action to take next.
