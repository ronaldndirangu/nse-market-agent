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
    br = sub.add_parser("brief", help="Daily brief: top 5 with reasons, what changed, ledger append")
    br.add_argument("--no-fetch", action="store_true", help="Use cached market data only")
    br.add_argument("--no-prices", action="store_true", help="Refresh announcements only (prices already recorded)")
    br.add_argument("--alert-file", help="Write material-change alerts here (only when there are any)")
    sub.add_parser("score", help="Score logged picks against the market")
    bt = sub.add_parser("backtest", help="Point-in-time walk-forward backtest")
    bt.add_argument("--top", type=int, default=3)
    sm = sub.add_parser("simulate", help="Monte Carlo projection of current picks")
    sm.add_argument("--paths", type=int, default=5000)
    sub.add_parser("review", help="Review portfolio.yaml holdings")
    sub.add_parser("results-watch", help="Detect new results announcements and queue them for review")
    sub.add_parser("mcp", help="Run the MCP server (needs the mcp extra)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stderr)

    if args.cmd == "daily":
        from .market import update_daily
        snap = update_daily()
        print(f"source={snap['source']} trade_date={snap['trade_date']} errors={snap['errors']}")
        return 0 if snap["source"] != "cache" else 1
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
        out = run_weekly(fetch=not args.no_fetch)
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
