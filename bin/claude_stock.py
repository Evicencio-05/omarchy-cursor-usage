"""Omarchy's Claude collector, loaded with a model filter on its transcript scan.

Claude Code pointed at DeepSeek's Anthropic-compatible endpoint writes the same
~/.claude/projects transcripts as the Claude subscription, told apart only by
the model name. The Claude and DeepSeek collectors both reuse the stock scan
and keep their own side of that split.
"""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path


STOCK = Path(os.environ.get("OMARCHY_PATH") or "/usr/share/omarchy") / "bin/omarchy-agent-usage-claude"
REQUIRED = ("main", "scan_projects", "scan_cache_paths", "cached_scan", "config_dir", "json")


def is_deepseek(model):
    return str(model or "").lower().startswith("deepseek")


class FilteredJson:
    # Stands in for the json module inside scan_projects. An entry whose model
    # is filtered out raises, which the stock loop already skips like any
    # unparseable line; everything else parses as before.
    def __init__(self, keep):
        self.keep = keep

    def loads(self, text):
        entry = json.loads(text)
        if isinstance(entry, dict):
            message = entry.get("message") if isinstance(entry.get("message"), dict) else {}
            if not self.keep(str(message.get("model") or entry.get("model") or "claude")):
                raise ValueError("filtered model")
        return entry

    def __getattr__(self, name):
        return getattr(json, name)


def load(keep, cache_tag):
    loader = importlib.machinery.SourceFileLoader("omarchy_claude_usage_" + cache_tag, str(STOCK))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    stock = importlib.util.module_from_spec(spec)
    loader.exec_module(stock)
    if not all(hasattr(stock, name) for name in REQUIRED):
        raise AttributeError("unsupported stock Claude collector")

    scan_projects = stock.scan_projects
    def filtered_scan(projects_path):
        stock.json = FilteredJson(keep)
        try:
            return scan_projects(projects_path)
        finally:
            stock.json = json
    stock.scan_projects = filtered_scan

    # A filtered summary must not share the stock collector's scan cache.
    scan_cache_paths = stock.scan_cache_paths
    def tagged_cache_paths(projects_path):
        cache, lock = scan_cache_paths(projects_path)
        return (cache.with_name(f"{cache.stem}-{cache_tag}{cache.suffix}"),
                lock.with_name(f"{lock.stem}-{cache_tag}{lock.suffix}"))
    stock.scan_cache_paths = tagged_cache_paths
    return stock
