from __future__ import annotations

import argparse
import logging
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nse_agent", description="Deterministic NSE value agent")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("daily", help="Record today's prices and NASI")
    sub.add_parser("backfill", help="One-time price history backfill from AFX charts")
    sub.add_parser("refresh", help="Refresh AFX company pages (volume history, liquidity)")
    wk = sub.add_parser("weekly", help="Value, rank and write the report")
    wk.add_argument("--no-fetch", action="store_true", help="Use cached market data only")
    wk.add_argument("--alert-file", help="Write Buy and undervalued list changes here (only when there are any)")
    br = sub.add_parser("brief", help="Daily brief: top 5 with reasons, what changed, ledger append")
    br.add_argument("--no-fetch", action="store_true", help="Use cached market data only")
    br.add_argument("--no-prices", action="store_true",
                    help="Refresh announcements and official inputs without collecting prices")
    br.add_argument("--alert-file", help="Write material-change alerts here (only when there are any)")
    sub.add_parser("score", help="Score logged picks against the market")
    bt = sub.add_parser("backtest", help="Point-in-time walk-forward backtest")
    bt.add_argument("--top", type=int, default=3)
    sm = sub.add_parser("simulate", help="Monte Carlo projection of current picks")
    sm.add_argument("--paths", type=int, default=5000)
    sub.add_parser("reconstruct", help="Rerun the engine point in time on every month start (reconstructed ledger)")
    rt = sub.add_parser("retro", help="Forward scorecard, per-signal IC and reverse attribution")
    rt.add_argument("--no-rebuild", action="store_true", help="Reuse the existing reconstructed ledger")
    tw = sub.add_parser("tune-weights", help="Walk-forward weight tuning report (never edits settings)")
    tw.add_argument("--proposal-file", help="Write proposed weights here as JSON when a change is recommended")
    tw.add_argument("--body-file", help="Write a pull request body here when a change is recommended")
    aw = sub.add_parser("apply-weights", help="Set ranking weights in settings.yaml from a proposal file (review branch)")
    aw.add_argument("proposal")
    sub.add_parser("review", help="Review portfolio.yaml holdings")
    sub.add_parser("results-watch", help="Detect new results announcements and queue them for review")
    sub.add_parser("enrich", help="Collect official CBK rates and KNBS inflation with dated provenance")
    sub.add_parser("mcp", help="Run the MCP server (needs the mcp extra)")
    st = sub.add_parser("site", help="Build the static site without refreshing data")
    st.add_argument("--check", action="store_true", help="Validate pages and publication provenance")
    published = sub.add_parser("check-published", help="Check the deployed report for missed updates")
    published.add_argument("--url", default="https://ronaldndirangu.github.io/nse-market-agent/")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stderr)

    if args.cmd == "enrich":
        from . import official
        outcomes = official.refresh()
        print(" ".join(f"{name}={status}" for name, status in outcomes.items()))
        return int(outcomes.get("cbk") == "failed")
    if args.cmd == "check-published":
        from .publication import check_published
        print(check_published(args.url))
        return 0
    if args.cmd == "site":
        from . import site
        written = site.build()
        checked = site.check() if args.check else 0
        print(f"site_pages={len(written)} checked={checked}")
        return 0
    if args.cmd == "daily":
        from .market import update_daily
        snap = update_daily()
        print(f"source={snap['source']} trade_date={snap['trade_date']} intraday={snap['intraday']} "
              f"errors={snap['errors']}")
        return 0 if snap["source"] != "cache" and not snap["intraday"] else 1
    if args.cmd == "backfill":
        from .market import backfill
        backfill()
        return 0
    if args.cmd == "refresh":
        from .market import refresh_companies
        refresh_companies()
        return 0
    if args.cmd == "weekly":
        from .pipeline import run_weekly
        out = run_weekly(fetch=not args.no_fetch, alert_file=args.alert_file)
        print(out)
        return 0
    if args.cmd == "brief":
        from .brief import run_brief
        print(run_brief(fetch=not args.no_fetch, alert_file=args.alert_file, fetch_prices=not args.no_prices))
        return 0
    if args.cmd == "score":
        from .score import run_score
        print(run_score())
        return 0
    if args.cmd == "backtest":
        from .backtest import run_backtest
        print(run_backtest(top=args.top))
        return 0
    if args.cmd == "simulate":
        from .simulate import run_simulation
        print(run_simulation(paths=args.paths))
        return 0
    if args.cmd == "reconstruct":
        from .retrospective import reconstruct
        print(f"reconstructed_rows={reconstruct()}")
        return 0
    if args.cmd == "retro":
        from .retrospective import run_retro
        print(run_retro(rebuild=not args.no_rebuild))
        return 0
    if args.cmd == "tune-weights":
        from .tuning import run_tuning
        print(run_tuning(proposal_file=args.proposal_file, body_file=args.body_file))
        return 0
    if args.cmd == "apply-weights":
        import json
        from .tuning import apply
        apply(json.loads(open(args.proposal, encoding="utf-8").read()))
        return 0
    if args.cmd == "review":
        from .portfolio import run_review
        print(run_review())
        return 0
    if args.cmd == "results-watch":
        from .results_watch import run_results_watch
        print(run_results_watch())
        return 0
    if args.cmd == "mcp":
        from .mcp_server import serve
        serve()
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
