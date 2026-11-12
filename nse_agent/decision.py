"""Consumer explanations of existing entry rules, separate from the research score."""
from __future__ import annotations

from . import config
from .fmt import estimate_reliable, kes, pct
from .valuation import MODEL_NAMES, cushion_price

TIER_ORDER = {"Buy": 0, "Watch": 1, "Avoid": 2}


def display_order(row: dict) -> tuple:
    return TIER_ORDER.get(row.get("tier"), 3), row.get("rank", 999), row["ticker"]


def explain(row: dict, hurdle: float) -> dict:
    settings = config.settings()["valuation"]
    threshold = settings["mos_threshold"]
    models, quality = row["models"], row["quality"]
    projection = row.get("projection") or {}
    reliable = estimate_reliable(row)
    value_pass = reliable and len(row["agree"]) >= row["agree_needed"]
    base = projection.get("base")
    return_pass = base is not None and base > hurdle
    years = projection.get("years", settings["horizon_years"])
    agreement = (f"{len(row['agree'])} of {len(models)} methods estimate at least {pct(threshold, 0)} upside; "
                 f"{row['agree_needed']} must agree. This cushion allows for errors in the estimates.")
    returns = (f"The middle case is {pct(base)} a year over {years} years, "
               f"{'above' if return_pass else 'at or below'} the {pct(hurdle, 2)} return hurdle."
               if reliable and base is not None else "The projected return cannot be assessed reliably.")
    checks = [
        {"name": "Trading and data screen", "passed": not row["screen_fail"],
         "detail": "; ".join(row["screen_fail"]) or "Price age, trading activity, history and earnings checks pass."},
        {"name": "Business health", "passed": quality["gate"] == "pass",
         "detail": ("The entry health check passes; stricter checks are separate." if quality["gate"] == "pass"
                    else "; ".join(quality["fails"]) or "Business health inputs are incomplete.")},
        {"name": "Valuation cushion", "passed": value_pass,
         "detail": agreement if reliable else "There are too few estimates or they disagree too widely."},
        {"name": "Return hurdle", "passed": return_pass if reliable else None, "detail": returns},
    ]
    if row["screen_fail"]:
        reason = "Trading or data check failed"
    elif not reliable:
        reason = "Cannot value reliably"
    elif quality["gate"] != "pass":
        reason = "Business health check failed" if quality["gate"] == "fail" else "Business health unassessed"
    elif not value_pass:
        reason = "Price above the middle estimate" if row["mos"] < 0 else "Insufficient valuation cushion"
    elif not return_pass:
        reason = "Projected return below the hurdle"
    else:
        reason = "Meets the Buy rules"
    why = [c["detail"] for c in checks if c["passed"] is False]
    if not reliable:
        why.insert(0, "Valuation methods disagree or lack inputs. A point estimate would give false precision.")
    elif not value_pass and return_pass:
        why.insert(0, returns + " Clearing this hurdle alone does not qualify a stock.")
    if not why:
        why = ["The entry screen, business health, valuation cushion and return hurdle pass."]
    price = cushion_price(models, threshold) if reliable and not value_pass else None
    changes = []
    if price is not None:
        changes.append(f"With every estimate held fixed, the valuation cushion rule passes at {kes(price)} or lower. "
                       "This is a conditional rule threshold, not a price target or a Buy instruction. "
                       "Peer prices, bond yields and new filings can move the estimates. "
                       "All other entry and evidence checks still apply.")
    if not reliable:
        changes.append("Verify missing inputs and investigate the disagreement between valuation methods before "
                       "relying on a return estimate. A lower price alone does not resolve this.")
    if quality["gate"] != "pass":
        changes.append("New, reviewed financial statements must resolve the failed or missing business-health checks.")
    if row["screen_fail"]:
        changes.append("Resolve the failed trading or data checks, then rerun the analysis.")
    if reliable and not return_pass:
        changes.append("A new price, reviewed filing or benchmark rate must produce a modelled return above the "
                       "hurdle, with the other entry rules still passing.")
    if not changes:
        changes.append("New prices, filings or benchmark rates can change the verdict. Recheck before acting.")
    verify = ["Read the annual filing and any more recent interim results; verify earnings, dividends and share changes.",
              "Review company notices and the assumptions behind the valuation; a fresh feed does not prove accuracy."]
    verify += row.get("conviction", {}).get("held_back", [])
    return {"reason": reason, "why": why, "checks": checks, "agreement": agreement, "return_context": returns,
            "cushion_fraction": threshold, "cushion_price": price, "changes": changes, "verify": verify,
            "models": [{"name": MODEL_NAMES.get(name, name), "value": value, "passes": name in row["agree"]}
                       for name, value in sorted(models.items(), key=lambda item: -item[1])],
            "holder_note": "These entry rules do not decide whether to sell an existing holding."}


def markdown(row: dict) -> list[str]:
    d = row.get("decision")
    if not d:
        return []
    return [f"- **Verdict: {row['tier']}. {d['reason']}.**",
            "- **Why:** " + " ".join(d["why"]),
            "- **What would change it:** " + " ".join(d["changes"]),
            "- **What to verify:** " + " ".join(d["verify"]), f"- **Already own it?** {d['holder_note']}"]
