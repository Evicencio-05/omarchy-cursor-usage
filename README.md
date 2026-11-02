# Agents + Cursor for Omarchy

Adds **Cursor** alongside **Claude Code** and **Codex** in Omarchy's native agents panel. Shows the Cursor spending-page meters, billing-cycle reset, tokens by day, and tokens by model.

This is an installable clone of the agents widget shipped with **Omarchy 4.0.4 (Quattro)**, not a separate dashboard. Enabling it replaces the built-in widget in its existing bar position and retains its settings. Claude and Fireworks continue using Omarchy's installed collectors.

Codex uses a bundled wrapper around Omarchy's installed Codex collector. Session scanning, caching and the record format are unchanged; only the limits probe differs. Codex's app-server can leave `account/read` unanswered, and the stock probe then reports "Codex limits unavailable". With no limits and no recent sessions, the panel hides the Codex tab. The wrapper asks only `account/rateLimits/read`, which also returns the plan. If the installed collector is missing, the stock updater handles Codex as before; if it is a version the wrapper does not recognize, the wrapper runs it unmodified.

**DeepSeek** gets its own tab: the live prepaid balance from DeepSeek's `/user/balance` API, plus tokens by day and by model from Claude Code sessions that ran on a `deepseek-*` model through DeepSeek's Anthropic-compatible endpoint. Those sessions write the same `~/.claude/projects` transcripts as the Claude subscription, so a bundled Claude wrapper runs Omarchy's installed Claude collector with `deepseek-*` models filtered out, and the DeepSeek collector runs the same scan keeping only them. Each keeps its own scan cache.

## Install

Requires Omarchy Quattro with the agents widget, Python 3, Bash and jq (already provided by Omarchy), and a signed-in **Cursor desktop app** using an individual subscription.

```sh
omarchy plugin add https://github.com/Darkosxl/omarchy-cursor-usage --enable
```

Cursor's authentication is read from `~/.config/Cursor/User/globalStorage/state.vscdb` in read-only mode. `XDG_CONFIG_HOME` is honored. CLI-only authentication, teams and enterprise plans are not supported by this version. No API key or copied browser cookie is required.

DeepSeek reads `DEEPSEEK_API_KEY`, then `~/.config/deepseek/api_key` (or the file named by `DEEPSEEK_KEY_FILE`). The key is sent only to `https://api.deepseek.com/user/balance`, redirects are refused, and it is never written to the usage record. The API reports only what is left. To get a meter and a spent-of-funded line, add the credits you bought to `~/.config/omarchy/agents/deepseek.json`:

```json
{ "fundedAmount": 10 }
```

Without a key the tab still shows token usage; with neither a key nor DeepSeek transcripts it stays hidden.

## Refresh

Cursor uses exactly the existing panel refresh lifecycle:

| Trigger | Behavior |
| --- | --- |
| Shell starts / widget loads | Collect all enabled providers |
| Every 900 seconds by default | Refresh limits and token history |
| Open the panel | Refresh Cursor limits **and token history**; other providers retain their native `--limits-only` behavior |
| Press `r` or Enter in the panel | `--force`: refresh limits and token statistics |

The bundled updater forwards all arguments to the installed stock updater, adding `--except codex --except claude`, and runs the Cursor, DeepSeek, Codex and Claude collectors alongside it. It honors `--except cursor`, `--except deepseek`, `--except codex`, `--except claude`, explicit provider selections, and the panel's enabled-provider settings. There is no additional timer, service, global command override, or packaged Omarchy file modification.

To change the interval:

```sh
omarchy bar set darkosxl.agents-cursor refreshIntervalSec 900 --json
```

Cursor token history covers the past 30 days; the daily chart shows the last seven local calendar days. Values come from account-wide usage, including other devices, and use Omarchy's account-scope aggregation. Every panel opening fetches fresh Cursor data. The meters use the spending-page names: **Cursor Models · Grok**, **Other Models**, and **Grok Bot**. Grok Bot is the separate weekly allowance. Nonzero usage below 1% displays a decimal or `<0.1%`, never `0%`. A failed request preserves previously collected data and displays an error; a first-ever failure with no usable data may leave the Cursor tab hidden.

## Update and remove

```sh
omarchy plugin update darkosxl.agents-cursor
```

Removal restores the original Omarchy agents widget. Delete the generated Cursor record too, otherwise the original widget can continue displaying its last cached numbers:

```sh
omarchy plugin remove darkosxl.agents-cursor
rm -f "${XDG_STATE_HOME:-$HOME/.local/state}"/omarchy/agents/usage/{cursor,deepseek}.json
omarchy-shell omarchy.agents refresh
```

Only the plugin directory and its generated usage record are removed. Cursor's app, authentication database and conversations are untouched.

## Data access

The collector sends the existing session credential only to `https://cursor.com`, using its dashboard's read-only usage endpoints. Redirects are refused. Credentials are neither printed nor written to the usage record. The generated record contains plan limits, dates and aggregate token counts; it contains no chat text, email address or session token.

The individual dashboard endpoints are not a supported public API and can change. Invalid or unavailable responses produce a status message rather than fabricated usage. Pagination is capped at 10,000 events per refresh; beyond that the collector reports incomplete history and retains previous statistics. Plugins run unsandboxed under your account; review the source before installing.

## Development

```sh
python3 tests/check.py
omarchy plugin validate .
bash -n bin/omarchy-agent-usage-update
```

The Python standard-library checks cover percentage conversion, token totals and caching, pagination, errors, refresh flag routing, and Codex limits against a stand-in app-server that never answers `account/read`. No package installation is needed.

The upstream QML and assets were copied from Omarchy 4.0.4's `shell/plugins/agents`, preserving its MIT license. The integration changes the updater command in `Main.qml`, small-percentage formatting for Cursor in `Panel.qml`, the plugin manifest, and the bundled collectors/tests. See [CHANGES.md](CHANGES.md) for the implementation and validation record. This clone does not automatically receive future changes to Omarchy's stock QML; update the plugin when a compatible release is available.

## License

MIT. Original widget copyright David Heinemeier Hansson; Cursor integration copyright 2026 Darkosxl. See [LICENSE](LICENSE).
