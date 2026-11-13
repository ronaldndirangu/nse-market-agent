# Monte Carlo simulation

> **Not financial advice.** This report is generated automatically from public data and fixed rules. It is not financial advice, an offer, or a recommendation to buy or sell any security. Figures can be wrong or stale. Verify everything against company filings and consult a licensed adviser before investing.

Basket (top 3 ranked (no undervalued picks this week)): **IMH, KPLC, KEGN**, equal weight, as of 2026-11-13.

Weekly basket returns from 2016-W48 to 2026-W46 (520 weeks) are resampled in 4-week blocks to keep short-term momentum and volatility clustering. Each path adds the basket's net dividend yield (6.0%) and one round trip of trading costs. Results are annualised.

- **History:** repeats the basket's own past drift and volatility.
- **Valuation-anchored:** keeps the historical volatility but centres the drift on the engine's base projection (3.0% a year).
- Net 364-day T-bill: 7.66%.

| Model | Horizon | P5 | P25 | Median | P75 | P95 | P(beat T-bill) | P(loss) |
|---|---|---|---|---|---|---|---|---|
| History | 1y | -25.1% | -4.1% | 13.8% | 37.8% | 83.1% | 58% | 31% |
| History | 3y | -7.8% | 6.9% | 18.1% | 31.5% | 53.2% | 74% | 14% |
| History | 5y | -2.2% | 9.7% | 19.1% | 29.0% | 45.8% | 79% | 7% |
| Valuation-anchored | 1y | -34.7% | -16.5% | -0.8% | 20.0% | 59.5% | 38% | 51% |
| Valuation-anchored | 3y | -19.6% | -6.8% | 2.9% | 14.6% | 33.5% | 38% | 43% |
| Valuation-anchored | 5y | -14.8% | -4.4% | 3.8% | 12.4% | 27.1% | 37% | 38% |

## Stress tests

| Window | Dates | Basket | Universe |
|---|---|---|---|
| 2016 rate cap shock | 2016-08-01 to 2016-12-31 | n/a | n/a |
| COVID crash | 2020-02-01 to 2020-04-30 | -17.8% | -16.2% |
| 2023 sell-off | 2023-01-01 to 2023-12-31 | -5.4% | -3.5% |

Worst historical stretches for this basket (split-adjusted prices, dividends excluded):

- 4 weeks starting 2020-W09: -21.3%
- 13 weeks starting 2020-W02: -24.2%
- 52 weeks starting 2017-W48: -42.9%

## Limitations

- The past is resampled, so regimes that never happened in the sample cannot appear.
- Stress returns add dividends net of withholding tax and use today's basket, not what the engine would have picked then.
- Dividends are assumed constant at the current net yield.
