# Walk-forward backtest

> **Not financial advice.** This report is generated automatically from public data and fixed rules. It is not financial advice, an offer, or a recommendation to buy or sell any security. Figures can be wrong or stale. Verify everything against company filings and consult a licensed adviser before investing.

Monthly rebalance from 2026-08-01 to 2026-11-01 (3 months). At each date the engine only sees annual results published on or before that date.

| Strategy | CAGR | Volatility | Max drawdown | Total return |
|---|---|---|---|---|
| Top 3 by composite rank | -3.7% | 21.1% | -8.6% | -0.9% |
| Undervalued picks only (cash at net T-bill otherwise) | 7.9% | 0.0% | 0.0% | 1.9% |
| Equal-weight universe | 5.1% | 18.7% | -6.1% | 1.2% |

- Months the top 3 beat the universe: **33.3%**.
- Months with at least one undervalued pick: **0 of 3**.

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
| 2026-10-01 | 7 | KPLC, CARB, KEGN | cash | -5.3% | 0.6% | -5.1% |
| 2026-09-01 | 7 | KPLC, KEGN, CARB | cash | -3.5% | 0.6% | -1.0% |
| 2026-08-01 | 7 | KPLC, BAT, CARB | cash | 8.4% | 0.6% | 7.8% |
