# Monte Carlo simulation

> **Not financial advice.** This report is generated automatically from public data and fixed rules. It is not financial advice, an offer, or a recommendation to buy or sell any security. Figures can be wrong or stale. Verify everything against company filings and consult a licensed adviser before investing.

Basket (top 3 ranked (no undervalued picks this week)): **KPLC, KCB, EQTY**, equal weight, as of 2026-11-11.

Weekly basket returns from 2016-W48 to 2026-W46 (520 weeks) are resampled in 4-week blocks to keep short-term momentum and volatility clustering. Each path adds the basket's net dividend yield (6.5%) and one round trip of trading costs. Results are annualised.

- **History:** repeats the basket's own past drift and volatility.
- **Valuation-anchored:** keeps the historical volatility but centres the drift on the engine's base projection (18.6% a year).
- Net 364-day T-bill: 7.67%.

| Model | Horizon | P5 | P25 | Median | P75 | P95 | P(beat T-bill) | P(loss) |
|---|---|---|---|---|---|---|---|---|
| History | 1y | -27.0% | -2.9% | 17.4% | 41.8% | 88.4% | 63% | 28% |
| History | 3y | -7.8% | 8.1% | 21.0% | 34.9% | 58.1% | 76% | 13% |
| History | 5y | -1.5% | 11.0% | 21.1% | 32.1% | 49.7% | 83% | 6% |
| Valuation-anchored | 1y | -27.8% | -4.0% | 16.1% | 40.3% | 86.4% | 61% | 29% |
| Valuation-anchored | 3y | -8.8% | 6.9% | 19.7% | 33.4% | 56.4% | 73% | 14% |
| Valuation-anchored | 5y | -2.6% | 9.8% | 19.8% | 30.7% | 48.1% | 80% | 7% |

## Stress tests

| Window | Dates | Basket | Universe |
|---|---|---|---|
| 2016 rate cap shock | 2016-08-01 to 2016-12-31 | n/a | n/a |
| COVID crash | 2020-02-01 to 2020-04-30 | -27.4% | -17.4% |
| 2023 sell-off | 2023-01-01 to 2023-12-31 | -25.3% | -12.6% |

Worst historical stretches for this basket (price-only):

- 4 weeks starting 2020-W11: -27.0%
- 13 weeks starting 2020-W02: -39.1%
- 52 weeks starting 2019-W50: -37.8%

## Limitations

- The past is resampled, so regimes that never happened in the sample cannot appear.
- Stress returns are price-only and use today's basket, not what the engine would have picked then.
- Dividends are assumed constant at the current net yield.
