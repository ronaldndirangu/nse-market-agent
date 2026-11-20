# Monte Carlo simulation

> **Not financial advice.** This report is generated automatically from public data and fixed rules. It is not financial advice, an offer, or a recommendation to buy or sell any security. Figures can be wrong or stale. Verify everything against company filings and consult a licensed adviser before investing.

Basket (top 3 ranked (no undervalued picks this week)): **EQTY, IMH, KPLC**, equal weight, as of 2026-11-20.

Weekly basket returns from 2016-W49 to 2026-W47 (520 weeks) are resampled in 4-week blocks to keep short-term momentum and volatility clustering. Each path adds the basket's net dividend yield (5.5%) and one round trip of trading costs. Results are annualised.

- **History:** repeats the basket's own past drift and volatility.
- **Valuation-anchored:** keeps the historical volatility but centres the drift on the engine's base projection (11.1% a year).
- Net 364-day T-bill: 7.65%.

| Model | Horizon | P5 | P25 | Median | P75 | P95 | P(beat T-bill) | P(loss) |
|---|---|---|---|---|---|---|---|---|
| History | 1y | -23.5% | -2.0% | 17.5% | 41.6% | 84.9% | 63% | 28% |
| History | 3y | -6.3% | 9.0% | 20.9% | 33.8% | 55.9% | 77% | 12% |
| History | 5y | -0.4% | 12.0% | 21.6% | 31.8% | 48.3% | 84% | 5% |
| Valuation-anchored | 1y | -29.4% | -9.6% | 8.5% | 30.7% | 70.7% | 51% | 38% |
| Valuation-anchored | 3y | -13.6% | 0.6% | 11.6% | 23.5% | 43.8% | 59% | 24% |
| Valuation-anchored | 5y | -8.1% | 3.4% | 12.2% | 21.6% | 36.9% | 64% | 17% |

## Stress tests

| Window | Dates | Basket | Universe |
|---|---|---|---|
| 2016 rate cap shock | 2016-08-01 to 2016-12-31 | n/a | n/a |
| COVID crash | 2020-02-01 to 2020-04-30 | -19.9% | -16.2% |
| 2023 sell-off | 2023-01-01 to 2023-12-31 | -3.1% | -3.5% |

Worst historical stretches for this basket (split-adjusted prices, dividends excluded):

- 4 weeks starting 2020-W09: -22.8%
- 13 weeks starting 2020-W02: -31.2%
- 52 weeks starting 2017-W48: -39.8%

## Limitations

- The past is resampled, so regimes that never happened in the sample cannot appear.
- Stress returns add dividends net of withholding tax and use today's basket, not what the engine would have picked then.
- Dividends are assumed constant at the current net yield.
