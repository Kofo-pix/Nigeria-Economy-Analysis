# Findings (SAMPLE DATA - NOT OFFICIAL STATISTICS)

> These results were computed from **synthetic sample data** to demonstrate the pipeline. They are not statements about Nigeria.

## What the data shows

- **WARNING: these findings come from SYNTHETIC SAMPLE data and say nothing about Nigeria.**
- Annual inflation peaked at 26.4% in 2024.
- The misery index (inflation + unemployment) was highest in 2024 at 32.9 points.
- Prices rose 15.9x between 2000 and 2024: NGN 100 in 2000 had the purchasing power of NGN 6.3 by 2024.
- Monthly headline inflation peaked at 35.63% in Nov 2024; latest reading 16.60% (Sep 2026).
- Average inflation was 15.9% before Jun 2023 and 26.6% after.
- The official rate moved from 414 to 1,049 NGN/USD, so the naira lost 61% of its USD value since just before the reform date.
- The real policy rate was negative in 90 of 141 months (latest +6.4 pts).
- Data-driven break in mean inflation: May 2021 (14.0% -> 24.7%), explaining 67% of variance.
- FX depreciation and inflation line up most strongly at a 7-month lag (r = 0.60); descriptive, not causal.

## Latest verified official readings (always real; see data/raw/verified_datapoints.csv)

| Indicator | Period | Value | Source |
|---|---|---|---|
| cpi_index | 2026-02 | 130 index | NBS (X post) |
| mpr | 2026-09 | 23 % | CBN decisions page |
| headline_inflation_yoy | 2026-09 | 14.63 % | NBS (via Voice of Nigeria) |
| food_inflation_yoy | 2026-09 | 19.59 % | NBS (X post) |
| headline_inflation_mom | 2026-09 | 0.06 % | NBS (X post) |
| official_fx_ngn_usd | 2026-09 | 1328.67 NGN per USD | Legit.ng (citing CBN) |

### Real policy rate from verified points (MPR minus headline inflation)

| Period | MPR | Inflation | Real rate (pts) |
|---|---|---|---|
| 2026-02 | 26.5 | 15.06 | +11.44 |
| 2026-05 | 26.5 | 15.93 | +10.57 |
| 2026-09 | 23 | 14.63 | +8.37 |

## Notes

- SYNTHETIC sample generated for pipeline testing; values are NOT official statistics.
