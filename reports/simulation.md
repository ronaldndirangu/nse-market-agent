# Monte Carlo simulation

> **Not financial advice.** This report is generated automatically from public data and fixed rules. It is not financial advice, an offer, or a recommendation to buy or sell any security. Figures can be wrong or stale. Verify everything against company filings and consult a licensed adviser before investing.

Basket (top 3 ranked (no undervalued picks this week)): **KPLC, EABL, BAT**, equal weight, as of 2026-11-11.

Weekly basket returns from 2016-W48 to 2026-W46 (520 weeks) are resampled in 4-week blocks to keep short-term momentum and volatility clustering. Each path adds the basket's net dividend yield (7.7%) and one round trip of trading costs. Results are annualised.

- **History:** repeats the basket's own past drift and volatility.
- **Valuation-anchored:** keeps the historical volatility but centres the drift on the engine's base projection (1.1% a year).
- Net 364-day T-bill: 7.67%.

| Model | Horizon | P5 | P25 | Median | P75 | P95 | P(beat T-bill) | P(loss) |
|---|---|---|---|---|---|---|---|---|
| History | 1y | -24.8% | -5.5% | 9.2% | 27.1% | 59.8% | 53% | 34% |
| History | 3y | -9.0% | 2.8% | 12.8% | 22.8% | 39.3% | 63% | 19% |
| History | 5y | -4.8% | 5.2% | 13.0% | 21.0% | 34.4% | 68% | 12% |
| Valuation-anchored | 1y | -32.5% | -15.2% | -2.0% | 14.0% | 43.4% | 33% | 54% |
| Valuation-anchored | 3y | -18.4% | -7.8% | 1.2% | 10.2% | 24.9% | 32% | 46% |
| Valuation-anchored | 5y | -14.6% | -5.6% | 1.4% | 8.6% | 20.6% | 27% | 45% |

## Stress tests

| Window | Dates | Basket | Universe |
|---|---|---|---|
| 2016 rate cap shock | 2016-08-01 to 2016-12-31 | n/a | n/a |
| COVID crash | 2020-02-01 to 2020-04-30 | -27.4% | -17.4% |
| 2023 sell-off | 2023-01-01 to 2023-12-31 | -17.4% | -12.6% |

Worst historical stretches for this basket (price-only):

- 4 weeks starting 2020-W10: -26.8%
- 13 weeks starting 2020-W03: -30.5%
- 52 weeks starting 2017-W47: -44.5%

## Limitations

- The past is resampled, so regimes that never happened in the sample cannot appear.
- Stress returns are price-only and use today's basket, not what the engine would have picked then.
- Dividends are assumed constant at the current net yield.
