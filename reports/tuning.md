# Weight tuning

> **Not financial advice.** This report is generated automatically from public data and fixed rules. It is not financial advice, an offer, or a recommendation to buy or sell any security. Figures can be wrong or stale. Verify everything against company filings and consult a licensed adviser before investing.

Generated 2026-11-11. Prices through 2026-11-11. 117 reconstructed month starts (first 2017-03-01), 286 candidate weightings.

**Proposed weights: margin of safety 0.1, quality 0.2, momentum 0.4, dividend yield 0.3. Walk-forward selection beat the current weights out of sample on both rank IC and top-5 excess return at every evaluated horizon.**

Current weights: margin of safety 0.5, quality 0.3, momentum 0.2. Selected on all matured data: margin of safety 0.1, quality 0.2, momentum 0.4, dividend yield 0.3.

## Method

Candidates split a weight of 1 across margin of safety, quality, momentum, dividend yield in steps of 0.1, plus the current weights. On each month start, the tuner picks the candidate with the best mean 3-month rank IC over windows that had fully ended by that date (at least 6), then ranks that month's stored point-in-time z-scores with it. Ties go to the candidate closest to the current weights. Every result below is out of sample: the weights were chosen before the window started.

The weights change only through a reviewed pull request, and only when walk-forward selection beats the current weights on both rank IC and top-5 excess return at every evaluated horizon.

## Out-of-sample results

| Horizon | Weights | Windows | Top 5 | Universe (EW) | Excess | Hit rate | Rank IC |
|---|---|---|---|---|---|---|---|
| 3m | current weights | 106 | 5.9% | 4.5% | 1.4% | 50% | +0.075 |
| 3m | walk-forward | 106 | 6.4% | 4.5% | 1.9% | 53% | +0.147 |
| 12m | current weights | 97 | 23.4% | 20.2% | 3.1% | 54% | +0.094 |
| 12m | walk-forward | 97 | 25.8% | 20.2% | 5.6% | 60% | +0.232 |

## Weights chosen over time

| From | Training windows | Weights |
|---|---|---|
| 2017-11-01 | 6 | margin of safety 0.5, quality 0.3, momentum 0.2 |
| 2018-02-01 | 9 | margin of safety 0.3, quality 0.5, momentum 0.2 |
| 2018-03-01 | 10 | quality 0.5, momentum 0.4, dividend yield 0.1 |
| 2018-04-01 | 11 | quality 0.6, momentum 0.3, dividend yield 0.1 |
| 2018-05-01 | 12 | quality 0.5, momentum 0.4, dividend yield 0.1 |
| 2018-07-01 | 14 | quality 0.4, momentum 0.5, dividend yield 0.1 |
| 2018-11-01 | 18 | quality 0.2, momentum 0.3, dividend yield 0.5 |
| 2018-12-01 | 19 | margin of safety 0.1, quality 0.4, momentum 0.2, dividend yield 0.3 |
| 2019-01-01 | 20 | quality 0.2, momentum 0.4, dividend yield 0.4 |
| 2019-02-01 | 21 | quality 0.2, momentum 0.3, dividend yield 0.5 |
| 2019-03-01 | 22 | quality 0.2, momentum 0.4, dividend yield 0.4 |
| 2019-04-01 | 23 | quality 0.2, momentum 0.5, dividend yield 0.3 |
| 2020-10-01 | 41 | quality 0.2, momentum 0.4, dividend yield 0.4 |
| 2021-07-01 | 50 | quality 0.2, momentum 0.5, dividend yield 0.3 |
| 2021-11-01 | 54 | quality 0.3, momentum 0.5, dividend yield 0.2 |
| 2024-02-01 | 81 | margin of safety 0.1, quality 0.2, momentum 0.4, dividend yield 0.3 |
| 2024-04-01 | 83 | margin of safety 0.1, quality 0.3, momentum 0.4, dividend yield 0.2 |
| 2024-05-01 | 84 | margin of safety 0.1, quality 0.2, momentum 0.4, dividend yield 0.3 |
| 2024-07-01 | 86 | margin of safety 0.1, quality 0.3, momentum 0.4, dividend yield 0.2 |
| 2024-08-01 | 87 | quality 0.3, momentum 0.5, dividend yield 0.2 |
| 2024-09-01 | 88 | margin of safety 0.1, quality 0.2, momentum 0.4, dividend yield 0.3 |
| 2024-12-01 | 91 | margin of safety 0.1, quality 0.3, momentum 0.5, dividend yield 0.1 |
| 2025-02-01 | 93 | margin of safety 0.1, quality 0.3, momentum 0.4, dividend yield 0.2 |
| 2025-04-01 | 95 | margin of safety 0.1, quality 0.2, momentum 0.4, dividend yield 0.3 |
| 2025-11-01 | 102 | margin of safety 0.1, quality 0.3, momentum 0.4, dividend yield 0.2 |
| 2026-02-01 | 105 | margin of safety 0.1, quality 0.2, momentum 0.4, dividend yield 0.3 |

## Limitations

- Monthly windows overlap at the 3 and 12-month horizons, so they are not independent observations.
- Point-in-time fundamentals are short until the backfill PRs are merged, so the sample is small and covers one market regime. Rerun after merging them.
- The universe is 16 stocks; one month's IC is noisy.
