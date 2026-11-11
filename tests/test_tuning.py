from datetime import date

import pytest
import yaml

from nse_agent import DISCLAIMER, config
from nse_agent import tuning
from nse_agent.retrospective import add_months
from tests.test_daily import outputs  # noqa: F401

MOM, MOS = {"momentum": 1.0}, {"margin_of_safety": 1.0}
SWITCH = date(2024, 7, 1)
END = date(2026, 6, 1)


@pytest.fixture
def world(monkeypatch):
    """Momentum wins on windows starting before SWITCH, margin of safety on every later window."""
    days = [add_months(date(2024, 1, 1), k) for k in range(24)]

    def window(snap, a, h, w, universe):
        sign = {tuning.key(MOM): 1, tuning.key(MOS): -1}.get(tuning.key(w), 0) * (1 if a < SWITCH else -1)
        return {"top": [], "top_return": 0.1 + 0.05 * sign, "universe": 0.1, "excess": 0.05 * sign,
                "hit_rate": 0.5, "ic": float(sign)}

    monkeypatch.setattr(tuning.ledger, "read", lambda name: [])
    monkeypatch.setattr(tuning.ledger, "by_date", lambda rows: {d.isoformat(): {} for d in days})
    monkeypatch.setattr(tuning, "grid", lambda: [dict(MOM), dict(MOS)])
    monkeypatch.setattr(tuning, "window", window)
    monkeypatch.setattr(tuning, "_tickers", lambda: [])
    monkeypatch.setattr(tuning, "data_end", lambda: END)


def test_walk_forward_selects_only_from_matured_windows(world):
    res = tuning.compute(END)
    path = {p["date"]: tuning.key(p["weights"]) for p in res["path"]}
    assert min(path) == "2024-09-01"
    # By 2025-03-01 the 3-month windows from Jan to Dec 2024 have ended: 6 favour each side, so the tie keeps the
    # current weights. Margin of safety leads only once the window starting 2025-01-01 has ended.
    assert path["2025-02-01"] == tuning.key(MOM)
    assert path["2025-03-01"] == tuning.key(res["current"])
    assert path["2025-04-01"] == tuning.key(MOS)
    assert res["proposal"] == MOS and res["changed"]
    assert res["results"][12]["tuned"]["ic"] < 0 and not res["recommend"]


def test_run_tuning_never_edits_settings_and_apply_changes_only_weights(world, outputs, tmp_path):
    settings = config.DATA / "settings.yaml"
    before = settings.read_bytes()
    proposal, body = tmp_path / "w.json", tmp_path / "pr.md"
    assert tuning.run_tuning(str(proposal), str(body)).startswith("recommend=False")
    assert settings.read_bytes() == before and not proposal.exists() and not body.exists()
    assert DISCLAIMER in (config.REPORTS / "tuning.md").read_text(encoding="utf-8")

    copy = tmp_path / "settings.yaml"
    copy.write_bytes(before)
    tuning.apply({"margin_of_safety": 0.6, "quality": 0.0, "momentum": 0.4}, copy)
    old, new = yaml.safe_load(before), yaml.safe_load(copy.read_text(encoding="utf-8"))
    assert new["ranking"]["weights"] == {"margin_of_safety": 0.6, "momentum": 0.4}
    assert {k: v for k, v in new.items() if k != "ranking"} == {k: v for k, v in old.items() if k != "ranking"}
    assert len(copy.read_text(encoding="utf-8").splitlines()) == len(before.decode("utf-8").splitlines())


def test_proposal_written_only_when_it_wins_out_of_sample(world, outputs, tmp_path, monkeypatch):
    def window(snap, a, h, w, universe):
        sign = {tuning.key(MOM): -1, tuning.key(MOS): 1}.get(tuning.key(w), 0)
        return {"top": [], "top_return": 0.1, "universe": 0.1, "excess": 0.05 * sign, "hit_rate": 0.5,
                "ic": float(sign)}

    monkeypatch.setattr(tuning, "window", window)
    settings = config.DATA / "settings.yaml"
    before = settings.read_bytes()
    proposal, body = tmp_path / "w.json", tmp_path / "pr.md"
    assert tuning.run_tuning(str(proposal), str(body)).startswith("recommend=True")
    assert yaml.safe_load(proposal.read_text(encoding="utf-8")) == MOS
    assert DISCLAIMER in body.read_text(encoding="utf-8") and settings.read_bytes() == before
