# Walk-forward backtest

> **Not financial advice.** This report is generated automatically from public data and fixed rules. It is not financial advice, an offer, or a recommendation to buy or sell any security. Figures can be wrong or stale. Verify everything against company filings and consult a licensed adviser before investing.

Monthly rebalance from 2019-06-01 to 2026-11-01 (89 months). At each date the engine only sees annual results published by then and the CBK T-bill rates published before each month start (the Buy hurdle uses the 364-day rate; cash earns the 91-day rate after 15% tax).

## Result

**The Buy rule did not clearly beat or trail the covered stocks weighted by company size: 11.1% a year against 12.8% after trading costs, with a worst fall of -8.2% against -47.7%. The 95% range for the yearly difference is -17.4 points to +10.4 points.**

| Strategy | Return a year after costs | Before costs | Volatility | Worst fall | Turnover a year |
|---|---|---|---|---|---|
| Buy rule (T-bills when there is no Buy) | 11.1% | 15.0% | 7.4% | -8.2% | 1.90x |
| Top 3 by research score | 16.0% | 32.2% | 23.5% | -52.4% | 7.15x |
| Covered stocks, weighted by company size | 12.8% | 13.2% | 22.4% | -47.7% | 0.21x |
| Covered stocks, equal weights | 20.2% | 21.7% | 17.5% | -25.8% | 0.68x |
| NASI, all listed shares (price only, no dividends or costs) | 6.4% | 6.4% | 20.2% | -51.4% | n/a |
| 91-day T-bills after tax | 8.1% | 8.1% | n/a | 0.0% | 0.00x |

- Every strategy starts in cash and pays 1.82% per side on the weight it trades, including the first purchase and monthly rebalancing. Dividends stay invested until the next rebalance.
- The Buy rule held stocks in **15 of 89** months. In those months it earned 4.10% a month before costs and 2.95% after, against 2.83% for the size-weighted basket.
- The T-bill hurdle never blocked a stock that passed the valuation checks, even when 364-day bills paid 17.0%.

## Benchmark check

The size-weighted covered basket, price only, returned 7.0% a year against 6.4% for NASI: a gap of +0.5 points and a tracking error of 4.6%. **Passed** (limits: 1.5% gap, 6.0% tracking error). A close match means the 16 covered stocks stand in reasonably for the whole market.

## What a fixed mix would have become

KES 250,000 invested on 2019-06-01 in the size-weighted covered basket and 91-day T-bills, rebalanced monthly after costs. KES 250,000 is the smallest round amount that buys whole shares of every covered stock at today's weights with under 1% left over.

| Mix | Value on 2026-11-01 | Return a year | Worst fall |
|---|---|---|---|
| 0% stocks, 100% T-bills | KES 446,556 | 8.1% | 0.0% |
| 25% stocks, 75% T-bills | KES 493,070 | 9.6% | -5.0% |
| 50% stocks, 50% T-bills | KES 537,248 | 10.9% | -21.0% |
| 75% stocks, 25% T-bills | KES 577,374 | 11.9% | -35.5% |
| 100% stocks, 0% T-bills | KES 609,905 | 12.8% | -47.7% |

These illustrate fixed rules and are the same for every reader. They are not a recommended mix.

## Shadow experiments

Each rule below is frozen and compared with the size-weighted basket. None changes a published verdict. A rule goes to human review only when all four checks pass: the 95% range of its yearly gain over the basket is above zero, its signal changed the portfolio in at least 30 months, it still gains at 2.10% per side, and it has at least 24 months of positive live results.

| Experiment | Return a year | Gain over basket | 95% range | Signal months | Gain at 2.10% | Live months | Status |
|---|---|---|---|---|---|---|---|
| Covered basket with Buy stocks at double weight | 12.8% | 0.0 points | -0.4 points to +0.6 points | 15 | -0.1 points | 0 | Not adopted (0 of 4 checks met) |
| Covered basket without stocks priced above their high fair value | 17.3% | +3.7 points | -6.9 points to +13.6 points | 89 | +3.3 points | 0 | Not adopted (2 of 4 checks met) |
| Buy rule that keeps a stock until it reaches its base fair value | 23.7% | +8.0 points | -5.1 points to +21.0 points | 30 | +7.7 points | 0 | Not adopted (2 of 4 checks met) |
| Buy-stock tilt, rebalanced every three months | 12.7% | -0.1 points | -0.4 points to +0.2 points | 2 | -0.1 points | 0 | Not adopted (0 of 4 checks met) |

Both halves of this history have already been seen, so a split-half result could only veto a rule. The live shadow log is the only untouched test: it starts with the first verified daily brief after this change.

## Limitations

- Cash earned between 5.3% (2020-09-01) and 14.2% (2024-04-01) a year after tax. Each month uses the previous month's CBK figure.
- The 10-year bond yield, risk premiums and taxes are today's values, so valuations stay provisional until dated versions are sourced.
- The universe is today's 16 covered stocks, so delisted and failed counters are missing (survivorship bias). The NASI check above bounds the effect on the size-weighted basket.
- Size weights use full market value from published share counts, not free float, so majority-owned companies weigh more than an index fund could hold. Share counts for DTK, EQTY, IMH, KCB were backfilled from their earliest sourced filing for months before it, rebased for bonus issues and splits.
- 89 of 144 fundamentals periods use the CMA filing deadline as their publication date. That is later than the real release for companies that report early, but it is look-ahead for any company that filed late. 53 period(s) with a stated release date, including known late filings, use that date instead.
- Liquidity and suspension screens are off because historical volume and suspension data are not stored.
- Small trades can cost more than the base rate, and whole-share rounding is ignored after the start.
- 89 months of one market make every figure noisy. Treat them as a sanity check, not a forecast.

## Holdings by month

| Month | Buys | Buy rule | Size-weighted | Equal | NASI | Cash rate | Hurdle |
|---|---|---|---|---|---|---|---|
| 2026-10-01 | cash | 0.6% | -6.4% | -4.6% | -3.0% | 7.45% | 12.70% |
| 2026-09-01 | cash | 0.6% | -2.1% | -0.7% | -2.3% | 7.46% | 12.68% |
| 2026-08-01 | cash | -1.2% | 8.0% | 8.3% | 5.7% | 7.48% | 12.67% |
| 2026-07-01 | EQTY | 5.2% | 5.4% | 4.5% | 6.1% | 7.36% | 12.52% |
| 2026-06-01 | EQTY | 9.1% | 10.5% | 9.4% | 9.0% | 7.00% | 12.26% |
| 2026-05-01 | cash | 0.5% | 2.8% | 2.0% | 0.2% | 6.38% | 12.03% |
| 2026-04-01 | cash | 0.5% | 5.6% | 4.2% | 5.4% | 6.41% | 12.23% |
| 2026-03-01 | cash | 0.5% | -10.0% | -6.7% | -9.8% | 6.48% | 12.71% |
| 2026-02-01 | cash | 0.5% | 11.8% | 12.7% | 10.6% | 6.56% | 12.82% |
| 2026-01-01 | cash | 0.6% | 4.4% | 5.6% | 4.7% | 6.60% | 12.89% |
| 2025-12-01 | cash | 0.6% | 3.4% | 5.5% | 3.0% | 6.62% | 12.96% |
| 2025-11-01 | cash | 0.6% | -3.7% | -3.0% | -3.8% | 6.70% | 13.00% |
| 2025-10-01 | cash | 0.6% | 6.6% | 8.5% | 6.5% | 6.77% | 13.12% |
| 2025-09-01 | cash | -1.3% | 3.5% | 4.6% | 2.4% | 6.84% | 13.20% |
| 2025-08-01 | COOP | 4.6% | 9.5% | 12.3% | 7.7% | 6.91% | 13.26% |
| 2025-07-01 | cash | -1.2% | 2.8% | 3.7% | 4.4% | 6.98% | 13.36% |
| 2025-06-01 | COOP | 13.2% | 17.9% | 13.5% | 14.3% | 7.11% | 13.51% |
| 2025-05-01 | COOP | 5.7% | 10.1% | 6.9% | 6.4% | 7.23% | 13.65% |
| 2025-04-01 | cash | 0.6% | -3.3% | -1.8% | -3.6% | 7.55% | 13.90% |
| 2025-03-01 | cash | 0.6% | 1.2% | -1.4% | -1.0% | 7.77% | 14.18% |
| 2025-02-01 | cash | 0.7% | 4.8% | 5.4% | 3.0% | 8.19% | 14.63% |
| 2025-01-01 | cash | 0.7% | 0.9% | 4.5% | 3.9% | 8.77% | 15.06% |
| 2024-12-01 | cash | 0.9% | 12.4% | 12.9% | 10.7% | 11.10% | 17.04% |
| 2024-11-01 | cash | 1.1% | -5.4% | -1.7% | -5.2% | 12.72% | 18.69% |
| 2024-10-01 | cash | 1.1% | 10.7% | 10.2% | 9.8% | 13.39% | 19.30% |
| 2024-09-01 | cash | 1.1% | 5.0% | 11.3% | 3.3% | 13.47% | 19.36% |
| 2024-08-01 | cash | 1.1% | -0.7% | 3.7% | -1.9% | 13.60% | 19.33% |
| 2024-07-01 | cash | -0.7% | -4.1% | -0.9% | -3.4% | 13.57% | 19.23% |
| 2024-06-01 | SBIC | 2.0% | -3.1% | -1.5% | -3.1% | 13.52% | 19.06% |
| 2024-05-01 | cash | 1.1% | 9.4% | 6.5% | 6.0% | 13.74% | 19.20% |
| 2024-04-01 | cash | 1.2% | -5.2% | -2.3% | -5.8% | 14.18% | 19.43% |
| 2024-03-01 | cash | -0.7% | 24.9% | 15.9% | 22.3% | 14.03% | 19.31% |
| 2024-02-01 | COOP | 5.8% | 2.5% | 4.4% | 0.3% | 13.72% | 18.91% |
| 2024-01-01 | COOP, EQTY | 7.1% | -0.5% | 0.3% | 0.1% | 13.34% | 18.44% |
| 2023-12-01 | COOP | 0.0% | -0.3% | 1.4% | 0.2% | 13.02% | 18.19% |
| 2023-11-01 | COOP | -4.0% | 5.1% | -0.3% | 3.8% | 12.72% | 17.97% |
| 2023-10-01 | COOP, EQTY | -0.2% | -8.3% | -2.8% | -7.0% | 12.22% | 17.26% |
| 2023-09-01 | COOP | -0.4% | -2.9% | -1.5% | -4.0% | 11.26% | 16.52% |
| 2023-08-01 | COOP | -0.8% | -8.9% | -4.8% | -5.9% | 10.30% | 15.59% |
| 2023-07-01 | COOP | -2.0% | 1.7% | 2.3% | -1.4% | 9.77% | 14.94% |
| 2023-06-01 | COOP | -1.0% | 3.3% | 2.9% | 3.2% | 8.90% | 14.58% |
| 2023-05-01 | cash | 0.7% | -1.3% | -1.2% | -3.7% | 8.53% | 14.28% |
| 2023-04-01 | cash | 0.7% | -4.8% | -0.8% | -4.5% | 8.30% | 14.14% |
| 2023-03-01 | cash | 0.7% | -10.3% | 0.3% | -10.5% | 8.18% | 14.03% |
| 2023-02-01 | cash | 0.7% | -1.2% | -1.0% | 0.1% | 8.02% | 13.85% |
| 2023-01-01 | cash | 0.7% | 0.2% | 0.2% | -1.2% | 7.93% | 13.73% |
| 2022-12-01 | cash | 0.7% | 0.5% | 3.4% | 0.8% | 7.81% | 13.64% |
| 2022-11-01 | cash | 0.6% | -0.9% | -1.4% | -1.8% | 7.70% | 13.43% |
| 2022-10-01 | cash | 0.6% | 0.4% | 1.2% | 0.3% | 7.58% | 13.41% |
| 2022-09-01 | cash | 0.6% | -6.4% | 0.0% | -6.6% | 7.29% | 13.43% |
| 2022-08-01 | cash | 0.6% | -1.5% | 3.6% | -2.5% | 6.98% | 13.48% |
| 2022-07-01 | cash | 0.6% | 13.8% | 4.5% | 13.3% | 6.71% | 13.47% |
| 2022-06-01 | cash | 0.5% | -2.9% | -1.9% | -3.3% | 6.50% | 13.37% |
| 2022-05-01 | cash | 0.5% | -14.3% | -1.8% | -14.3% | 6.28% | 13.29% |
| 2022-04-01 | cash | 0.5% | -3.0% | -2.3% | -3.6% | 6.16% | 13.30% |
| 2022-03-01 | cash | 0.5% | -1.9% | -0.1% | -2.8% | 6.19% | 13.24% |
| 2022-02-01 | cash | 0.5% | -2.8% | 0.0% | -1.9% | 6.22% | 13.05% |
| 2022-01-01 | cash | 0.5% | -0.8% | -1.1% | -1.9% | 6.17% | 12.76% |
| 2021-12-01 | cash | 0.5% | 2.5% | 3.9% | 1.6% | 6.03% | 11.74% |
| 2021-11-01 | cash | 0.5% | -7.3% | -2.7% | -7.9% | 5.91% | 11.92% |
| 2021-10-01 | cash | 0.5% | -3.2% | -2.7% | -0.2% | 5.81% | 11.60% |
| 2021-09-01 | cash | 0.5% | 0.0% | 0.1% | -2.2% | 5.58% | 11.32% |
| 2021-08-01 | cash | 0.5% | 3.7% | 2.8% | 2.7% | 5.64% | 11.41% |
| 2021-07-01 | cash | 0.5% | 1.4% | 3.9% | 2.3% | 5.98% | 12.15% |
| 2021-06-01 | cash | 0.5% | 2.5% | 2.5% | 2.1% | 6.08% | 12.98% |
| 2021-05-01 | cash | 0.5% | 2.0% | 0.4% | 0.5% | 6.03% | 12.97% |
| 2021-04-01 | cash | 0.5% | 5.7% | -0.9% | 6.6% | 5.98% | 12.77% |
| 2021-03-01 | cash | 0.5% | -2.2% | -1.8% | -4.1% | 5.87% | 12.45% |
| 2021-02-01 | cash | 0.5% | 8.0% | 2.9% | 6.3% | 5.88% | 12.16% |
| 2021-01-01 | cash | 0.5% | 1.2% | -1.3% | 2.3% | 5.87% | 12.03% |
| 2020-12-01 | cash | 0.5% | 5.2% | 5.6% | 4.8% | 5.69% | 11.83% |
| 2020-11-01 | cash | 0.5% | 3.4% | 2.4% | 3.7% | 5.52% | 11.62% |
| 2020-10-01 | cash | 0.4% | 0.2% | -1.9% | 0.1% | 5.35% | 11.46% |
| 2020-09-01 | cash | 0.4% | -0.5% | -1.1% | 0.2% | 5.27% | 11.36% |
| 2020-08-01 | cash | 0.4% | 9.0% | 2.7% | 4.8% | 5.30% | 11.44% |
| 2020-07-01 | cash | 0.5% | -3.3% | -4.5% | -3.2% | 6.07% | 12.52% |
| 2020-06-01 | cash | 0.5% | 0.2% | 0.9% | 0.4% | 6.18% | 12.79% |
| 2020-05-01 | cash | 0.5% | -1.8% | -4.1% | -1.8% | 6.13% | 12.71% |
| 2020-04-01 | cash | 0.5% | 6.2% | 3.7% | 5.9% | 6.20% | 12.82% |
| 2020-03-01 | cash | 0.5% | -10.2% | -13.6% | -11.2% | 6.21% | 13.37% |
| 2020-02-01 | cash | 0.5% | -8.2% | -6.6% | -8.3% | 6.15% | 13.39% |
| 2020-01-01 | cash | 0.5% | -2.5% | -0.6% | -2.6% | 6.09% | 13.33% |
| 2019-12-01 | cash | 0.5% | 5.8% | 1.5% | 5.4% | 5.65% | 13.32% |
| 2019-11-01 | cash | 0.5% | -3.9% | -4.5% | -1.0% | 5.61% | 13.59% |
| 2019-10-01 | cash | 0.5% | 13.9% | 14.4% | 9.7% | 5.58% | 13.29% |
| 2019-09-01 | cash | 0.5% | -1.3% | -0.7% | -1.4% | 5.65% | 12.90% |
| 2019-08-01 | cash | 0.5% | 0.4% | -2.4% | -0.5% | 5.63% | 12.51% |
| 2019-07-01 | cash | 0.5% | -0.8% | -0.2% | -0.9% | 5.87% | 12.85% |
| 2019-06-01 | cash | 0.5% | -0.7% | -0.7% | -0.2% | 6.09% | 12.92% |
