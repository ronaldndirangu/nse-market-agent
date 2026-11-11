"""Point the package at a throwaway root before it is imported, so tests never touch repo data."""
import os
import shutil
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures"

_ROOT = Path(tempfile.mkdtemp(prefix="nse-agent-test-"))
(_ROOT / "data" / "prices").mkdir(parents=True)
for _name in ("settings.yaml", "macro.yaml", "universe.yaml"):
    shutil.copy(REPO / "data" / _name, _ROOT / "data" / _name)
os.environ["NSE_AGENT_ROOT"] = str(_ROOT)
os.environ["NSE_AGENT_DELAY"] = "0"


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_ROOT, ignore_errors=True)


@pytest.fixture
def root():
    return _ROOT


@pytest.fixture
def fixture_text():
    return lambda name: (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _fresh_caches():
    from nse_agent import dividends, fundamentals, prices

    prices.clear_cache()
    dividends.clear_cache()
    fundamentals._load.cache_clear()
    yield
    prices.clear_cache()
    dividends.clear_cache()
    fundamentals._load.cache_clear()
