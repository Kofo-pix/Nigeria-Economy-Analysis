from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = Path(os.getenv("NGECO_RAW_DIR", ROOT / "data" / "raw"))
PROCESSED_DIR = Path(os.getenv("NGECO_PROCESSED_DIR", ROOT / "data" / "processed"))
OUTPUT_DIR = Path(os.getenv("NGECO_OUTPUT_DIR", ROOT / "outputs"))

# World Bank WDI indicator code -> canonical column name (annual data, country NGA)
WB_INDICATORS = {
    "FP.CPI.TOTL.ZG": "inflation_pct",           # Inflation, consumer prices (annual %)
    "NY.GDP.MKTP.KD.ZG": "gdp_growth_pct",       # GDP growth (annual %)
    "SL.UEM.TOTL.ZS": "unemployment_pct",        # Unemployment, % of labour force (ILO modelled)
    "PA.NUS.FCRF": "fx_ngn_usd",                 # Official exchange rate (LCU per US$, period average)
    "NY.GDP.PCAP.CD": "gdp_per_capita_usd",      # GDP per capita (current US$)
    "BN.CAB.XOKA.GD.ZS": "current_account_pct_gdp",
}

# ---- Analyst-chosen event dates (assumptions: change them, everything recomputes) ----------
# Subsidy removal was announced on 29 May 2023 and CBN unified FX windows in mid-June 2023.
REFORM_DATE = "2023-06-01"
# NBS moved to a new CPI index (base 2024 = 100) from January 2025; no official chain-linked series.
CPI_REBASE_DATE = "2025-01-01"

ANNUAL_COLS = ["year", *WB_INDICATORS.values()]
MONTHLY_COLS = ["date", "inflation_yoy", "food_inflation_yoy", "core_inflation_yoy", "fx_ngn_usd", "mpr"]
