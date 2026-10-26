#!/usr/bin/env python3
"""
Crypto programming task collector (public endpoints only, no API keys).

Fetches open programming-related tasks paid in crypto / USD-stablecoins,
prefers rewards up to 50 USD, writes tasks.txt next to this script.

Sources (no authentication required):
  - Superteam Earn public listings API
  - GitHub Issues Search API (unauthenticated, rate-limited)
  - Bounty Radar public JSON (optional security-program index)

Dependencies: requests
  pip install requests
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    raise SystemExit("Missing dependency. Install with: pip install requests")

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = SCRIPT_DIR / "tasks.txt"

MAX_REWARD_USD = 50.0
MAX_TASKS = 80
REQUEST_TIMEOUT = 20
USER_AGENT = "CryptoTaskParser/1.0 (portfolio; public data only)"

# Keywords that suggest programming / software work
PROG_HINTS = (
    "code", "python", "javascript", "typescript", "rust", "go ", "golang",
    "script", "api", "backend", "frontend", "bug", "fix", "test", "pytest",
    "docs", "readme", "cli", "sdk", "library", "refactor", "implement",
    "feature", "endpoint", "github", "pr ", "pull request", "solidity",
    "smart contract", "web3", "dev", "developer", "programming", "software",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_reward_usd(text: str) -> float:
    """Best-effort parse of a dollar / stablecoin amount from free text."""
    if not text:
        return 0.0
    lowered = text.lower()
    patterns = [
        r"\$\s*([\d.,]+)",
        r"([\d.,]+)\s*usdc?\b",
        r"([\d.,]+)\s*usdt?\b",
        r"([\d.,]+)\s*usd\b",
        r"worker price:\s*\$?\s*([\d.,]+)",
        r"/bounty\s+\$?\s*([\d.,]+)",
        r"reward[:\s]+\$?\s*([\d.,]+)",
        r"bounty\s+\$?\s*([\d.,]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        try:
            value = float(match.group(1).replace(",", ""))
            if 0 < value < 1_000_000:
                return value
        except ValueError:
            continue
    return 0.0


def looks_like_programming(title: str, body: str = "") -> bool:
    """Lightweight filter: title/body mention common programming terms."""
    blob = f"{title} {body}".lower()
    return any(hint in blob for hint in PROG_HINTS)


def sort_tasks(tasks: list) -> list:
    """Prefer known rewards <= MAX_REWARD_USD, then unknown, then higher."""
    low = [t for t in tasks if 0 < t["reward_usd"] <= MAX_REWARD_USD]
    unknown = [t for t in tasks if t["reward_usd"] <= 0]
    high = [t for t in tasks if t["reward_usd"] > MAX_REWARD_USD]
    low.sort(key=lambda t: t["reward_usd"])
    high.sort(key=lambda t: t["reward_usd"])
    return (low + unknown + high)[:MAX_TASKS]


# ---------------------------------------------------------------------------
# Sources (public, no keys)
# ---------------------------------------------------------------------------

def fetch_superteam() -> list:
    """Superteam Earn public bounty listings."""
    url = "https://earn.superteam.fun/api/listings"
    params = {
        "type": "bounty",
        "isWinnersAnnounced": "false",
        "take": 40,
    }
    headers = {"User-Agent": USER_AGENT}
    results = []
    try:
        response = requests.get(
            url, params=params, headers=headers, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            data = data.get("listings") or data.get("data") or []
        for item in data:
            title = item.get("title") or "Untitled"
            reward = float(item.get("rewardAmount") or 0)
            token = (item.get("token") or "USDC").upper()
            reward_usd = reward if token in ("USDC", "USDG", "USDT", "USD") else reward
            slug = item.get("slug") or ""
            link = f"https://earn.superteam.fun/listing/{slug}" if slug else ""
            results.append({
                "source": "Superteam Earn",
                "title": title,
                "reward_usd": reward_usd,
                "reward_text": f"{reward} {token}",
                "url": link,
                "notes": "",
            })
    except Exception as exc:
        print(f"[Superteam] skipped: {exc}")
    return results


def fetch_github() -> list:
    """GitHub issue search (unauthenticated). No token required."""
    queries = [
        "label:bounty state:open is:issue",
        'label:"💎 Bounty" state:open is:issue',
        "label:bounty language:Python state:open is:issue",
        "label:bounty documentation state:open is:issue",
        "label:bounty test state:open is:issue",
        '"/bounty" state:open is:issue',
        "frantic bounty state:open is:issue",
    ]
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": USER_AGENT,
    }
    results = []
    seen = set()

    for query in queries:
        if len(results) >= 60:
            break
        try:
            response = requests.get(
                "https://api.github.com/search/issues",
                params={"q": query, "per_page": 20, "sort": "updated"},
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            if response.status_code == 403:
                print("[GitHub] rate limit reached (no token). Stopping extra queries.")
                break
            response.raise_for_status()
            payload = response.json()
            for item in payload.get("items", []):
                html_url = item.get("html_url") or ""
                if not html_url or html_url in seen:
                    continue
                seen.add(html_url)
                title = item.get("title") or ""
                body = item.get("body") or ""
                reward = extract_reward_usd(f"{title}\n{body}")
                if not looks_like_programming(title, body) and reward <= 0:
                    continue
                results.append({
                    "source": "GitHub",
                    "title": title,
                    "reward_usd": reward,
                    "reward_text": f"~${reward:.0f}" if reward else "amount not stated",
                    "url": html_url,
                    "notes": (body or "")[:400].replace("\r", ""),
                })
            time.sleep(0.7)
        except Exception as exc:
            print(f"[GitHub] skipped query: {exc}")
    return results


def fetch_bounty_radar() -> list:
    """Optional free JSON index of security bounty programs."""
    urls = [
        "https://agent.zbang.net/radar/data.json",
        "https://raw.githubusercontent.com/ofirbaranesad-agent/bounty-radar/master/data/latest.json",
    ]
    results = []
    for url in urls:
        try:
            response = requests.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            items = data if isinstance(data, list) else (
                data.get("programs") or data.get("data") or []
            )
            for item in items[:15]:
                if not isinstance(item, dict):
                    continue
                name = (
                    item.get("name")
                    or item.get("project")
                    or item.get("title")
                    or "Program"
                )
                raw = (
                    item.get("maxBounty")
                    or item.get("max_bounty")
                    or item.get("bounty")
                    or 0
                )
                try:
                    max_bounty = float(str(raw).replace(",", "").replace("$", ""))
                except ValueError:
                    max_bounty = 0.0
                link = item.get("url") or item.get("link") or item.get("immunefi") or ""
                results.append({
                    "source": "Bounty Radar",
                    "title": f"Bug bounty program: {name}",
                    "reward_usd": max_bounty,
                    "reward_text": (
                        f"up to ${max_bounty:.0f}" if max_bounty else "amount not stated"
                    ),
                    "url": link or "https://immunefi.com",
                    "notes": "Security / vulnerability program index entry.",
                })
            if results:
                break
        except Exception as exc:
            print(f"[Bounty Radar] skipped: {exc}")
    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_tasks_file(tasks: list) -> None:
    """Always write tasks.txt next to this script."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "=" * 64,
        "CRYPTO PROGRAMMING TASKS",
        f"Generated: {now}",
        f"Reward priority: up to ${MAX_REWARD_USD:.0f}",
        "Language: original (no translation)",
        "Auth: none (public endpoints only)",
        "=" * 64,
        "",
    ]

    if not tasks:
        lines.append("No tasks found.")
    else:
        for index, task in enumerate(tasks, 1):
            tag = ""
            if 0 < task["reward_usd"] <= MAX_REWARD_USD:
                tag = f" [<=${MAX_REWARD_USD:.0f}]"
            lines.append(f"{index}. {task['title']}{tag}")
            lines.append(f"   Source : {task['source']}")
            lines.append(f"   Reward : {task['reward_text']}")
            lines.append(f"   URL    : {task['url']}")
            notes = (task.get("notes") or "").strip()
            if notes:
                notes = re.sub(r"<!--.*?-->", "", notes, flags=re.DOTALL).strip()
                short = notes[:350].replace("\n", " ")
                if len(notes) > 350:
                    short += "..."
                lines.append(f"   Notes  : {short}")
            lines.append("-" * 48)

    lines.append("")
    lines.append(f"Total: {len(tasks)}")
    lines.append(f"Output file: {OUTPUT_FILE}")
    OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    print("Collecting public crypto programming tasks...")
    print(f"Output will be written to: {OUTPUT_FILE}")

    collected = []

    superteam = fetch_superteam()
    print(f"  Superteam Earn : {len(superteam)}")
    collected.extend(superteam)

    github = fetch_github()
    print(f"  GitHub         : {len(github)}")
    collected.extend(github)

    radar = fetch_bounty_radar()
    print(f"  Bounty Radar   : {len(radar)}")
    collected.extend(radar)

    filtered = []
    for task in collected:
        if task["reward_usd"] > 0 or looks_like_programming(
            task["title"], task.get("notes", "")
        ):
            filtered.append(task)
        elif task["source"] == "Superteam Earn":
            filtered.append(task)

    ordered = sort_tasks(filtered)
    write_tasks_file(ordered)

    print(f"Done. Wrote {len(ordered)} tasks to {OUTPUT_FILE.name}")


if __name__ == "__main__":
    main()
