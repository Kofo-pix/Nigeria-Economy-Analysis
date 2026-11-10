# Building the Power BI report (about 30 minutes)

`make build` (or `make sample`) writes everything Power BI needs to `outputs/<mode>/powerbi_data/`.
A `.pbix` file can only be authored in **Power BI Desktop (Windows)**, so this guide is the build spec.

## 1. Load the data
**Get data > Text/CSV**, load every CSV in `powerbi_data/`. Then **View > Themes > Browse for themes** and pick `theme.json`.
Set data types: `date` / `period_date` = Date; percent columns = Percentage; `fx_ngn_usd` = Fixed decimal.
Percent columns are exported as fractions (0.1463 = 14.63%).

## 2. Model (star schema)
| From (many) | To (one) | Column |
|---|---|---|
| `fact_monthly[date]` | `dim_date[date]` | single direction |
| `fact_decomposition[date]` | `dim_date[date]` | single direction |
| `fact_verified[period_date]` | `dim_date[date]` | single direction (may be inactive) |
| `fact_annual[year]` | `dim_year[year]` | single direction |

`fact_passthrough` and `fact_regime_summary` stand alone. Mark `dim_date` as a date table. Sort `month_name` by `month_no`.
In `dim_date`, `regime` (pre/post reform) and `cpi_base` (old/new CPI index) let you split any visual by policy
regime or flag the **series break**.

## 3. Measures
Create a `_Measures` table and paste the measures from [`powerbi/measures.dax`](../powerbi/measures.dax).
Validate each measure against `outputs/<mode>/nigeria_economy_analysis.xlsx` (the Regimes sheet has the same numbers).

## 4. Report pages
| Page | Visuals |
|---|---|
| **1. Overview** | Cards: Latest Inflation, Inflation Change vs 12M Ago, Latest FX, Latest MPR, Latest Real Policy Rate. Line: `inflation_yoy` + `inflation_12m_avg` by `dim_date[date]`. Slicers: `regime`, `year`. Banner card: *Data Status Banner*. |
| **2. Naira & prices** | Line: `fx_ngn_usd`. Line (two series): `fx_yoy` vs `inflation_yoy`. Column: `fact_passthrough[correlation]` by `lag_months`. Card: *Naira Value Lost Since Reform*. |
| **3. Policy stance** | Column: `real_policy_rate` (colour by *Real Rate Colour*). Line: `mpr` vs `inflation_yoy`. Table: `fact_regime_summary`. |
| **4. Annual story** | Line: `inflation` & `unemployment` by `year`. Column: `misery_index_pts`. Area: `purchasing_power_of_100`. Column: `gdp_growth`. |
| **5. Fact check** | Table of `fact_verified` (indicator, period, value, source_name, source_url as web URL). Cards: Latest Verified Inflation / MPR / Real Policy Rate. |

Add a text box on page 1 with the **three-sentence story** (see README "Storyline") and a footer with sources.

## 5. Publish
Save as `nigeria_economy.pbix`, export a PDF and PNG screenshots into `docs/`, and link them in the README.
Use **Publish to web** only with official (not sample) data and only after checking source licensing.
