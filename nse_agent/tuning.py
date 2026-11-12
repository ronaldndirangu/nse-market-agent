"""Guarded walk-forward weight tuning.

Candidates are a small grid of composite weights. On each reconstructed month start, the tuner picks the candidate
with the best mean rank IC over windows that had fully matured by that date, then scores the pick on windows that
start on that date. Only these out-of-sample windows are reported. The tuner never edits data/settings.yaml on main:
a proposal goes to a pull request for review.
"""
from __future__ import annotations

import re
from datetime import date
from itertools import product
from pathlib import Path
from statistics import fmean

from . import config, ledger, report, storage
from .fmt import pct, table
from .retrospective import TOP, _mean, _tickers, add_months, data_end, fwd, spearman

GRID_SIGNALS = ("margin_of_safety", "quality", "momentum", "dividend_yield")
STEP = 0.1
SELECT_H = 3
EVAL_H = (3, 12)
MIN_TRAIN = 6
MIN_OOS = 24
MIN_IC_GAIN = 0.02
MIN_WIN_SHARE = 0.5
WEIGHTS_LINE = re.compile(r"^(\s*weights:\s*)\{[^}]*\}(.*)$", re.M)


def grid(signals: tuple[str, ...] = GRID_SIGNALS, step: float = STEP) -> list[dict[str, float]]:
    n = round(1 / step)
    return [{s: round(c * step, 4) for s, c in zip(signals, combo)}
            for combo in product(range(n + 1), repeat=len(signals)) if sum(combo) == n]


def key(w: dict[str, float]) -> tuple:
    return tuple(sorted((s, round(v, 4)) for s, v in w.items() if v))


def label(w: dict[str, float]) -> str:
    return ", ".join(f"{s.replace('_', ' ')} {v:g}" for s, v in w.items() if v) or "none"


def composite(row: dict, w: dict[str, float]) -> float:
    return sum(v * (row.get(f"{s}_z") or 0.0) for s, v in w.items())


def window(snap: dict[str, dict], a: date, h: int, w: dict[str, float], universe: list[str]) -> dict | None:
    """Re-rank one stored snapshot with weights `w` and score it over the next `h` months."""
    b = add_months(a, h)
    rets = {t: fwd(t, a, b) for t in snap}
    scored = sorted(((t, composite(snap[t], w)) for t in snap if rets[t] is not None), key=lambda x: (-x[1], x[0]))
    uni = _mean(fwd(t, a, b) for t in universe)
    if len(scored) < TOP or uni is None:
        return None
    top = [t for t, _ in scored[:TOP]]
    top_ret = fmean(rets[t] for t in top)
    return {"top": top, "top_return": top_ret, "universe": uni, "excess": top_ret - uni,
            "hit_rate": sum(rets[t] > uni for t in top) / TOP,
            "ic": spearman([s for _, s in scored], [rets[t] for t, _ in scored])}


def select(perf: dict, train: list[date], cands: list[dict], current: dict) -> int:
    """Best mean IC over the training windows; ties go to the candidate closest to the current weights."""
    def score(i: int) -> tuple:
        ic = _mean((perf.get((d, SELECT_H, i)) or {}).get("ic") for d in train)
        dist = sum(abs(cands[i].get(s, 0.0) - current.get(s, 0.0)) for s in set(cands[i]) | set(current))
        return (ic if ic is not None else float("-inf"), -dist, -i)
    return max(range(len(cands)), key=score)


def _summary(ws: list[dict]) -> dict:
    return {k: _mean(w[k] for w in ws) for k in ("top_return", "universe", "excess", "hit_rate", "ic")} | {"n": len(ws)}


def _win_share(tuned: list[dict], current: list[dict]) -> float | None:
    pairs = [(t["ic"], c["ic"]) for t, c in zip(tuned, current) if t["ic"] is not None and c["ic"] is not None]
    return sum(t > c for t, c in pairs) / len(pairs) if pairs else None


def passes(r: dict) -> bool:
    """One horizon clears the gate: enough windows, a material IC gain, more windows won than not, higher excess."""
    t, c = r["tuned"], r["current"]
    return (t["n"] >= MIN_OOS and t["ic"] is not None and c["ic"] is not None and t["ic"] >= c["ic"] + MIN_IC_GAIN
            and (r["ic_win_share"] or 0) > MIN_WIN_SHARE and t["excess"] is not None and c["excess"] is not None
            and t["excess"] > c["excess"])


def compute(end: date | None = None) -> dict:
    end = end or data_end()
    snaps = {date.fromisoformat(d): s for d, s in ledger.by_date(ledger.read("reconstructed")).items()}
    days = sorted(snaps)
    current = {s: float(v) for s, v in config.settings()["ranking"]["weights"].items() if v}
    cands = grid()
    if key(current) not in {key(c) for c in cands}:
        cands.append(current)
    cur = next(i for i, c in enumerate(cands) if key(c) == key(current))
    universe = _tickers()

    perf: dict[tuple[date, int, int], dict | None] = {}
    for d in days:
        for h in sorted({SELECT_H, *EVAL_H}):
            if add_months(d, h) <= end:
                for i, w in enumerate(cands):
                    perf[(d, h, i)] = window(snaps[d], d, h, w, universe)

    path, oos = [], {h: {"tuned": [], "current": []} for h in EVAL_H}
    for d in days:
        train = [x for x in days if add_months(x, SELECT_H) <= d]
        if len(train) < MIN_TRAIN:
            continue
        i = select(perf, train, cands, current)
        path.append({"date": d.isoformat(), "train": len(train), "weights": cands[i]})
        for h in EVAL_H:
            tuned, base = perf.get((d, h, i)), perf.get((d, h, cur))
            if tuned and base:
                oos[h]["tuned"].append(tuned)
                oos[h]["current"].append(base)

    final_train = [x for x in days if add_months(x, SELECT_H) <= end]
    proposal = cands[select(perf, final_train, cands, current)] if len(final_train) >= MIN_TRAIN else current
    results = {h: {k: _summary(v) for k, v in oos[h].items()}
               | {"ic_win_share": _win_share(oos[h]["tuned"], oos[h]["current"])} for h in EVAL_H}
    better = all(passes(results[h]) for h in EVAL_H)
    return {
        "generated": date.today().isoformat(), "data_end": end.isoformat(),
        "first": days[0].isoformat() if days else None, "dates": len(days), "candidates": len(cands),
        "current": current, "proposal": proposal, "changed": key(proposal) != key(current),
        "recommend": better and key(proposal) != key(current),
        "results": results, "path": path,
    }


def _results_table(res: dict) -> str:
    rows = []
    for h in EVAL_H:
        for name in ("current", "tuned"):
            r = res["results"][h][name]
            won = res["results"][h].get("ic_win_share") if name == "tuned" else None
            rows.append([f"{h}m", "walk-forward" if name == "tuned" else "current weights", r["n"],
                         pct(r["top_return"]), pct(r["universe"]), pct(r["excess"]), pct(r["hit_rate"], 0),
                         "n/a" if r["ic"] is None else f"{r['ic']:+.3f}", "" if won is None else pct(won, 0)])
    return table(["Horizon", "Weights", "Windows", "Top 5", "Universe (EW)", "Excess", "Hit rate", "Rank IC",
                  "Windows won on IC"], rows)


GATE = (f"at every evaluated horizon, walk-forward selection must have at least {MIN_OOS} out-of-sample windows, "
        f"beat the current weights' mean rank IC by at least {MIN_IC_GAIN:.2f}, win on IC in more than "
        f"{MIN_WIN_SHARE:.0%} of windows, and earn a higher top-5 excess return")


def verdict(res: dict) -> str:
    if not res["changed"]:
        return "Keep the current weights: the tuner selects them on all matured data."
    if res["recommend"]:
        return (f"Proposed weights: {label(res['proposal'])}. Walk-forward selection cleared the review gate: "
                f"{GATE}.")
    return (f"Keep the current weights. The tuner would pick {label(res['proposal'])} on all matured data, but "
            f"the evidence does not clear the review gate: {GATE}.")


def render(res: dict) -> str:
    changes = [p for k, p in enumerate(res["path"]) if k == 0 or key(p["weights"]) != key(res["path"][k - 1]["weights"])]
    lines = [
        "# Weight tuning", "", report.DISCLAIMER_LINE, "",
        f"Generated {res['generated']}. Prices through {res['data_end']}. {res['dates']} reconstructed month starts "
        f"(first {res['first'] or 'n/a'}), {res['candidates']} candidate weightings.", "",
        f"**{verdict(res)}**", "",
        f"Current weights: {label(res['current'])}. Selected on all matured data: {label(res['proposal'])}.", "",
        "## Method", "",
        f"Candidates split a weight of 1 across {', '.join(s.replace('_', ' ') for s in GRID_SIGNALS)} in steps of "
        f"{STEP:g}, plus the current weights. On each month start, the tuner picks the candidate with the best mean "
        f"{SELECT_H}-month rank IC over windows that had fully ended by that date (at least {MIN_TRAIN}), then ranks "
        "that month's stored point-in-time z-scores with it. Ties go to the candidate closest to the current weights. "
        "Every result below is out of sample: the weights were chosen before the window started.", "",
        "The weights change only through a reviewed pull request, and the tuner proposes one only when it clears "
        f"this gate: {GATE}. Overlapping monthly windows are not independent, so the gate asks for a clear, "
        "consistent gain before a change is worth reviewing.", "",
        "## Out-of-sample results", "", _results_table(res), "",
        "## Weights chosen over time", "",
    ]
    lines += [table(["From", "Training windows", "Weights"],
                    [[p["date"], p["train"], label(p["weights"])] for p in changes]) if changes
              else "Not enough matured windows to tune yet.", ""]
    lines += ["## Limitations", "",
              "- Monthly windows overlap at the 3 and 12-month horizons, so they are not independent observations.",
              "- Point-in-time fundamentals are short until the backfill PRs are merged, so the sample is small and "
              "covers one market regime. Rerun after merging them.",
              "- The universe is 16 stocks; one month's IC is noisy.", ""]
    return "\n".join(lines)


def apply(weights: dict[str, float], path=None) -> None:
    """Rewrite only the ranking weights line in settings.yaml. Used on the review branch, never on main."""
    path = path or config.DATA / "settings.yaml"
    text = path.read_text(encoding="utf-8")
    flow = "{" + ", ".join(f"{s}: {v:g}" for s, v in weights.items() if v) + "}"
    new, n = WEIGHTS_LINE.subn(lambda m: m.group(1) + flow + m.group(2), text, count=1)
    if n != 1:
        raise ValueError("ranking weights line not found in settings.yaml")
    path.write_text(new, encoding="utf-8", newline="\n")


def pr_body(res: dict) -> str:
    return "\n".join([
        f"Walk-forward weight tuning proposes new composite weights: **{label(res['proposal'])}** "
        f"(current: {label(res['current'])}).", "",
        "Results are out of sample: on each month start the weights were chosen only from windows that had already "
        f"ended. The proposal cleared this gate: {GATE}.", "", _results_table(res), "",
        "Before merging, check the full report in `reports/tuning.md`, especially the limitations. "
        "Merging changes the ranking for every later brief and report.", "", report.DISCLAIMER_LINE,
    ])


def run_tuning(proposal_file: str | None = None, body_file: str | None = None) -> str:
    res = compute()
    config.REPORTS.mkdir(parents=True, exist_ok=True)
    (config.REPORTS / "tuning.md").write_text(render(res), encoding="utf-8", newline="\n")
    storage.write_json(config.DATA / "tuning.json", {k: v for k, v in res.items() if k != "results"}
                       | {"results": {str(h): v for h, v in res["results"].items()}})
    report.build_site()
    if res["recommend"] and proposal_file:
        storage.write_json(Path(proposal_file), res["proposal"])
    if res["recommend"] and body_file:
        Path(body_file).write_text(pr_body(res), encoding="utf-8", newline="\n")
    r3 = res["results"][SELECT_H]
    return (f"recommend={res['recommend']} proposal=\"{label(res['proposal'])}\" "
            f"oos_windows_{SELECT_H}m={r3['tuned']['n']}")
