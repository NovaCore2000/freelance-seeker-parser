# Crypto Task Parser

Small public-data collector for **programming-related tasks** paid in cryptocurrency or USD-stablecoins (USDC / USDT and similar).

Built for a GitHub portfolio: one folder, **no API keys**, **no translation**, output file always created next to the script.

## Features

- Uses **only public HTTP endpoints** (no personal tokens or keys)
- Focuses on rewards **up to about 50 USD** (higher amounts are listed after)
- Keeps titles and notes in the **original language**
- Writes `tasks.txt` in the **same directory** as `parser.py` on every run

## Folder layout

```text
crypto_task_parser/
├── parser.py      # collector script
├── README.md      # this file
└── tasks.txt      # generated on each run (next to parser.py)
```

## Requirements

- Python 3.8+
- `requests`

```bash
pip install requests
```

## Usage

```bash
cd crypto_task_parser
python parser.py
```

After a successful run, open `tasks.txt` in the same folder.

## Data sources

| Source | Type | Auth | What you get |
|--------|------|------|----------------|
| **Superteam Earn** | Public REST listings | None | Open bounties (often USDC / Solana ecosystem) |
| **GitHub** | Public Search API | None (rate-limited) | Issues labeled `bounty` and related queries |
| **Bounty Radar** | Public JSON index | None | Indexed security / bug-bounty programs |

Unauthenticated GitHub search is limited (about 60 requests per hour). If you hit a rate limit, wait and run again later.

## Output format (`tasks.txt`)

Each entry includes:

- Title (original text)
- Source name
- Reward text / approximate USD when parseable
- URL
- Short notes (when available)

Entries with a detected reward **≤ $50** are marked `[<=$50]` and listed first.

## Limits and honesty

- This is a **collector**, not a payment or claim bot.
- Reward amounts are best-effort parses from public text; always verify on the source page.
- Some listings are tests, already claimed, or not programming work — filter manually.
- No scraping of login-walled pages; no stored credentials.

## License

Use freely for portfolio and personal automation. Respect each platform’s terms of use.
