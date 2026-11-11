# Walk-forward backtest

> **Not financial advice.** This report is generated automatically from public data and fixed rules. It is not financial advice, an offer, or a recommendation to buy or sell any security. Figures can be wrong or stale. Verify everything against company filings and consult a licensed adviser before investing.

Monthly rebalance from 2026-06-01 to 2026-11-01 (5 months). At each date the engine only sees annual results published on or before that date.

| Strategy | CAGR | Volatility | Max drawdown | Total return |
|---|---|---|---|---|
| Top 3 by composite rank | 46.5% | 23.4% | -8.7% | 17.3% |
| Undervalued picks only (cash at net T-bill otherwise) | 57.8% | 18.0% | -1.2% | 20.9% |
| Equal-weight universe | 41.0% | 18.6% | -6.1% | 15.4% |

- Months the top 3 beat the universe: **80.0%**.
- Months with at least one undervalued pick: **2 of 5**.

## Limitations

- Returns are price-only. Dividends are excluded from every line, which understates high-yield names.
- The universe is today's coverage list, so delisted and failed counters are missing (survivorship bias).
- Macro inputs (bond yield, risk premiums) are today's values, not the values known at each date.
- Liquidity and suspension screens are off because historical volume and suspension data are not stored.
- Trading costs use the current per-side rate on names that change at each rebalance.
- Short samples and a small universe make these numbers noisy. Treat them as a sanity check.

## Holdings by month

| Month | Valued | Top 3 | Picks | Top return | Picks return | Universe |
|---|---|---|---|---|---|---|
| 2026-10-01 | 16 | KCB, EQTY, KPLC | cash | -8.7% | 0.6% | -5.1% |
| 2026-09-01 | 16 | EQTY, KCB, COOP | cash | 1.8% | 0.6% | -1.0% |
| 2026-08-01 | 16 | EQTY, KCB, COOP | cash | 8.1% | -1.2% | 7.8% |
| 2026-07-01 | 16 | EQTY, KCB, DTK | EQTY, KCB | 5.3% | 7.2% | 4.6% |
| 2026-06-01 | 16 | KPLC, KCB, EQTY | KCB, EQTY | 10.8% | 12.7% | 9.0% |
