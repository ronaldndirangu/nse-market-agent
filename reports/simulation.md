# Monte Carlo simulation

> **Not financial advice.** This report is generated automatically from public data and fixed rules. It is not financial advice, an offer, or a recommendation to buy or sell any security. Figures can be wrong or stale. Verify everything against company filings and consult a licensed adviser before investing.

Basket (top 3 ranked (no undervalued picks this week)): **IMH, EQTY, KPLC**, equal weight, as of 2026-11-27.

Weekly basket returns from 2016-W50 to 2026-W48 (520 weeks) are resampled in 4-week blocks to keep short-term momentum and volatility clustering. Each path adds the basket's net dividend yield (5.6%) and one round trip of trading costs. Results are annualised.

- **History:** repeats the basket's own past drift and volatility.
- **Valuation-anchored:** keeps the historical volatility but centres the drift on the engine's base projection (11.7% a year).
- Net 364-day T-bill: 7.64%.

| Model | Horizon | P5 | P25 | Median | P75 | P95 | P(beat T-bill) | P(loss) |
|---|---|---|---|---|---|---|---|---|
| History | 1y | -22.9% | -1.5% | 17.8% | 42.4% | 85.5% | 64% | 27% |
| History | 3y | -6.0% | 8.8% | 21.0% | 33.9% | 55.7% | 77% | 11% |
| History | 5y | 0.1% | 12.4% | 21.8% | 32.4% | 48.8% | 85% | 5% |
| Valuation-anchored | 1y | -28.4% | -8.6% | 9.3% | 32.2% | 72.2% | 52% | 37% |
| Valuation-anchored | 3y | -12.7% | 1.0% | 12.3% | 24.4% | 44.6% | 61% | 23% |
| Valuation-anchored | 5y | -7.1% | 4.4% | 13.1% | 22.9% | 38.2% | 67% | 15% |

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
