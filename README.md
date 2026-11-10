# Nigeria Economic & Inflation Analysis

![CI](https://github.com/YOUR-USERNAME/nigeria-economy-analysis/actions/workflows/ci.yml/badge.svg)

An end-to-end analysis of **inflation, the naira, interest rates, unemployment and growth in Nigeria**:
public-data ingestion, time-series analysis, an **Excel** workbook with live formulas, and a **Power BI**-ready
star schema, wrapped in an economic story.

> **Tools:** Python (pandas, numpy, matplotlib) · Excel (openpyxl, formulas + native charts) · Power BI (star schema, DAX)

## Read this first: what is real and what is sample

| Component | Status |
|---|---|
| `data/raw/verified_datapoints.csv` | **Real.** 28 official readings (inflation, MPR, FX, CPI index), each with a source URL and check date |
| `make fetch` | Downloads **real** annual World Bank indicators (needs internet) |
| `data/raw/manual/monthly.csv` | **You add this** from NBS/CBN (template + instructions in [`docs/data_sources.md`](docs/data_sources.md)) |
| `outputs/sample/` | Built from **synthetic** data to demonstrate the pipeline. Every chart, workbook and CSV is stamped `SAMPLE DATA` / `SYNTHETIC_SAMPLE` |

No sample number is a statement about Nigeria. Switch to official data with two commands (below).

## Storyline (what the analysis answers)

1. **How bad did prices get, and has the trend turned?** Headline inflation hit **28.92% in Dec 2023**, described as
   a 21-year high, up from about 20.5-21.5% in late 2022 (old 2009 base). In 2026 official releases show it
   easing from **15.10% (Jan)** to **14.63% (Sep)**, with a bump to 15.69% in April.
2. **Can we trust the comparison across years?** Not blindly. NBS moved to a new CPI index (reportedly base 2024 = 100 from
   January 2025) and flagged a further methodological revision in January 2026. June 2025 is quoted at **25.29%** in
   a 2026 release, so figures can be restated. The pipeline marks the break on every chart and in the Power BI date table.
3. **Is monetary policy tight or loose?** Using verified readings, the real policy rate (MPR minus inflation) was
   **+11.4 pts (Feb 2026), +10.6 (May 2026), +8.4 (Sep 2026)**. The MPR was cut to 26.5% in Feb 2026, held in May and July,
   then reset to **23%** on 22 Sep 2026. Tight, but easing.
4. **What happened to the naira?** Two verified official quotes, **~1,371 NGN/USD (21 May 2026)** and **1,328.67 (24 Sep 2026)**,
   put the naira about 3% stronger over four months, consistent with the CBN citing a stable exchange rate in 2026. The monthly
   series quantifies the value lost since the June 2023 reform date.
5. **What do jobs and growth say?** Annual unemployment, GDP growth and the misery index (from World Bank data). Unemployment
   definitions were reportedly revised in 2023, so a level shift is **not** necessarily a real recovery (see [`docs/data_notes.md`](docs/data_notes.md)).

When you run the pipeline on official data, `outputs/official/findings.md` computes the numbers for chapters 3-5
automatically (peak, regime averages, naira value lost, structural break, FX-to-inflation lag).

## Methods

| Technique | Where |
|---|---|
| Time-series decomposition (trend / seasonal / residual) | `analysis.classical_decompose` |
| Structural-break detection (least-squares mean shift) | `analysis.detect_mean_shift` |
| Lagged correlation (FX-to-price pass-through, descriptive) | `analysis.lagged_correlation` |
| Regime comparison around an analyst-set reform date | `analysis.regime_summary`, Excel `Regimes` sheet |
| Real policy rate, misery index, cumulative price level, purchasing power | `analysis.add_*_metrics` |
| Gap-aware monthly handling (no interpolation) | `analysis.complete_months` |

## Quick start

```bash
pip install -r requirements.txt

make sample                    # try everything now on SYNTHETIC data -> outputs/sample/

# Real data
make fetch                     # World Bank annual indicators (internet)
cp data/raw/manual/monthly_template.csv data/raw/manual/monthly.csv   # then add your NBS/CBN monthly rows
make build                     # -> outputs/official/
make test
```

Outputs per run (`outputs/<mode>/`): `charts/*.png`, `nigeria_economy_analysis.xlsx`, `powerbi_data/*.csv` + `theme.json`, `findings.md`.

## Excel workbook

Blue = inputs, black = formulas; every analytical number is a live formula (674 formulas in the sample build, recalculated with 0 errors).
Change the **reform date** on the `Assumptions` sheet and the `Regimes` sheet recalculates. Sheets: Dashboard (native charts),
Assumptions, Annual, Monthly, Regimes, PassThrough, VerifiedFacts.

## Power BI

`powerbi_data/` is a star schema (`dim_date`, `dim_year`, five fact tables). Follow [`docs/powerbi_guide.md`](docs/powerbi_guide.md)
for relationships and pages; DAX is in [`powerbi/measures.dax`](powerbi/measures.dax). The `.pbix` itself must be authored in
Power BI Desktop; the DAX has not been executed in Desktop yet, so validate measures against the Excel `Regimes` sheet.

## Design decisions

- **Verified facts are kept apart from series data**, with URL and check date on every row, so claims in the story are traceable.
- **Synthetic data can never masquerade as real**: a `data_status` column, chart watermarks, Excel banner/tab colour, and a
  warning at the top of `findings.md`.
- **Series breaks are first-class**: `CPI_REBASE_DATE` and `REFORM_DATE` are explicit, configurable assumptions.
- **Missing months stay missing** (no silent interpolation); the loader reports gaps.
- **Descriptive, not causal**: pass-through and regime results are labelled as associations.
- **Tested**: 22 tests cover the World Bank parser/fetcher (mocked), loaders, every analysis function against known answers,
  the Excel workbook structure, the Power BI star schema (every fact row joins to `dim_date`) and the CLI.

## Limitations & next steps

- Monthly series must be assembled by hand from NBS/CBN (their tables are not offered via a stable API).
- Add parallel-market FX, fuel prices and food-price indices to separate shocks from pass-through.
- Replace the single-break test with Bai-Perron multiple breaks; add forecasting (ETS/ARIMA) with backtests.
- Add state-level inflation and a regional map in Power BI.

See [`docs/data_notes.md`](docs/data_notes.md) for caveats and [`docs/data_sources.md`](docs/data_sources.md) for sources.
