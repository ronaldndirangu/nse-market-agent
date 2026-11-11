from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(os.environ.get("NSE_AGENT_ROOT", Path(__file__).resolve().parent.parent))
DATA = ROOT / "data"
PRICES_DIR = DATA / "prices"
REPORTS = ROOT / "reports"
SITE = ROOT / "site"

USER_AGENT = "nse-market-agent/0.1 (+https://github.com/ronaldndirangu/nse-market-agent)"


def load_yaml(path: Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@lru_cache(maxsize=None)
def settings() -> dict:
    return load_yaml(DATA / "settings.yaml")


@lru_cache(maxsize=None)
def macro() -> dict:
    return load_yaml(DATA / "macro.yaml")


@lru_cache(maxsize=None)
def universe() -> list[dict]:
    return load_yaml(DATA / "universe.yaml")["stocks"]


def universe_map() -> dict[str, dict]:
    return {s["ticker"]: s for s in universe()}
