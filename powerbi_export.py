"""Export a Power BI-ready star schema (CSV) + theme. Percentages are exported as fractions."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import analysis as A
from .data_sources import Dataset

THEME = {
    "name": "Nigeria Economy", "dataColors": ["#008751", "#3B5BDB", "#D98E04", "#B42318", "#1D2330", "#98A2B3"],
    "background": "#FFFFFF", "foreground": "#1D2330", "tableAccent": "#008751",
    "textClasses": {"title": {"fontFace": "Segoe UI Semibold", "fontSize": 14, "color": "#1D2330"},
                    "label": {"fontFace": "Segoe UI", "fontSize": 10, "color": "#667085"}},
}


def _frac(s: pd.Series) -> pd.Series:
    return s / 100.0


def build_dim_date(start: pd.Timestamp, end: pd.Timestamp, reform: str, rebase: str) -> pd.DataFrame:
    d = pd.DataFrame({"date": pd.date_range(start, end, freq="MS")})
    d["year"], d["quarter"] = d["date"].dt.year, "Q" + d["date"].dt.quarter.astype(str)
    d["month_no"], d["month_name"] = d["date"].dt.month, d["date"].dt.strftime("%b")
    d["year_month"] = d["date"].dt.strftime("%Y-%m")
    d["regime"] = np.where(d["date"] < pd.Timestamp(reform), "Pre-reform", "Post-reform")
    d["cpi_base"] = np.where(d["date"] < pd.Timestamp(rebase), "Old CPI base (2009)", "New CPI base (2024)")
    return d


def export(ds: Dataset, out_dir: Path, reform: str, rebase: str, verified: pd.DataFrame | None = None) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def save(df: pd.DataFrame, name: str):
        p = out_dir / name
        df.to_csv(p, index=False, date_format="%Y-%m-%d")
        written.append(p)

    a = A.add_annual_metrics(ds.annual)
    fa = pd.DataFrame({
        "year": a["year"], "inflation": _frac(a["inflation_pct"]), "gdp_growth": _frac(a["gdp_growth_pct"]),
        "unemployment": _frac(a["unemployment_pct"]), "misery_index_pts": a["misery_index"],
        "fx_ngn_usd": a["fx_ngn_usd"], "fx_change": _frac(a["fx_change_pct"]),
        "gdp_per_capita_usd": a["gdp_per_capita_usd"], "price_index": a["price_index"],
        "purchasing_power_of_100": a["purchasing_power_of_100"], "data_status": ds.status,
    })
    save(fa, "fact_annual.csv")
    save(pd.DataFrame({"year": a["year"], "decade": (a["year"] // 10 * 10).astype(str) + "s",
                       "regime": np.where(a["year"] < pd.Timestamp(reform).year, "Pre-reform", "Post-reform")}),
         "dim_year.csv")

    if ds.monthly is not None:
        m = A.add_monthly_metrics(ds.monthly)
        save(build_dim_date(m["date"].min(), m["date"].max(), reform, rebase), "dim_date.csv")
        fm = pd.DataFrame({
            "date": m["date"], "inflation_yoy": _frac(m["inflation_yoy"]),
            "food_inflation_yoy": _frac(m["food_inflation_yoy"]), "core_inflation_yoy": _frac(m["core_inflation_yoy"]),
            "fx_ngn_usd": m["fx_ngn_usd"], "mpr": _frac(m["mpr"]), "real_policy_rate": _frac(m["real_policy_rate"]),
            "fx_mom": _frac(m["fx_mom_pct"]), "fx_yoy": _frac(m["fx_yoy_pct"]),
            "inflation_12m_avg": _frac(m["inflation_12m_avg"]), "income_usd_equiv": m["income_usd_equiv"],
            "data_status": ds.status,
        })
        save(fm, "fact_monthly.csv")
        s = m.set_index("date")["inflation_yoy"].dropna()
        try:
            dec = A.classical_decompose(s).reset_index()
            save(dec, "fact_decomposition.csv")
        except ValueError:
            pass
        lc = A.lagged_correlation(m.set_index("date")["fx_yoy_pct"], m.set_index("date")["inflation_yoy"])
        save(lc, "fact_passthrough.csv")
        save(A.regime_summary(m, reform), "fact_regime_summary.csv")

    if verified is not None:
        v = verified.copy()
        v["period_date"] = pd.to_datetime(v["period"].astype(str).str[:7] + "-01", errors="coerce")
        save(v, "fact_verified.csv")

    (out_dir / "theme.json").write_text(json.dumps(THEME, indent=2), encoding="utf-8")
    written.append(out_dir / "theme.json")
    return written
