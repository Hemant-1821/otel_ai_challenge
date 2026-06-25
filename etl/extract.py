"""
Phase 1 — Extract

Scrapes the data site using Playwright, intercepting Next.js server-action
POST responses (text/x-component) to get structured JSON directly.

RSC wire format (two lines):
  0:{"a":"$@1","f":"","b":"..."}   ← metadata, ignored
  1:{...actual payload...}         ← data we want

Public entry points:
  run_extract()               → full extract, writes raw/ + SCRAPE_MANIFEST
  scrape_reservations()       → list-only  (creates its own browser)
  scrape_reservation_detail() → single ID  (creates its own browser)
  scrape_reference()          → not yet implemented
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from playwright.async_api import Browser, Page, async_playwright

BASE_URL = "https://otel-hackathon-data-site.vercel.app"
RAW_DIR = Path(__file__).parent / "raw"
MANIFEST_PATH = Path(__file__).parent / "SCRAPE_MANIFEST.json"

_NEXT_BTN = '[data-testid="next-page"]'
_DETAIL_DELAY_MS = 200  # polite pause between consecutive detail requests


# ── RSC helpers ──────────────────────────────────────────────────────────────

def _parse_rsc(body: str) -> dict:
    """
    Extract the data payload from a Next.js RSC wire-format response.
    Scans for the line starting with '1:' and JSON-parses its content.
    """
    for line in body.splitlines():
        if line.startswith("1:"):
            return json.loads(line[2:])
    raise ValueError(f"No chunk '1:' found in RSC body:\n{body[:300]}")


async def _intercept_action_response(page: Page, trigger) -> str:
    """
    Intercept the Next.js server-action POST using page.route().

    route.fetch() buffers the full response body inside our handler before
    Chrome can evict it from its CDP cache — this eliminates the intermittent
    'No data found for resource with given identifier' error that occurs when
    reading response.body() via page.on('response') after a subsequent navigation.
    """
    body_future: asyncio.Future[str] = asyncio.get_event_loop().create_future()

    async def handle_route(route) -> None:
        if route.request.method == "POST" and not body_future.done():
            try:
                response = await route.fetch()
                raw = await response.body()
                body_future.set_result(raw.decode("utf-8", errors="replace"))
                await route.fulfill(response=response)
            except Exception as exc:
                if not body_future.done():
                    body_future.set_exception(exc)
                await route.continue_()
        else:
            await route.continue_()

    await page.route("**", handle_route)
    try:
        await trigger()
        return await asyncio.wait_for(body_future, timeout=30.0)
    finally:
        await page.unroute("**", handle_route)


# ── List-page scraper ────────────────────────────────────────────────────────

async def _scrape_list_pages(page: Page) -> tuple[list[dict], int]:
    """
    Paginate through all /reservations list pages by intercepting the
    server-action POST that fires on each page load / Next click.

    Returns (all_items, total_pages) where each item is a reservation
    summary dict (no stay_rows — those come from the detail page).
    """
    all_items: list[dict] = []

    print(f"[list] → {BASE_URL}/reservations")

    # Page 1: POST fires automatically on page load
    body = await _intercept_action_response(
        page,
        lambda: page.goto(f"{BASE_URL}/reservations", wait_until="domcontentloaded"),
    )

    payload = _parse_rsc(body)
    total_pages = payload["totalPages"]
    total_items = payload["totalItems"]
    all_items.extend(payload["items"])
    print(
        f"  page  1/{total_pages}: {len(payload['items']):>3} items"
        f"  (server reports {total_items} total)"
    )

    # Pages 2..N: click Next, intercept the resulting POST
    for page_num in range(2, total_pages + 1):
        next_btn = page.locator(_NEXT_BTN)
        body = await _intercept_action_response(page, next_btn.click)
        payload = _parse_rsc(body)
        all_items.extend(payload["items"])
        print(f"  page {page_num:>2}/{total_pages}: {len(payload['items']):>3} items")

    return all_items, total_pages


# ── Detail-page scraper ──────────────────────────────────────────────────────

async def _scrape_detail_page(page: Page, reservation_id: str, retries: int = 3) -> dict:
    """
    Navigate to /reservations/<id>.  The page load fires a single server-action
    POST with body ["<id>"].  Intercept it and return the parsed payload, which
    includes all reservation header fields plus stay_rows[].

    Retries up to `retries` times with a 1-second delay on transient
    'No data found for resource' errors.
    """
    url = f"{BASE_URL}/reservations/{reservation_id}"
    last_exc: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            body = await _intercept_action_response(
                page,
                lambda: page.goto(url, wait_until="domcontentloaded"),
            )
            return _parse_rsc(body)
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                print(f"  [retry {attempt}/{retries-1}] {reservation_id}: {exc}")
                await asyncio.sleep(1.0)

    raise last_exc


# ── Reference-page scraper ───────────────────────────────────────────────────

async def _extract_table_by_testid(page: Page, testid: str) -> list[dict]:
    """
    Extract a table identified by data-testid as a list of row dicts.
    Keys are taken from <thead th> text; values from <tbody td> text.
    """
    await page.wait_for_selector(f'[data-testid="{testid}"]', timeout=10_000)
    return await page.evaluate(
        """(testid) => {
            const table = document.querySelector(`[data-testid="${testid}"]`);
            const headers = [...table.querySelectorAll("thead th")]
                .map(th => th.textContent.trim());
            return [...table.querySelectorAll("tbody tr")].map(tr => {
                const cells = [...tr.querySelectorAll("td")]
                    .map(td => td.innerText.trim());
                const row = {};
                headers.forEach((h, i) => { row[h] = cells[i] ?? null; });
                return row;
            });
        }""",
        testid,
    )


async def _scrape_reference_page(page: Page) -> dict:
    url = f"{BASE_URL}/reference"
    print(f"[ref]  → {url}")
    await page.goto(url, wait_until="domcontentloaded")

    room_type_lookup = await _extract_table_by_testid(page, "room-type-lookup")
    print(f"[ref]  room_type_lookup: {len(room_type_lookup)} rows")

    await page.get_by_role("tab", name="Markets").click()
    market_code_lookup = await _extract_table_by_testid(page, "market-code-lookup")
    print(f"[ref]  market_code_lookup: {len(market_code_lookup)} rows")

    await page.get_by_role("tab", name="Channels").click()
    channel_code_lookup = await _extract_table_by_testid(page, "channel-code-lookup")
    print(f"[ref]  channel_code_lookup: {len(channel_code_lookup)} rows")

    await page.get_by_role("tab", name="Rate plans").click()
    rate_plan_lookup = await _extract_table_by_testid(page, "rate-plan-lookup")
    print(f"[ref]  rate_plan_lookup: {len(rate_plan_lookup)} rows")

    await page.get_by_role("tab", name="Macro history").click()
    # valid_to = "—" (em dash) means open-ended; transform.py maps it to NULL
    market_macro_group_history = await _extract_table_by_testid(page, "market-macro-history")
    print(f"[ref]  market_macro_group_history: {len(market_macro_group_history)} rows")

    return {
        "room_type_lookup": room_type_lookup,
        "market_code_lookup": market_code_lookup,
        "channel_code_lookup": channel_code_lookup,
        "rate_plan_lookup": rate_plan_lookup,
        "market_macro_group_history": market_macro_group_history,
    }


# ── Manifest ─────────────────────────────────────────────────────────────────

def _build_manifest(reservation_ids: list[str], pages_scraped: int) -> dict:
    sorted_ids = sorted(reservation_ids)
    sha = hashlib.sha256("\n".join(sorted_ids).encode()).hexdigest()
    return {
        "anchor_date": date.today().isoformat(),
        "pages_scraped": pages_scraped,
        "reservation_ids_count": len(sorted_ids),
        "reservation_ids_sha256": sha,
    }


# ── Public API ────────────────────────────────────────────────────────────────

async def scrape_reservations() -> list[dict]:
    """
    Standalone: scrape the reservation list across all pages.
    Returns list of summary dicts (fields from the list API, no stay_rows).
    """
    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        items, _ = await _scrape_list_pages(page)
        await browser.close()
    return items


async def scrape_reservation_detail(reservation_id: str) -> dict:
    """
    Standalone: scrape one reservation detail page.
    Returns the full payload including stay_rows[].
    """
    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        detail = await _scrape_detail_page(page, reservation_id)
        await browser.close()
    return detail


async def scrape_reference() -> dict:
    raise NotImplementedError("Reference page scraping not yet implemented")


async def run_extract() -> dict:
    """
    Full extract using a single shared browser.

    Writes:
      etl/raw/list_items.json      — reservation summaries from list API
      etl/raw/details.json         — full detail payloads (with stay_rows)
      etl/raw/reference.json       — all 5 reference lookup tables
      etl/SCRAPE_MANIFEST.json     — manifest for verification

    Returns bundle dict with keys:
      list_items       list[dict]   — summary rows from list pages
      details          list[dict]   — full detail rows (one per reservation)
      reference        dict         — room_type_lookup, market_code_lookup,
                                      channel_code_lookup, rate_plan_lookup,
                                      market_macro_group_history
      manifest         dict
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(headless=True)
        page: Page = await browser.new_page()

        # ── 1. List pages ─────────────────────────────────────────────────
        list_items, total_pages = await _scrape_list_pages(page)
        reservation_ids = [item["reservation_id"] for item in list_items]
        print(f"\n[list] {len(reservation_ids)} reservations across {total_pages} page(s)")

        p = RAW_DIR / "list_items.json"
        p.write_text(json.dumps(list_items, indent=2))
        print(f"[list] saved → {p.name}")

        # ── 2. Manifest ───────────────────────────────────────────────────
        manifest = _build_manifest(reservation_ids, total_pages)
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
        print(f"[manifest] count={manifest['reservation_ids_count']}  sha256={manifest['reservation_ids_sha256']}")

        # ── 3. Detail pages ───────────────────────────────────────────────
        print(f"\n[detail] scraping {len(reservation_ids)} detail pages …")
        details: list[dict] = []

        for i, rid in enumerate(reservation_ids, 1):
            detail = await _scrape_detail_page(page, rid)
            details.append(detail)
            if i % 25 == 0 or i == len(reservation_ids):
                nights = len(detail.get("stay_rows", []))
                print(f"  {i:>4}/{len(reservation_ids)}: {rid}  ({nights} night row(s))")
            await asyncio.sleep(_DETAIL_DELAY_MS / 1000)

        p = RAW_DIR / "details.json"
        p.write_text(json.dumps(details, indent=2))
        print(f"[detail] saved → {p.name}")

        # ── 4. Reference page ─────────────────────────────────────────────
        reference = await _scrape_reference_page(page)
        p = RAW_DIR / "reference.json"
        p.write_text(json.dumps(reference, indent=2))
        print(f"[ref]  saved → {p.name}")

        await browser.close()

    print("\n✓ Extract complete.")
    return {
        "list_items": list_items,
        "details": details,
        "reference": reference,
        "manifest": manifest,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(run_extract())
