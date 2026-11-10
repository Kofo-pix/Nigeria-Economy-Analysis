# Data caveats (read before drawing conclusions)

1. **CPI series breaks.** NBS reportedly introduced a new CPI index (base 2024 = 100) from January 2025, and a further
   methodological revision is flagged around January 2026. No official chain-linked series bridges the old
   (2009-based) and new indices, so y/y inflation across the break is **not strictly comparable**.
   The pipeline marks the rebase date (`CPI_REBASE_DATE`) on charts and in the Power BI date table.
2. **Data vintage.** The 2025 comparatives quoted in 2026 NBS releases (e.g. June 2025 = 25.29%) may differ
   from figures first published in 2025. When you assemble a monthly series, record which release you used.
3. **Unemployment definitions changed (verify against NBS LFS reports).** NBS is widely reported to have revised its
   labour-force methodology in 2023, producing a sharp downward level shift versus earlier published rates; World Bank/ILO modelled estimates use a different
   basis again. Treat unemployment as a *level-shifted* series and avoid reading the break as a real recovery.
4. **Official vs. parallel FX.** The 2016-2023 period had large gaps between the official and parallel market
   rates; official-rate series understate depreciation before the June 2023 unification.
5. **Correlation is not pass-through.** Lagged correlations between FX moves and inflation are descriptive;
   they ignore fuel prices, food supply shocks and base effects.
6. **Latest World Bank year is often null/provisional** and values are revised: keep the fetch date
   (`worldbank_nga.meta.json`).
