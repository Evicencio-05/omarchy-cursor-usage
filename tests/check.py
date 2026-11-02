#!/usr/bin/python3
"""Run with python3 check.py; no third-party dependencies."""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "bin"
loader = importlib.machinery.SourceFileLoader("cursor_usage", str(ROOT / "omarchy-agent-usage-cursor"))
spec = importlib.util.spec_from_loader(loader.name, loader)
cursor = importlib.util.module_from_spec(spec)
loader.exec_module(cursor)

summary = {"individualUsage": {"plan": {"used": 2000, "limit": 2000, "autoPercentUsed": 7.2, "apiPercentUsed": 3.7, "totalPercentUsed": 6.8}},
           "billingCycleEnd": "2026-10-13T08:15:23Z", "membershipType": "pro"}
values = cursor.limits(summary)
assert [item["title"] for item in values] == [
    "Cursor Models · Grok",
    "Other Models",
]
assert [item["percent"] for item in values] == [7.2 / 100, 3.7 / 100]
assert cursor.limits({"individualUsage": {"plan": {"autoPercentUsed": 0}}})[0]["percent"] == 0
bot = cursor.grok_bot_limit({"usagePercent": 0, "hasNonZeroIncludedLimit": True,
                             "currentPeriodStart": "2026-10-01T00:00:00Z"})
assert bot["title"] == "Grok Bot" and bot["percent"] == 0 and bot["resetsAt"].startswith("2026-10-08")
assert cursor.grok_bot_limit({"usagePercent": 0, "usesPooledEnterpriseAllowance": True}) is None
assert cursor.grok_bot_limit({"includedLimitZero": True, "usagePercent": 0}) is None
assert cursor.grok_bot_limit({}) is None
for bad in (None, {}, {"individualUsage": None}, {"individualUsage": {"plan": []}},
            {"individualUsage": {"plan": {"used": 2000, "limit": 2000}}},
            {"individualUsage": {"plan": {"apiPercentUsed": "nan"}}}):
    try:
        cursor.limits(bad if bad is not None else {})
        raise AssertionError("Malformed limits accepted")
    except cursor.UsageError:
        pass

now = datetime.now().astimezone()
def event(when, model="test-model"):
    return {"timestamp": str(int(when.timestamp() * 1000)), "model": model,
            "tokenUsage": {"inputTokens": 10, "outputTokens": 2, "cacheReadTokens": 20, "cacheWriteTokens": 3}}
stats = cursor.summarize([event(now), event(now - timedelta(days=1)), event(now - timedelta(days=9))], now.date())
assert stats["todayTotalTokens"] == 35
assert stats["recentDays"][-1]["messageCount"] == 35
assert sum(row["messageCount"] for row in stats["recentDays"]) == 70
assert sum(stats["modelUsage"]["test-model"].values()) == 105
assert len(cursor.summarize([], now.date())["recentDays"]) == 7

calls = []
def paged(cookie, path, body):
    calls.append(body["page"])
    return {"usageEventsDisplay": [event(now)], "totalUsageEventsCount": 2}
cursor.request = paged
assert len(cursor.events("", now)) == 2 and calls == [1, 2]

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    cursor.CACHE = home / "cache.json"
    cursor.session_cookie = lambda: "test"
    cursor.request = lambda *args: summary
    cursor.CACHE.write_text(json.dumps(dict(stats, id="cursor")))
    event_calls = []
    def fresh_events(*args):
        event_calls.append(True)
        return [event(now)]
    cursor.events = fresh_events
    result = cursor.collect(limits_only=True)
    assert result["ready"] and event_calls == [True] and result["todayTotalTokens"] == 35
    cursor.events = lambda *args: []
    assert cursor.collect(limits_only=True, force=True)["modelUsage"] == {}
    cursor.request = lambda *args: (_ for _ in ()).throw(cursor.UsageError("offline"))
    result = cursor.collect()
    assert result["usageStatusText"] == "Cursor usage unavailable" and result["modelUsage"] == stats["modelUsage"]
    cursor.CACHE.write_text("broken")
    assert cursor.collect()["ready"] is False

    # Exercise the real wrapper with isolated stand-in executables.
    bindir = home / "plugin/bin"
    stockdir = home / "stock/bin"
    bindir.mkdir(parents=True)
    stockdir.mkdir(parents=True)
    wrapper = bindir / "omarchy-agent-usage-update"
    wrapper.write_text((ROOT / "omarchy-agent-usage-update").read_text())
    collectors = {}
    for agent in ("cursor", "deepseek", "codex", "claude"):
        collectors[agent] = bindir / f"omarchy-agent-usage-{agent}"
        collectors[agent].write_text(f'#!/bin/bash\nprintf "%s\\n" "$@" > "$HOME/{agent}-args"\necho \'{{"id":"{agent}"}}\'\n')
        collectors[agent].chmod(0o755)
    stock = stockdir / "omarchy-agent-usage-update"
    stock.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$HOME/stock-args"\nexit "${STOCK_EXIT:-0}"\n')
    stock.chmod(0o755)
    stock_collectors = [stockdir / f"omarchy-agent-usage-{agent}" for agent in ("codex", "claude")]
    for stock_collector in stock_collectors:
        stock_collector.write_text("#!/bin/bash\n")
        stock_collector.chmod(0o755)
    env = dict(os.environ, HOME=str(home), XDG_STATE_HOME=str(home / "state"), OMARCHY_PATH=str(home / "stock"))
    outputs = {agent: home / f"state/omarchy/agents/usage/{agent}.json" for agent in collectors}
    everyone = set(collectors)
    for args, wanted in (([], everyone), (["--force"], everyone),
                         (["--limits-only", "cursor"], {"cursor"}), (["--except", "cursor"], everyone - {"cursor"}),
                         (["codex"], {"codex"}), (["--except", "codex"], everyone - {"codex"}),
                         (["--except", "claude"], everyone - {"claude"}), (["claude"], {"claude"}),
                         (["--except", "deepseek"], everyone - {"deepseek"}), (["deepseek"], {"deepseek"}),
                         (["fireworks"], set())):
        for output in outputs.values():
            output.unlink(missing_ok=True)
        subprocess.run(["bash", str(wrapper), *args], env=env, check=True)
        assert (home / "stock-args").read_text().strip().splitlines() == args + ["--except", "codex", "--except", "claude"]
        for agent, output in outputs.items():
            assert output.exists() == (agent in wanted), (args, agent)
            if agent in wanted:
                assert json.loads(output.read_text())["id"] == agent
                assert (home / f"{agent}-args").read_text().strip().splitlines() == [a for a in args if a in ("--force", "--limits-only")]
    assert subprocess.run(["bash", str(wrapper), "fireworks"], env=dict(env, STOCK_EXIT="1")).returncode == 1
    output = outputs["cursor"]
    output.write_text('{"id":"cursor","previous":true}')
    collectors["cursor"].write_text('#!/bin/bash\necho invalid\n')
    assert subprocess.run(["bash", str(wrapper), "cursor"], env=env).returncode == 1
    assert json.loads(output.read_text())["previous"] is True
    # A Codex record from the Cursor collector, or vice versa, is rejected.
    collectors["codex"].write_text('#!/bin/bash\necho \'{"id":"cursor"}\'\n')
    outputs["codex"].unlink(missing_ok=True)
    assert subprocess.run(["bash", str(wrapper), "codex"], env=env).returncode == 1
    assert not outputs["codex"].exists()

    # Without stock Codex and Claude collectors the stock updater keeps every agent.
    for stock_collector in stock_collectors:
        stock_collector.unlink()
    outputs["claude"].unlink(missing_ok=True)
    subprocess.run(["bash", str(wrapper), "claude"], env=env, check=True)
    assert (home / "stock-args").read_text().strip().splitlines() == ["claude"]
    assert not outputs["claude"].exists()

# The Codex limits probe must not wait on account/read, which can go unanswered.
installed = Path(os.environ.get("OMARCHY_PATH") or "/usr/share/omarchy") / "bin/omarchy-agent-usage-codex"
if installed.exists():
    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / "codex"
        fake.write_text("""#!/usr/bin/python3
import json, sys
for line in sys.stdin:
    message = json.loads(line)
    if message.get("method") == "initialize":
        reply = {}
    elif message.get("method") == "account/rateLimits/read":
        reply = {"rateLimits": {"planType": "plus", "primary": {"usedPercent": 25, "windowDurationMins": 300, "resetsAt": 1793566409},
                                "secondary": {"usedPercent": 50, "windowDurationMins": 10080, "resetsAt": 1794153209}}}
    else:
        continue
    print(json.dumps({"id": message["id"], "result": reply}), flush=True)
""")
        fake.chmod(0o755)
        saved_path = os.environ["PATH"]
        os.environ["PATH"] = tmp + os.pathsep + saved_path
        try:
            loader = importlib.machinery.SourceFileLoader("codex_usage", str(ROOT / "omarchy-agent-usage-codex"))
            spec = importlib.util.spec_from_loader(loader.name, loader)
            codex = importlib.util.module_from_spec(spec)
            loader.exec_module(codex)
            codex.STOCK = installed
            result = codex.rate_limits(codex.load_stock())
        finally:
            os.environ["PATH"] = saved_path
        assert result["tierLabel"] == "plus" and result["usageStatusText"] == "", result
        assert [(limit["label"], limit["percent"]) for limit in result["limits"]] == [("5h window", 0.25), ("Weekly (7-day)", 0.5)]

# DeepSeek: balance ledger, key lookup, and the transcript split with Claude.
sys.path.insert(0, str(ROOT))
loader = importlib.machinery.SourceFileLoader("deepseek_usage", str(ROOT / "omarchy-agent-usage-deepseek"))
spec = importlib.util.spec_from_loader(loader.name, loader)
deepseek = importlib.util.module_from_spec(spec)
loader.exec_module(deepseek)
import claude_stock

ledger = {"is_available": True, "balance_infos": [
    {"currency": "CNY", "total_balance": "0.00"},
    {"currency": "USD", "total_balance": "4.95", "granted_balance": "0.00", "topped_up_balance": "4.95"}]}
assert deepseek.balance(ledger) == {"remaining": 4.95, "funded": 0.0, "spent": 0.0, "currency": "USD", "estimated": False}
funded = deepseek.balance(ledger, deepseek.Decimal("10"))
assert funded["funded"] == 10.0 and abs(funded["spent"] - 5.05) < 1e-9
for bad in ({}, {"balance_infos": []}, {"balance_infos": [{"total_balance": "nan"}]}, {"balance_infos": [{"total_balance": "-1"}]}):
    try:
        deepseek.balance(bad)
        raise AssertionError("Malformed balance accepted")
    except deepseek.UsageError:
        pass

with tempfile.TemporaryDirectory() as tmp:
    saved_env = os.environ.pop("DEEPSEEK_API_KEY", None)
    try:
        deepseek.KEY_FILE = Path(tmp) / "api_key"
        try:
            deepseek.api_key()
            raise AssertionError("Missing key accepted")
        except deepseek.UsageError:
            pass
        deepseek.KEY_FILE.write_text(" sk-file\n")
        assert deepseek.api_key() == "sk-file"
        os.environ["DEEPSEEK_API_KEY"] = "sk-env"
        assert deepseek.api_key() == "sk-env"
    finally:
        os.environ.pop("DEEPSEEK_API_KEY", None)
        if saved_env is not None:
            os.environ["DEEPSEEK_API_KEY"] = saved_env

    deepseek.SETTINGS = Path(tmp) / "deepseek.json"
    assert deepseek.funded_amount() is None
    deepseek.SETTINGS.write_text('{"fundedAmount": 20}')
    assert deepseek.funded_amount() == 20

    deepseek.api_key = lambda: "sk-test"
    deepseek.stats = lambda *args: {"totalPrompts": 3, "todayTotalTokens": 9}
    deepseek.fetch_balance = lambda key: dict(ledger, is_available=False)
    result = deepseek.collect()
    assert result["ready"] and result["balance"]["funded"] == 20 and result["todayTotalTokens"] == 9
    assert result["usageStatusText"] == "Balance too low for API calls"
    deepseek.fetch_balance = lambda key: (_ for _ in ()).throw(deepseek.UsageError("offline"))
    result = deepseek.collect()
    assert result["ready"] and "balance" not in result and result["authHelpText"] == "offline"
    deepseek.stats = lambda *args: {}
    assert deepseek.collect()["ready"] is False

if claude_stock.STOCK.exists():
    with tempfile.TemporaryDirectory() as tmp:
        projects = Path(tmp) / "projects/demo"
        projects.mkdir(parents=True)
        stamp = datetime.now().astimezone().isoformat()
        lines = [{"type": "assistant", "sessionId": "s", "timestamp": stamp,
                  "message": {"id": f"m{n}", "role": "assistant", "model": model, "usage": {"input_tokens": n, "output_tokens": 1}}}
                 for n, model in ((10, "claude-opus-5-5"), (20, "deepseek-flash"), (30, "DeepSeek-V4"))]
        (projects / "session.jsonl").write_text("".join(json.dumps(line) + "\n" for line in lines))
        split = {}
        for name, keep in (("claude", lambda model: not claude_stock.is_deepseek(model)), ("deepseek", claude_stock.is_deepseek)):
            stock = claude_stock.load(keep, "check-" + name)
            split[name] = stock.scan_projects(projects.parent)
            assert stock.scan_cache_paths(projects.parent)[0].name.endswith(f"-check-{name}.json")
            assert stock.json is json
        assert set(split["claude"]["modelUsage"]) == {"claude-opus-5-5"} and split["claude"]["todayTotalTokens"] == 11
        assert set(split["deepseek"]["modelUsage"]) == {"deepseek-flash", "DeepSeek-V4"}
        assert split["deepseek"]["todayTotalTokens"] == 52 and split["deepseek"]["totalPrompts"] == 2

print("PASS: limits, token totals, pagination, cache/failure handling, Codex limits, DeepSeek balance and transcript split, refresh flag routing")
