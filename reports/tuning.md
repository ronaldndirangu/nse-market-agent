# Weight tuning

> **Not financial advice.** This report is generated automatically from public data and fixed rules. It is not financial advice, an offer, or a recommendation to buy or sell any security. Figures can be wrong or stale. Verify everything against company filings and consult a licensed adviser before investing.

Generated 2026-11-11. Prices through 2026-11-11. 31 reconstructed month starts (first 2024-05-01), 286 candidate weightings.

**Keep the current weights. The tuner would pick margin of safety 0.8, momentum 0.1, dividend yield 0.1 on all matured data, but walk-forward selection did not beat the current weights out of sample on both rank IC and excess return at every horizon, so the evidence does not support a change.**

Current weights: margin of safety 0.5, quality 0.3, momentum 0.2. Selected on all matured data: margin of safety 0.8, momentum 0.1, dividend yield 0.1.

## Method

Candidates split a weight of 1 across margin of safety, quality, momentum, dividend yield in steps of 0.1, plus the current weights. On each month start, the tuner picks the candidate with the best mean 3-month rank IC over windows that had fully ended by that date (at least 6), then ranks that month's stored point-in-time z-scores with it. Ties go to the candidate closest to the current weights. Every result below is out of sample: the weights were chosen before the window started.

The weights change only through a reviewed pull request, and only when walk-forward selection beats the current weights on both rank IC and top-5 excess return at every evaluated horizon.

## Out-of-sample results

| Horizon | Weights | Windows | Top 5 | Universe (EW) | Excess | Hit rate | Rank IC |
|---|---|---|---|---|---|---|---|
| 3m | current weights | 20 | 17.5% | 14.5% | 3.1% | 50% | +0.134 |
| 3m | walk-forward | 20 | 17.7% | 14.5% | 3.2% | 52% | +0.167 |
| 12m | current weights | 11 | 86.8% | 71.3% | 15.5% | 71% | +0.395 |
| 12m | walk-forward | 11 | 77.8% | 71.3% | 6.5% | 58% | +0.302 |

## Weights chosen over time

| From | Training windows | Weights |
|---|---|---|
| 2025-01-01 | 6 | margin of safety 0.4, momentum 0.4, dividend yield 0.2 |
| 2025-12-01 | 17 | margin of safety 0.6, momentum 0.3, dividend yield 0.1 |
| 2026-03-01 | 20 | margin of safety 0.7, momentum 0.2, dividend yield 0.1 |
| 2026-04-01 | 21 | margin of safety 0.8, momentum 0.1, dividend yield 0.1 |

## Limitations

- Monthly windows overlap at the 3 and 12-month horizons, so they are not independent observations.
- Point-in-time fundamentals are short until the backfill PRs are merged, so the sample is small and covers one market regime. Rerun after merging them.
- The universe is 16 stocks; one month's IC is noisy.
