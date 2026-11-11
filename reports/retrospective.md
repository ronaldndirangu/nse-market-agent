# Retrospective

> **Not financial advice.** This report is generated automatically from public data and fixed rules. It is not financial advice, an offer, or a recommendation to buy or sell any security. Figures can be wrong or stale. Verify everything against company filings and consult a licensed adviser before investing.

Generated 2026-11-11. Prices through 2026-11-11. Reconstructed rankings cover 117 month starts (first 2017-03-01); the live ledger covers 1 days (first 2026-11-11).

## Forward scorecard

Each ranking date, the top 5 by composite score is held for 1, 3, 6 and 12 months and compared with the equal-weight universe and NASI on total return. Hit rate is the share of top-5 picks that beat the equal-weight universe. Rank IC is the Spearman correlation between composite score and forward return across all ranked stocks. Inside bear-bull is the share of outcomes inside the projected range (target about 80%).

### Live ledger (daily)

No live window has matured yet. The first 1-month results are due on 2026-12-11.

### Reconstructed (monthly, point in time)

| Horizon | Windows | Top 5 | Universe (EW) | NASI | Excess | Hit rate | Rank IC | Inside bear-bull |
|---|---|---|---|---|---|---|---|---|
| 1m | 116 | 1.7% | 1.6% | 0.7% | 0.1% | 50% | +0.074 | 12% (38% below, 50% above, n=1472) |
| 3m | 114 | 5.9% | 4.9% | 2.2% | 1.0% | 49% | +0.090 | 19% (28% below, 53% above, n=1440) |
| 6m | 111 | 11.8% | 9.8% | 4.0% | 2.1% | 53% | +0.084 | 23% (21% below, 56% above, n=1392) |
| 12m | 105 | 24.2% | 20.3% | 7.2% | 3.9% | 55% | +0.094 | 27% (16% below, 57% above, n=1296) |

## Per-signal rank IC

Mean monthly Spearman IC between each signal and the forward total return, with the share of months where IC was positive. Price signals use the full price history; valuation and quality signals need point-in-time fundamentals, so they cover fewer months.

| Signal | Source | 1m | 3m | 6m | 12m |
|---|---|---|---|---|---|
| margin_of_safety | reconstructed ledger | +0.040 (50% > 0, n=115) | +0.064 (55% > 0, n=113) | +0.058 (55% > 0, n=110) | +0.055 (58% > 0, n=104) |
| quality | reconstructed ledger | +0.083 (59% > 0, n=108) | +0.079 (63% > 0, n=106) | +0.099 (58% > 0, n=103) | +0.145 (69% > 0, n=97) |
| momentum | prices | +0.087 (64% > 0, n=107) | +0.109 (63% > 0, n=105) | +0.130 (65% > 0, n=102) | +0.186 (76% > 0, n=96) |
| dividend_yield | prices | +0.074 (61% > 0, n=119) | +0.126 (64% > 0, n=117) | +0.170 (68% > 0, n=114) | +0.241 (74% > 0, n=108) |
| low_volatility | prices | +0.028 (52% > 0, n=113) | +0.034 (50% > 0, n=111) | +0.037 (56% > 0, n=108) | +0.016 (56% > 0, n=102) |
| composite | reconstructed ledger | +0.074 (57% > 0, n=115) | +0.090 (58% > 0, n=113) | +0.084 (57% > 0, n=110) | +0.094 (63% > 0, n=104) |

## Reverse attribution

Each month start, the 5 best actual total returns over the next 3, 6 and 12 months, against the rank the point-in-time engine gave them. Misses are classified in order: event (corporate action or a one-day move over 25%), missing data, turnaround (a recent loss), macro (over 70% of the universe moved more than 10% the same way), then signal miss.

### Miss classification

| Horizon | Winners | Caught (top 5) | Event | Missing data | Turnaround | Macro | Signal miss |
|---|---|---|---|---|---|---|---|
| 3m | 585 | 211 | 16 | 120 | 13 | 28 | 197 |
| 6m | 570 | 211 | 31 | 98 | 10 | 73 | 147 |
| 12m | 540 | 211 | 50 | 77 | 3 | 60 | 139 |

### Signals that flagged the winners

Share of actual winners with a positive z-score on each signal at the start date, among winners where the signal could be computed (n). About 50% is no better than chance.

| Signal | 3m | 6m | 12m |
|---|---|---|---|
| margin_of_safety | 40% (n=457) | 39% (n=458) | 38% (n=440) |
| quality | 53% (n=457) | 58% (n=458) | 60% (n=440) |
| momentum | 48% (n=585) | 45% (n=570) | 48% (n=540) |
| dividend_yield | 48% (n=585) | 53% (n=570) | 60% (n=540) |
| low_volatility | 55% (n=585) | 55% (n=570) | 55% (n=540) |

### Latest winners

**3-month windows**

| Start | Ticker | Return | Rank given | Signals flagged | Class | Why |
|---|---|---|---|---|---|---|
| 2026-06-01 | IMH | 57.6% | 8 of 16 | margin_of_safety, low_volatility | macro | over 70% of the universe moved more than 10% the same way |
| 2026-06-01 | KPLC | 46.1% | 5 of 16 | margin_of_safety, momentum | caught | ranked 5 of 16 |
| 2026-06-01 | CARB | 44.1% | 12 of 16 | quality, low_volatility | macro | over 70% of the universe moved more than 10% the same way |
| 2026-06-01 | KCB | 42.7% | 1 of 16 | margin_of_safety, quality, dividend_yield, low_volatility | caught | ranked 1 of 16 |
| 2026-06-01 | DTK | 31.9% | 4 of 16 | margin_of_safety, quality, momentum, low_volatility | caught | ranked 4 of 16 |
| 2026-07-01 | KPLC | 32.9% | 7 of 16 | margin_of_safety, momentum | signal miss | ranked outside the top 5 on available signals |
| 2026-07-01 | DTK | 30.3% | 3 of 16 | margin_of_safety, quality, momentum, low_volatility | caught | ranked 3 of 16 |
| 2026-07-01 | CARB | 28.5% | 12 of 16 | quality | signal miss | ranked outside the top 5 on available signals |
| 2026-07-01 | EQTY | 27.3% | 1 of 16 | margin_of_safety, quality, momentum, low_volatility | caught | ranked 1 of 16 |
| 2026-07-01 | KCB | 20.4% | 2 of 16 | margin_of_safety, quality, dividend_yield | caught | ranked 2 of 16 |
| 2026-08-01 | IMH | 19.9% | 5 of 16 | momentum, low_volatility | caught | ranked 5 of 16 |
| 2026-08-01 | CARB | 18.6% | 11 of 16 | quality | signal miss | ranked outside the top 5 on available signals |
| 2026-08-01 | DTK | 17.5% | 4 of 16 | margin_of_safety, quality, momentum, low_volatility | caught | ranked 4 of 16 |
| 2026-08-01 | EQTY | 9.5% | 1 of 16 | margin_of_safety, quality, momentum, low_volatility | caught | ranked 1 of 16 |
| 2026-08-01 | TOTL | 5.4% | 15 of 16 | momentum, dividend_yield | signal miss | ranked outside the top 5 on available signals |

**6-month windows**

| Start | Ticker | Return | Rank given | Signals flagged | Class | Why |
|---|---|---|---|---|---|---|
| 2026-03-01 | IMH | 61.1% | 11 of 16 | margin_of_safety, low_volatility | macro | over 70% of the universe moved more than 10% the same way |
| 2026-03-01 | CARB | 40.1% | 10 of 16 | quality, momentum, low_volatility | macro | over 70% of the universe moved more than 10% the same way |
| 2026-03-01 | COOP | 31.8% | 8 of 16 | margin_of_safety, momentum, dividend_yield, low_volatility | macro | over 70% of the universe moved more than 10% the same way |
| 2026-03-01 | EQTY | 31.7% | 6 of 16 | margin_of_safety, low_volatility | macro | over 70% of the universe moved more than 10% the same way |
| 2026-03-01 | DTK | 31.1% | 2 of 16 | margin_of_safety, quality, momentum, low_volatility | caught | ranked 2 of 16 |
| 2026-04-01 | IMH | 73.1% | 10 of 16 | margin_of_safety, low_volatility | macro | over 70% of the universe moved more than 10% the same way |
| 2026-04-01 | EQTY | 60.1% | 5 of 16 | margin_of_safety, low_volatility | caught | ranked 5 of 16 |
| 2026-04-01 | CARB | 46.2% | 11 of 16 | quality, low_volatility | macro | over 70% of the universe moved more than 10% the same way |
| 2026-04-01 | KCB | 42.1% | 3 of 16 | margin_of_safety, momentum, dividend_yield | caught | ranked 3 of 16 |
| 2026-04-01 | COOP | 39.4% | 8 of 16 | margin_of_safety, momentum, dividend_yield, low_volatility | macro | over 70% of the universe moved more than 10% the same way |
| 2026-05-01 | IMH | 64.1% | 8 of 16 | margin_of_safety, dividend_yield, low_volatility | signal miss | ranked outside the top 5 on available signals |
| 2026-05-01 | CARB | 40.2% | 10 of 16 | quality, low_volatility | signal miss | ranked outside the top 5 on available signals |
| 2026-05-01 | EQTY | 36.7% | 5 of 16 | margin_of_safety, low_volatility | caught | ranked 5 of 16 |
| 2026-05-01 | KCB | 32.6% | 3 of 16 | margin_of_safety, momentum, dividend_yield | caught | ranked 3 of 16 |
| 2026-05-01 | KPLC | 32.5% | 1 of 16 | margin_of_safety, momentum | caught | ranked 1 of 16 |

**12-month windows**

| Start | Ticker | Return | Rank given | Signals flagged | Class | Why |
|---|---|---|---|---|---|---|
| 2025-09-01 | DTK | 124.7% | 1 of 16 | margin_of_safety, quality, low_volatility | caught | ranked 1 of 16 |
| 2025-09-01 | COOP | 121.5% | 9 of 16 | margin_of_safety, dividend_yield, low_volatility | macro | over 70% of the universe moved more than 10% the same way |
| 2025-09-01 | IMH | 114.0% | 7 of 16 | margin_of_safety, low_volatility | macro | over 70% of the universe moved more than 10% the same way |
| 2025-09-01 | KCB | 87.8% | 2 of 16 | margin_of_safety, low_volatility | caught | ranked 2 of 16 |
| 2025-09-01 | EQTY | 81.6% | 10 of 16 | margin_of_safety, low_volatility | macro | over 70% of the universe moved more than 10% the same way |
| 2025-10-01 | IMH | 99.8% | 8 of 16 | margin_of_safety, low_volatility | macro | over 70% of the universe moved more than 10% the same way |
| 2025-10-01 | EQTY | 90.5% | 9 of 16 | margin_of_safety, low_volatility | macro | over 70% of the universe moved more than 10% the same way |
| 2025-10-01 | DTK | 88.6% | 1 of 16 | margin_of_safety, quality, low_volatility | caught | ranked 1 of 16 |
| 2025-10-01 | COOP | 87.0% | 10 of 16 | margin_of_safety, low_volatility | macro | over 70% of the universe moved more than 10% the same way |
| 2025-10-01 | KCB | 72.9% | 2 of 16 | margin_of_safety, dividend_yield, low_volatility | caught | ranked 2 of 16 |
| 2025-11-01 | IMH | 93.2% | 8 of 16 | margin_of_safety, low_volatility | macro | over 70% of the universe moved more than 10% the same way |
| 2025-11-01 | COOP | 79.5% | 9 of 16 | margin_of_safety, low_volatility | macro | over 70% of the universe moved more than 10% the same way |
| 2025-11-01 | DTK | 78.9% | 2 of 16 | margin_of_safety, quality, momentum, low_volatility | caught | ranked 2 of 16 |
| 2025-11-01 | KPLC | 65.3% | 1 of 16 | margin_of_safety, momentum | caught | ranked 1 of 16 |
| 2025-11-01 | CARB | 56.1% | 13 of 16 | quality | macro | over 70% of the universe moved more than 10% the same way |

## Limitations

- Fundamentals are point in time, but sourced history is short until the backfill lands, so early months rank few stocks and most early misses are missing data.
- Total return adds dividends net of withholding tax without reinvestment and ignores trading costs. Prices are adjusted only for corporate actions recorded in data/corporate_actions.yaml.
- The universe is today's 16 counters, so delisted stocks are missing (survivorship bias).
- Calibration scales annual bear and bull projections to each horizon. The bands are valuation ranges, not price-volatility ranges, so they understate short-term dispersion; the below and above shares show which way outcomes missed. Read the 12-month figure first.
- Daily live windows overlap, so their statistics are not independent observations.
- With 16 stocks, one month's IC is noisy. Judge signals on the share of positive months and N.
