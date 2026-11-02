# Implementation record

## 0.1.4

- Added a DeepSeek tab. Its collector reads the live prepaid balance from `https://api.deepseek.com/user/balance` with the key from `DEEPSEEK_API_KEY` or `~/.config/deepseek/api_key`. An optional `fundedAmount` in `~/.config/omarchy/agents/deepseek.json` adds the meter. Token stats come from Claude Code transcripts whose model starts with `deepseek`.
- Added a Claude collector wrapper that excludes those `deepseek-*` transcripts, so DeepSeek tokens no longer count toward the Claude tab. Both collectors load Omarchy's installed Claude collector through `bin/claude_stock.py` and filter its transcript scan by model, each with its own cache file. With a stock Claude collector the wrapper does not recognize, it runs the stock collector unmodified.
- CNY balances display with `¥`. The DeepSeek mark comes from the MIT-licensed LobeHub icon set.
- Live check on 2026-11-02: the DeepSeek record showed a $4.95 balance and `deepseek-flash` tokens; the Claude record kept its limits and no longer listed `deepseek-flash`.

## 0.1.3

- Added a Codex collector wrapper. Codex 0.166's app-server intermittently left `account/read` unanswered, so the stock collector reported "Codex limits unavailable" (4 of 5, then 2 of 3, back-to-back runs on 2026-11-01). A record with no limits and no recent sessions hid the Codex tab. The wrapper reuses the installed collector's scanning, caching and record assembly, and reads limits and plan from `account/rateLimits/read` alone. It returned limits on 8 of 8 back-to-back live runs, in about 0.5 s each.
- The updater passes `--except codex` to the stock updater only when an installed Codex collector exists. The Cursor and Codex records are written concurrently through the same validated atomic write.

## 0.1.2

- Added Cursor's cube mark as the tab icon, with light and dark variants matching the Codex icon. The SVG path comes from the MIT-licensed LobeHub icon set.

## 0.1.1

- Replaced the included-spend bar with the meters on Cursor's spending page: Cursor Models · Grok, Other Models, and Grok Bot. The $20 credit cap is no longer shown.

## 0.1.0

- Imported the native agents widget and its SVG assets from Omarchy 4.0.4 with the upstream MIT license.
- Added a Python standard-library Cursor collector. It reads desktop authentication without modifying it, fetches actual plan percentages and paginated token events, and emits the existing agent record format.
- Added an updater that calls Omarchy's installed collector runner and the Cursor collector using the same refresh flags and provider selection rules.
- Connected the existing QML refresh command to the bundled updater. The timer, panel-open behavior, manual refresh, rendering, keyboard interactions and stock collectors are unchanged.
- Declared a root plugin manifest with ID `darkosxl.agents-cursor` and `clonedFrom: omarchy.agents`, preserving native enable/disable restoration behavior.
- Added executable checks and installation, update, privacy and removal documentation.
- Corrected the headline allowance to use included spend / plan limit, matching Cursor's overall usage display; model-pool percentages remain separately labeled. Small nonzero Cursor percentages no longer round to zero.
- Cursor refreshes both limits and token history every time the existing panel-open refresh runs; other providers retain their stock limits-only behavior.

Runtime records and account credentials are outside the repository. `preview.png` is a reviewed capture of the agents panel only.

## Validation

Checked on 2026-10-01 with Omarchy 4.0.4-1.

- `python3 tests/check.py`, `omarchy plugin validate .`, and `bash -n bin/omarchy-agent-usage-update` pass. The checks cover percentage conversion, token totals, pagination, cache and failure handling, and refresh flag routing.
- After `omarchy-shell omarchy.agents refresh` and opening the panel, Cursor showed Included plan 99%, Auto pool 4%, and API pool 4%. The usage record behind that view was about 0.994, 0.0405, and 0.0369. No meter displayed 0%. Every live value was at least 1%, so the panel used ordinary rounding. Nonzero Cursor values below 1% still format as one decimal, or `<0.1%` when they are below a tenth of a percent, in `Panel.qml`.
- Opening the panel runs the bundled updater with `--limits-only`. Cursor still fetches limits and token history on that path; the other providers keep their stock limits-only behavior. A manual refresh (`omarchy-shell omarchy.agents refresh`) collects both as well.
- Removing the plugin restores the stock Omarchy agents widget. Installing again with `omarchy plugin add https://github.com/Darkosxl/omarchy-cursor-usage --enable` put the Cursor tab back in the same bar position. That copy's origin is the public repository, `omarchy plugin update darkosxl.agents-cursor` reported it up to date, and the panel showed Included plan 100%, Auto pool 5%, and API pool 4%, matching the fresh record (1.0, about 0.0537, and about 0.0369).
