#!/usr/bin/env python3
"""Refresh lottery-stats.json from public frequency tables.

The updater is deliberately fail-safe: a source-format change never replaces a
previously verified value. Failed games remain unchanged and are reported in the
GitHub Actions log for review.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "lottery-stats.json"

SOURCES = {
    "usa:Powerball": dict(url="https://www.texaslottery.com/export/sites/lottery/Games/Powerball/Number_Frequency.html", main_max=69, main_count=5, special_max=26, special_count=1),
    "usa:Mega Millions": dict(url="https://www.texaslottery.com/export/sites/lottery/Games/Mega_Millions/Number_Frequency.html", main_max=70, main_count=5, special_max=24, special_count=1),
    "korea:Lotto 6/45": dict(url="https://www.dhlottery.co.kr/lt645/selectLt645NoStats.do?srchStrLtEpsd=&srchEndLtEpsd=&srchBnsYn=N", main_max=45, main_count=6, adapter="donghaeng"),
    "europe:EuroMillions": dict(url="https://www.euro-millions.com/statistics", main_max=50, main_count=5, special_max=12, special_count=2),
    "uk:Lotto": dict(url="https://www.beatlottery.co.uk/lotto/statistics", main_max=59, main_count=6),
    "australia:Oz Lotto": dict(url="https://www.ozlotteries.com/oz-lotto/statistics", main_max=47, main_count=7),
    "italy:SuperEnalotto": dict(url="https://www.superenalotto.net/en/statistics", main_max=90, main_count=6),
    "spain:La Primitiva": dict(url="https://www.loteriasyapuestas.es/en/la-primitiva/estadisticas", main_max=49, main_count=6),
}

HEADERS = {"User-Agent": "GoodFortuneStats/1.0 (+https://goodfortune.com; contact@goodfortune.com)"}


def numeric_pairs(frame: pd.DataFrame, number_max: int) -> dict[int, int]:
    """Return the best number→frequency mapping found in one HTML table."""
    best: dict[int, int] = {}
    for a in range(len(frame.columns)):
        for b in range(len(frame.columns)):
            if a == b:
                continue
            nums = pd.to_numeric(frame.iloc[:, a], errors="coerce")
            freqs = pd.to_numeric(frame.iloc[:, b], errors="coerce")
            pairs = {
                int(n): int(f)
                for n, f in zip(nums, freqs)
                if pd.notna(n) and pd.notna(f) and 0 <= int(n) <= number_max and int(f) >= 0
            }
            if len(pairs) > len(best):
                best = pairs
    return best


def choose_table(tables: list[pd.DataFrame], number_max: int, minimum_rows: int) -> dict[int, int]:
    candidates = [numeric_pairs(table, number_max) for table in tables]
    candidates = [item for item in candidates if len(item) >= minimum_rows]
    if not candidates:
        raise ValueError(f"no usable frequency table for 0–{number_max}")
    return max(candidates, key=len)


def refresh_game(config: dict) -> tuple[list[int], dict[str, int], list[int], dict[str, int]]:
    response = requests.get(config["url"], headers=HEADERS, timeout=35)
    response.raise_for_status()
    if config.get("adapter") == "donghaeng":
        rows = response.json()["data"]["result"]
        main_map = {int(row["wnNo"]): int(row["cnt"]) for row in rows}
        if len(main_map) != 45:
            raise ValueError("Donghaeng official frequency response is incomplete")
        ranked_main = sorted(main_map, key=lambda n: (-main_map[n], n))[: config["main_count"]]
        return sorted(ranked_main), {str(n): main_map[n] for n in ranked_main}, [], {}

    # pandas 2.2+ no longer reliably accepts literal HTML strings directly;
    # wrapping the downloaded markup prevents it being treated as a file path.
    tables = pd.read_html(StringIO(response.text))
    main_map = choose_table(tables, config["main_max"], max(config["main_count"] + 2, 10))
    ranked_main = sorted(main_map, key=lambda n: (-main_map[n], n))[: config["main_count"]]

    ranked_special: list[int] = []
    special_counts: dict[str, int] = {}
    if config.get("special_count"):
        candidates = []
        for table in tables:
            mapping = numeric_pairs(table, config["special_max"])
            if config["special_max"] <= len(mapping) <= config["special_max"] + 1:
                candidates.append(mapping)
        if not candidates:
            raise ValueError("special-ball frequency table not found")
        special_map = max(candidates, key=len)
        ranked_special = sorted(special_map, key=lambda n: (-special_map[n], n))[: config["special_count"]]
        special_counts = {str(n): special_map[n] for n in ranked_special}

    return (
        sorted(ranked_main),
        {str(n): main_map[n] for n in ranked_main},
        sorted(ranked_special),
        special_counts,
    )


def main() -> int:
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    failures = []
    changed = 0
    today = datetime.now(timezone.utc).strftime("%B %-d, %Y")

    for key, config in SOURCES.items():
        try:
            main_numbers, main_counts, special_numbers, special_counts = refresh_game(config)
            entry = payload["games"].setdefault(key, {})
            display_date = datetime.now(timezone.utc).strftime("%Y년 %-m월 %-d일") if key == "korea:Lotto 6/45" else today
            entry.update(status="ok", updated=display_date, main=main_numbers, mainCounts=main_counts)
            if config.get("special_count"):
                entry.update(special=special_numbers, specialCounts=special_counts)
            if key == "korea:Lotto 6/45":
                entry["sources"] = [{"label": "동행복권 공식 통계", "url": "https://www.dhlottery.co.kr/lt645/stats"}]
            else:
                entry["sources"] = [{"label": "Public frequency table", "url": config["url"]}]
            changed += 1
            print(f"updated {key}: {main_numbers} {special_numbers}")
        except Exception as exc:  # preserve last verified values
            failures.append(f"{key}: {exc}")
            print(f"preserved {key}: {exc}")

    payload["generatedAt"] = datetime.now(timezone.utc).isoformat()
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"updated {changed}/{len(SOURCES)} configured games")
    if failures:
        print("Source review needed:\n- " + "\n- ".join(failures))
    return 0 if changed else 1


if __name__ == "__main__":
    raise SystemExit(main())
