# Walk-forward backtest

> **Not financial advice.** This report is generated automatically from public data and fixed rules. It is not financial advice, an offer, or a recommendation to buy or sell any security. Figures can be wrong or stale. Verify everything against company filings and consult a licensed adviser before investing.

Monthly rebalance from 2019-06-01 to 2026-11-01 (89 months). At each date the engine only sees annual results published on or before that date.

| Strategy | CAGR | Volatility | Max drawdown | Total return |
|---|---|---|---|---|
| Top 3 by composite rank | 6.5% | 25.6% | -68.5% | 59.4% |
| Undervalued picks only (cash at net T-bill otherwise) | 20.9% | 14.2% | -6.4% | 309.3% |
| Equal-weight universe | 13.8% | 17.6% | -31.7% | 161.6% |

- Months the top 3 beat the universe: **44.9%**.
- Months with at least one undervalued pick: **26 of 89**.

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
| 2026-10-01 | 16 | KCB, EQTY, COOP | cash | -6.6% | 0.6% | -5.1% |
| 2026-09-01 | 16 | EQTY, KCB, COOP | cash | 1.8% | 0.6% | -1.0% |
| 2026-08-01 | 16 | EQTY, KCB, COOP | cash | 8.1% | -1.2% | 7.8% |
| 2026-07-01 | 16 | EQTY, KCB, DTK | EQTY, KCB | 5.3% | 7.2% | 4.6% |
| 2026-06-01 | 16 | KCB, EQTY, COOP | KCB, EQTY | 9.6% | 13.6% | 9.0% |
| 2026-05-01 | 16 | KPLC, DTK, KCB | KCB | -0.9% | -0.4% | -1.1% |
| 2026-04-01 | 16 | KPLC, DTK, KCB | KCB | -2.7% | -4.4% | 3.8% |
| 2026-03-01 | 16 | NCBA, DTK, KPLC | cash | -7.0% | -1.2% | -6.5% |
| 2026-02-01 | 16 | DTK, KPLC, KCB | KCB | 20.9% | 20.7% | 12.4% |
| 2026-01-01 | 16 | KPLC, DTK, KCB | KCB | 8.8% | 1.1% | 5.7% |
| 2025-12-01 | 16 | KPLC, DTK, KCB | KCB | 6.1% | 11.9% | 4.5% |
| 2025-11-01 | 16 | KPLC, DTK, KCB | KCB | -2.5% | -4.5% | -3.6% |
| 2025-10-01 | 16 | DTK, KCB, SCBK | KCB | 4.0% | 8.8% | 8.6% |
| 2025-09-01 | 16 | DTK, KCB, NCBA | KCB | 8.0% | 3.2% | 3.6% |
| 2025-08-01 | 16 | DTK, KCB, KPLC | KCB, COOP | 18.0% | 9.7% | 12.2% |
| 2025-07-01 | 16 | DTK, KCB, KPLC | KCB | 1.7% | 1.2% | 3.6% |
| 2025-06-01 | 16 | KPLC, DTK, KCB | KCB, COOP | 16.8% | 10.7% | 13.2% |
| 2025-05-01 | 16 | KPLC, DTK, IMH | COOP | 9.5% | 5.8% | 2.9% |
| 2025-04-01 | 16 | KPLC, DTK, KEGN | cash | -4.3% | 0.6% | -2.8% |
| 2025-03-01 | 16 | KPLC, DTK, KCB | cash | -5.1% | 0.6% | -1.7% |
| 2025-02-01 | 16 | KPLC, DTK, IMH | cash | 2.1% | 0.6% | 5.5% |
| 2025-01-01 | 16 | KPLC, DTK, KEGN | cash | 24.8% | 0.6% | 4.6% |
| 2024-12-01 | 16 | KPLC, DTK, KEGN | cash | 13.5% | 0.6% | 11.8% |
| 2024-11-01 | 16 | KPLC, DTK, KEGN | cash | -5.5% | 0.6% | -3.0% |
| 2024-10-01 | 16 | DTK, KCB, IMH | cash | 12.7% | 0.6% | 10.4% |
| 2024-09-01 | 16 | DTK, KCB, IMH | cash | 8.3% | 0.6% | 10.1% |
| 2024-08-01 | 16 | DTK, KCB, IMH | cash | 2.9% | 0.6% | 3.8% |
| 2024-07-01 | 16 | DTK, KCB, IMH | cash | -2.5% | -1.2% | -1.1% |
| 2024-06-01 | 16 | DTK, IMH, KCB | SBIC | -1.3% | 2.0% | -1.9% |
| 2024-05-01 | 16 | DTK, IMH, KCB | cash | 4.5% | 0.6% | 3.0% |
| 2024-04-01 | 14 | COOP, KCB, BAT | cash | -7.4% | 0.6% | -4.1% |
| 2024-03-01 | 14 | KCB, COOP, CARB | cash | 19.3% | -1.2% | 15.7% |
| 2024-02-01 | 14 | KCB, COOP, BAT | COOP | 3.0% | 6.9% | 4.4% |
| 2024-01-01 | 14 | COOP, KCB, EQTY | COOP, EQTY | 1.9% | 8.2% | 0.4% |
| 2023-12-01 | 14 | KCB, COOP, CARB | COOP | 3.9% | 0.0% | 1.2% |
| 2023-11-01 | 14 | KCB, COOP, ABSA | COOP | -1.4% | -3.1% | -1.6% |
| 2023-10-01 | 14 | KPLC, KEGN, COOP | COOP, EQTY | 0.5% | 0.8% | -2.7% |
| 2023-09-01 | 14 | KPLC, KEGN, COOP | COOP | -1.8% | -0.4% | -1.9% |
| 2023-08-01 | 14 | KPLC, COOP, KEGN | COOP | -1.4% | -0.8% | -4.8% |
| 2023-07-01 | 14 | KPLC, COOP, KEGN | COOP | -0.9% | -2.0% | 2.2% |
| 2023-06-01 | 14 | KPLC, COOP, KEGN | COOP | 0.9% | -1.0% | 2.5% |
| 2023-05-01 | 14 | KPLC, COOP, KEGN | cash | -2.0% | 0.6% | -5.1% |
| 2023-04-01 | 14 | COOP, KPLC, KEGN | cash | 1.4% | 0.6% | -2.1% |
| 2023-03-01 | 14 | KPLC, COOP, KEGN | cash | -1.3% | 0.6% | 0.3% |
| 2023-02-01 | 14 | KPLC, KEGN, COOP | cash | -5.1% | 0.6% | -1.0% |
| 2023-01-01 | 14 | COOP, KPLC, KEGN | cash | -3.6% | 0.6% | -0.1% |
| 2022-12-01 | 14 | KPLC, COOP, KEGN | cash | 2.0% | 0.6% | 3.1% |
| 2022-11-01 | 14 | KPLC, COOP, KEGN | cash | -7.2% | 0.6% | -2.0% |
| 2022-10-01 | 14 | KEGN, COOP, SBIC | cash | -2.7% | 0.6% | 1.3% |
| 2022-09-01 | 14 | KEGN, COOP, SBIC | cash | -3.3% | -1.2% | -0.7% |
| 2022-08-01 | 14 | KEGN, COOP, SBIC | NCBA | 5.0% | 20.1% | 3.6% |
| 2022-07-01 | 14 | KEGN, COOP, SBIC | NCBA | 1.1% | 2.2% | 4.4% |
| 2022-06-01 | 14 | COOP, KEGN, SCBK | cash | -2.9% | 0.6% | -2.5% |
| 2022-05-01 | 14 | COOP, KEGN, NCBA | cash | -6.0% | 0.6% | -3.5% |
| 2022-04-01 | 14 | COOP, KEGN, SBIC | cash | -2.5% | 0.6% | -4.6% |
| 2022-03-01 | 14 | KEGN, NCBA, BAT | cash | -1.5% | 0.6% | -0.1% |
| 2022-02-01 | 14 | KEGN, BAT, TOTL | cash | 1.2% | 0.6% | -0.0% |
| 2022-01-01 | 14 | KEGN, SBIC, BAT | cash | 0.0% | 0.6% | -1.0% |
| 2021-12-01 | 14 | KEGN, BAT, SBIC | cash | -3.7% | 0.6% | 3.2% |
| 2021-11-01 | 14 | KEGN, BAT, CARB | cash | -4.6% | 0.6% | -3.4% |
| 2021-10-01 | 14 | KEGN, BAT, NCBA | cash | -6.1% | 0.6% | -2.6% |
| 2021-09-01 | 14 | KEGN, BAT, SBIC | cash | -0.9% | 0.6% | -0.1% |
| 2021-08-01 | 14 | KEGN, BAT, SBIC | cash | 4.9% | 0.6% | 2.8% |
| 2021-07-01 | 14 | KEGN, BAT, SBIC | cash | 6.4% | 0.6% | 3.9% |
| 2021-06-01 | 14 | KEGN, BAT, SBIC | cash | -1.7% | 0.6% | 2.2% |
| 2021-05-01 | 14 | KEGN, CARB, BAT | cash | -3.7% | 0.6% | -2.5% |
| 2021-04-01 | 14 | KEGN, CARB, TOTL | cash | -4.7% | 0.6% | -0.9% |
| 2021-03-01 | 14 | KEGN, NCBA, KCB | cash | -1.2% | 0.6% | -1.7% |
| 2021-02-01 | 14 | KPLC, CARB, COOP | cash | -1.1% | 0.6% | 3.0% |
| 2021-01-01 | 14 | KPLC, CARB, KCB | cash | -6.2% | 0.6% | -1.1% |
| 2020-12-01 | 14 | KPLC, KCB, SCOM | cash | 9.0% | 0.6% | 5.7% |
| 2020-11-01 | 14 | KPLC, KCB, COOP | cash | -6.1% | 0.6% | 2.5% |
| 2020-10-01 | 14 | KPLC, KCB, EQTY | cash | -6.2% | 0.6% | -1.8% |
| 2020-09-01 | 14 | KPLC, COOP, KCB | cash | -1.8% | 0.6% | -1.0% |
| 2020-08-01 | 14 | KPLC, COOP, KCB | cash | 6.5% | 0.6% | 2.6% |
| 2020-07-01 | 14 | KPLC, COOP, KCB | cash | -5.4% | 0.6% | -4.4% |
| 2020-06-01 | 14 | KPLC, COOP, KCB | cash | 3.5% | 0.6% | 1.0% |
| 2020-05-01 | 14 | COOP, KPLC, KCB | cash | -7.6% | 0.6% | -4.6% |
| 2020-04-01 | 12 | KPLC, COOP, BAT | cash | -4.2% | 0.6% | 2.5% |
| 2020-03-01 | 12 | KPLC, NCBA, ABSA | cash | -21.6% | 0.6% | -13.5% |
| 2020-02-01 | 12 | KPLC, NCBA, SCOM | cash | -11.0% | 0.6% | -6.6% |
| 2020-01-01 | 12 | KPLC, NCBA, SCOM | cash | -3.1% | 0.6% | -0.6% |
| 2019-12-01 | 12 | KPLC, NCBA, ABSA | cash | 0.8% | 0.6% | 1.5% |
| 2019-11-01 | 12 | KPLC, NCBA, BAT | cash | -7.1% | 0.6% | -4.3% |
| 2019-10-01 | 12 | KPLC, NCBA, SCOM | cash | 14.7% | 0.6% | 14.5% |
| 2019-09-01 | 12 | KPLC, NCBA, SBIC | cash | -7.0% | 0.6% | -0.7% |
| 2019-08-01 | 12 | KPLC, NCBA, SCOM | cash | -3.4% | 0.6% | -2.4% |
| 2019-07-01 | 12 | KPLC, NCBA, TOTL | cash | 0.3% | 0.6% | -0.1% |
| 2019-06-01 | 12 | KPLC, NCBA, SCOM | cash | 4.0% | 0.6% | 0.9% |
