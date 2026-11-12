# Walk-forward backtest

> **Not financial advice.** This report is generated automatically from public data and fixed rules. It is not financial advice, an offer, or a recommendation to buy or sell any security. Figures can be wrong or stale. Verify everything against company filings and consult a licensed adviser before investing.

Monthly rebalance from 2019-06-01 to 2026-11-01 (89 months). At each date the engine only sees annual results published on or before that date.

| Strategy | CAGR | Volatility | Max drawdown | Total return |
|---|---|---|---|---|
| Top 3 by composite rank | 17.0% | 23.8% | -51.9% | 219.6% |
| Undervalued picks only (cash at net T-bill otherwise) | 11.5% | 7.5% | -8.2% | 124.7% |
| Equal-weight universe | 21.7% | 17.5% | -24.9% | 329.4% |

- Months the top 3 beat the universe: **43.8%**.
- Months with at least one undervalued pick: **15 of 89**.

## Limitations

- Returns adjust for sourced bonus issues and splits and add sourced dividends net of withholding tax, without reinvestment. Dividends missing from `data/dividends.yaml` understate high-yield names.
- The universe is today's coverage list, so delisted and failed counters are missing (survivorship bias).
- Macro inputs (bond yield, risk premiums) are today's values, not the values known at each date.
- 89 of 144 fundamentals periods use the CMA filing deadline as their publication date. That is later than the real release for companies that report early, but it is look-ahead for any company that filed late. 53 period(s) with a stated release date, including known late filings, use that date instead.
- Liquidity and suspension screens are off because historical volume and suspension data are not stored.
- Trading costs use the current per-side rate on names that change at each rebalance.
- Short samples and a small universe make these numbers noisy. Treat them as a sanity check.

## Holdings by month

| Month | Valued | Top 3 | Picks | Top return | Picks return | Universe |
|---|---|---|---|---|---|---|
| 2026-10-01 | 16 | KCB, EQTY, COOP | cash | -7.8% | 0.6% | -4.5% |
| 2026-09-01 | 16 | COOP, IMH, EQTY | cash | 2.6% | 0.6% | -0.6% |
| 2026-08-01 | 16 | COOP, BAT, IMH | cash | 6.5% | -1.2% | 8.4% |
| 2026-07-01 | 16 | COOP, DTK, BAT | EQTY | 1.5% | 5.2% | 4.6% |
| 2026-06-01 | 16 | COOP, BAT, SBIC | EQTY | 3.3% | 9.3% | 9.4% |
| 2026-05-01 | 16 | KPLC, DTK, KEGN | cash | -0.7% | 0.6% | 2.0% |
| 2026-04-01 | 16 | KPLC, SCBK, KEGN | cash | -0.6% | 0.6% | 4.3% |
| 2026-03-01 | 16 | KEGN, NCBA, COOP | cash | -6.6% | 0.6% | -6.5% |
| 2026-02-01 | 16 | KEGN, DTK, SBIC | cash | 14.6% | 0.6% | 12.8% |
| 2026-01-01 | 16 | KEGN, KPLC, SCBK | cash | 6.7% | 0.6% | 5.7% |
| 2025-12-01 | 16 | KEGN, SCBK, KPLC | cash | 5.1% | 0.6% | 5.6% |
| 2025-11-01 | 16 | KPLC, SCBK, KEGN | cash | -4.3% | 0.6% | -2.9% |
| 2025-10-01 | 16 | KEGN, SCBK, KPLC | cash | 6.7% | 0.6% | 8.6% |
| 2025-09-01 | 16 | KPLC, SCBK, KEGN | cash | -3.8% | -1.2% | 4.7% |
| 2025-08-01 | 16 | KPLC, SCBK, KEGN | COOP | 17.9% | 4.8% | 12.3% |
| 2025-07-01 | 16 | KPLC, SCBK, KEGN | cash | 5.9% | -1.2% | 3.8% |
| 2025-06-01 | 16 | KPLC, SCBK, KEGN | COOP | 26.7% | 13.2% | 13.6% |
| 2025-05-01 | 16 | KPLC, KEGN, IMH | COOP | 12.1% | 5.8% | 7.0% |
| 2025-04-01 | 16 | KPLC, KEGN, IMH | cash | -3.8% | 0.6% | -1.7% |
| 2025-03-01 | 16 | KPLC, KEGN, IMH | cash | -2.4% | 0.6% | -1.3% |
| 2025-02-01 | 16 | KPLC, KEGN, IMH | cash | 5.4% | 0.6% | 5.6% |
| 2025-01-01 | 16 | KPLC, KEGN, IMH | cash | 20.7% | 0.6% | 4.6% |
| 2024-12-01 | 16 | KPLC, KEGN, SCBK | cash | 12.5% | 0.6% | 13.0% |
| 2024-11-01 | 16 | KPLC, SCBK, IMH | cash | 2.6% | 0.6% | -1.6% |
| 2024-10-01 | 16 | SCBK, IMH, KCB | cash | 13.5% | 0.6% | 10.4% |
| 2024-09-01 | 16 | IMH, SCBK, KCB | cash | 9.4% | 0.6% | 11.4% |
| 2024-08-01 | 16 | IMH, SCBK, KCB | cash | 5.9% | 0.6% | 3.8% |
| 2024-07-01 | 16 | KCB, IMH, SCBK | cash | -6.7% | -1.2% | -0.9% |
| 2024-06-01 | 16 | SBIC, ABSA, DTK | SBIC | -1.2% | 2.0% | -1.4% |
| 2024-05-01 | 16 | IMH, COOP, SCBK | cash | 7.6% | 0.6% | 6.6% |
| 2024-04-01 | 14 | CARB, COOP, BAT | cash | -4.3% | 0.6% | -2.1% |
| 2024-03-01 | 14 | CARB, COOP, SCBK | cash | 12.6% | -1.2% | 16.0% |
| 2024-02-01 | 14 | SCBK, BAT, CARB | COOP | -1.2% | 6.0% | 4.5% |
| 2024-01-01 | 14 | CARB, KEGN, SCBK | COOP, EQTY | -0.7% | 7.3% | 0.4% |
| 2023-12-01 | 14 | CARB, KEGN, SBIC | COOP | -2.2% | 0.0% | 1.5% |
| 2023-11-01 | 14 | SCBK, SBIC, ABSA | COOP | -5.8% | -4.0% | -0.2% |
| 2023-10-01 | 14 | CARB, NCBA, SCBK | COOP, EQTY | 2.8% | -0.1% | -2.7% |
| 2023-09-01 | 14 | CARB, SCBK, NCBA | COOP | 2.7% | -0.4% | -1.4% |
| 2023-08-01 | 14 | NCBA, SCBK, CARB | COOP | -4.5% | -0.8% | -4.7% |
| 2023-07-01 | 14 | SCBK, NCBA, COOP | COOP | -1.5% | -2.0% | 2.4% |
| 2023-06-01 | 14 | NCBA, BAT, COOP | COOP | 4.2% | -1.0% | 2.9% |
| 2023-05-01 | 14 | SCBK, NCBA, COOP | cash | 0.5% | 0.6% | -1.1% |
| 2023-04-01 | 14 | NCBA, SCBK, CARB | cash | 3.4% | 0.6% | -0.7% |
| 2023-03-01 | 14 | NCBA, SCBK, CARB | cash | 2.5% | 0.6% | 0.4% |
| 2023-02-01 | 14 | NCBA, SCBK, CARB | cash | 2.6% | 0.6% | -0.9% |
| 2023-01-01 | 14 | NCBA, SCBK, CARB | cash | 0.5% | 0.6% | 0.3% |
| 2022-12-01 | 14 | NCBA, CARB, SCBK | cash | 8.2% | 0.6% | 3.5% |
| 2022-11-01 | 14 | NCBA, SCBK, BAT | cash | 2.9% | 0.6% | -1.3% |
| 2022-10-01 | 14 | NCBA, SCBK, BAT | cash | -0.1% | 0.6% | 1.3% |
| 2022-09-01 | 14 | SCBK, SBIC, NCBA | cash | 3.1% | 0.6% | 0.1% |
| 2022-08-01 | 14 | SBIC, SCBK, NCBA | cash | 7.9% | 0.6% | 3.6% |
| 2022-07-01 | 14 | SBIC, SCBK, NCBA | cash | 3.7% | 0.6% | 4.6% |
| 2022-06-01 | 14 | SCBK, SBIC, NCBA | cash | -6.6% | 0.6% | -1.9% |
| 2022-05-01 | 14 | ABSA, SCBK, BAT | cash | -3.8% | 0.6% | -1.8% |
| 2022-04-01 | 14 | ABSA, EQTY, COOP | cash | -6.0% | 0.6% | -2.2% |
| 2022-03-01 | 14 | ABSA, KEGN, TOTL | cash | 0.1% | 0.6% | -0.0% |
| 2022-02-01 | 14 | TOTL, ABSA, KEGN | cash | -1.9% | 0.6% | 0.1% |
| 2022-01-01 | 14 | KEGN, TOTL, EQTY | cash | -5.9% | 0.6% | -1.0% |
| 2021-12-01 | 14 | KEGN, KPLC, CARB | cash | -0.8% | 0.6% | 4.0% |
| 2021-11-01 | 14 | CARB, EQTY, KEGN | cash | -1.3% | 0.6% | -2.6% |
| 2021-10-01 | 14 | CARB, SCOM, EQTY | cash | -2.8% | 0.6% | -2.6% |
| 2021-09-01 | 14 | CARB, TOTL, SCOM | cash | 0.8% | 0.6% | 0.2% |
| 2021-08-01 | 14 | CARB, SCOM, COOP | cash | -1.5% | 0.6% | 2.9% |
| 2021-07-01 | 14 | BAT, SCOM, CARB | cash | 1.6% | 0.6% | 4.0% |
| 2021-06-01 | 14 | BAT, SCOM, CARB | cash | 3.9% | 0.6% | 2.5% |
| 2021-05-01 | 14 | BAT, CARB, SCOM | cash | 0.2% | 0.6% | 0.5% |
| 2021-04-01 | 14 | CARB, BAT, SCOM | cash | -1.3% | 0.6% | -0.8% |
| 2021-03-01 | 14 | CARB, COOP, SCOM | cash | -6.4% | 0.6% | -1.7% |
| 2021-02-01 | 14 | CARB, COOP, SCOM | cash | 4.4% | 0.6% | 3.0% |
| 2021-01-01 | 14 | CARB, BAT, ABSA | cash | -2.4% | 0.6% | -1.1% |
| 2020-12-01 | 14 | SCOM, TOTL, KEGN | cash | 3.6% | 0.6% | 5.7% |
| 2020-11-01 | 14 | COOP, KEGN, SCOM | cash | -2.5% | 0.6% | 2.5% |
| 2020-10-01 | 14 | EQTY, SCOM, KEGN | cash | -3.9% | 0.6% | -1.8% |
| 2020-09-01 | 14 | CARB, KEGN, COOP | cash | -4.5% | 0.6% | -1.0% |
| 2020-08-01 | 14 | CARB, COOP, ABSA | cash | 8.2% | 0.6% | 2.8% |
| 2020-07-01 | 14 | CARB, ABSA, COOP | cash | -12.5% | 0.6% | -4.4% |
| 2020-06-01 | 14 | COOP, CARB, ABSA | cash | -2.3% | 0.6% | 1.0% |
| 2020-05-01 | 14 | COOP, CARB, ABSA | cash | -2.2% | 0.6% | -4.0% |
| 2020-04-01 | 12 | ABSA, COOP, SBIC | cash | -0.9% | 0.6% | 3.9% |
| 2020-03-01 | 12 | ABSA, COOP, CARB | cash | -11.5% | 0.6% | -13.5% |
| 2020-02-01 | 12 | ABSA, NCBA, SCOM | cash | -5.8% | 0.6% | -6.6% |
| 2020-01-01 | 12 | ABSA, NCBA, SCOM | cash | -2.5% | 0.6% | -0.6% |
| 2019-12-01 | 12 | NCBA, ABSA, SCOM | cash | 5.6% | 0.6% | 1.5% |
| 2019-11-01 | 12 | NCBA, ABSA, BAT | cash | -8.1% | 0.6% | -4.3% |
| 2019-10-01 | 12 | SCOM, ABSA, NCBA | cash | 18.5% | 0.6% | 14.5% |
| 2019-09-01 | 12 | ABSA, SCOM, SBIC | cash | -0.9% | 0.6% | -0.7% |
| 2019-08-01 | 12 | SCOM, ABSA, SBIC | cash | 0.4% | 0.6% | -2.4% |
| 2019-07-01 | 12 | ABSA, SCOM, TOTL | cash | 0.6% | 0.6% | -0.1% |
| 2019-06-01 | 12 | NCBA, SCOM, ABSA | cash | 0.6% | 0.6% | 1.2% |
