"""Data acquisition: World Bank API, manually-downloaded NBS/CBN monthly data, and a synthetic sample."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ANNUAL_COLS, MONTHLY_COLS, RAW_DIR, WB_INDICATORS

WB_URL = "https://api.worldbank.org/v2/country/{country}/indicator/{code}?format=json&per_page=1000&date={start}:{end}"


class DataError(RuntimeError):
    """Raised for missing/invalid data with a message telling the user how to fix it."""


@dataclass
class Dataset:
    annual: pd.DataFrame
    monthly: pd.DataFrame | None
    is_sample: bool
    notes: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return "SAMPLE DATA - NOT OFFICIAL STATISTICS" if self.is_sample else "Official data"

    @property
    def status(self) -> str:
        return "SYNTHETIC_SAMPLE" if self.is_sample else "OFFICIAL"


# ------------------------------------------------------------------ World Bank ------------
def parse_worldbank(payload) -> pd.DataFrame:
    """Parse one World Bank API response ([meta, rows]) into a tidy (year, value) frame."""
    if not isinstance(payload, list) or not payload:
        raise DataError("Unexpected World Bank API response shape.")
    meta = payload[0]
    if isinstance(meta, dict) and "message" in meta:
        raise DataError(f"World Bank API error: {meta['message']}")
    rows = payload[1] if len(payload) > 1 else None
    if not rows:
        return pd.DataFrame(columns=["year", "value"])
    df = pd.DataFrame({"year": [int(r["date"]) for r in rows],
                       "value": [r.get("value") for r in rows]})
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna(subset=["value"]).sort_values("year").reset_index(drop=True)


def _get_json(url: str, timeout: int = 30, retries: int = 3):
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (fixed https host)
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise DataError(f"Could not reach the World Bank API ({last}). Check your internet connection and retry.")


def fetch_worldbank(country: str = "NGA", start: int = 1990, end: int | None = None,
                    raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    end = end or datetime.now().year
    series = []
    for code, name in WB_INDICATORS.items():
        df = parse_worldbank(_get_json(WB_URL.format(country=country, code=code, start=start, end=end)))
        series.append(df.set_index("year")["value"].rename(name))
    annual = pd.concat(series, axis=1).sort_index().rename_axis("year").reset_index()
    annual = annual.dropna(how="all", subset=list(WB_INDICATORS.values()))
    raw_dir.mkdir(parents=True, exist_ok=True)
    annual.to_csv(raw_dir / "worldbank_nga.csv", index=False)
    (raw_dir / "worldbank_nga.meta.json").write_text(json.dumps({
        "source": "World Bank World Development Indicators API", "country": country,
        "indicators": WB_INDICATORS, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": "Latest year is often null or provisional; values are revised, so keep the fetch date.",
    }, indent=2), encoding="utf-8")
    return annual


# ------------------------------------------------------------------ manual monthly --------
def load_monthly(path: Path) -> pd.DataFrame:
    """Load a hand-assembled monthly CSV (see data/raw/manual/monthly_template.csv)."""
    df = pd.read_csv(path, comment="#")
    missing = {"date", "inflation_yoy"} - set(df.columns)
    if missing:
        raise DataError(f"{path.name}: missing required column(s) {sorted(missing)}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if df["date"].isna().any():
        raise DataError(f"{path.name}: unparseable dates in 'date' column")
    df["date"] = df["date"].dt.to_period("M").dt.to_timestamp()
    for col in MONTHLY_COLS[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce") if col in df else np.nan
    df = df.drop_duplicates("date", keep="last").sort_values("date")
    return df[MONTHLY_COLS].reset_index(drop=True)


def load_official(raw_dir: Path = RAW_DIR, min_monthly_rows: int = 36) -> Dataset:
    annual_path = raw_dir / "worldbank_nga.csv"
    if not annual_path.exists():
        raise DataError(f"{annual_path} not found. Run `make fetch` (needs internet) to download "
                        "World Bank annual indicators, or use `--mode sample` to try the pipeline.")
    annual = pd.read_csv(annual_path)
    for c in ANNUAL_COLS:
        if c not in annual:
            annual[c] = np.nan
    notes: list[str] = []
    monthly = None
    mpath = raw_dir / "manual" / "monthly.csv"
    if mpath.exists():
        monthly = load_monthly(mpath)
        full = pd.date_range(monthly["date"].min(), monthly["date"].max(), freq="MS")
        gaps = len(full) - len(monthly)
        if gaps:
            notes.append(f"monthly.csv has {gaps} missing month(s); gaps are left blank, not interpolated.")
        if len(monthly) < min_monthly_rows:
            notes.append(f"monthly.csv has only {len(monthly)} rows (< {min_monthly_rows}); "
                         "monthly time-series analysis skipped.")
            monthly = None
    else:
        notes.append("No data/raw/manual/monthly.csv found: running annual analysis only. "
                     "See docs/data_sources.md to add monthly NBS/CBN data.")
    return Dataset(annual[ANNUAL_COLS].sort_values("year").reset_index(drop=True), monthly, False, notes)


# ------------------------------------------------------------------ synthetic sample ------
def generate_sample(seed: int = 11) -> Dataset:
    """Stylised synthetic data for testing/demoing the pipeline. NOT real statistics."""
    rng = np.random.default_rng(seed)

    # monthly
    idx = pd.date_range("2015-01-01", "2026-09-01", freq="MS")
    t = idx.year + (idx.month - 1) / 12
    anchors_t = [2015, 2017, 2019, 2021, 2022, 2023.5, 2024.9, 2026.7]
    anchors_v = [9, 18, 11, 17, 20, 24, 34, 15]
    mean = np.interp(t, anchors_t, anchors_v)
    e = np.zeros(len(idx))
    for i in range(1, len(idx)):
        e[i] = 0.85 * e[i - 1] + rng.normal(0, 0.6)
    infl = np.clip(mean + e, 2, None)
    logfx = np.log(200) + np.cumsum(0.004 + rng.normal(0, 0.01, len(idx)))
    for when, jump in [("2016-06-01", 0.22), ("2020-03-01", 0.15), ("2023-06-01", 0.40), ("2024-01-01", 0.30)]:
        logfx[idx >= pd.Timestamp(when)] += jump
    steps = [("2015-01-01", 13.0), ("2016-07-01", 14.0), ("2020-05-01", 12.5), ("2022-05-01", 13.0),
             ("2022-09-01", 15.5), ("2023-02-01", 18.0), ("2024-02-01", 24.75), ("2024-11-01", 27.5),
             ("2026-09-01", 23.0)]
    mpr = np.full(len(idx), steps[0][1])
    for when, v in steps:
        mpr[idx >= pd.Timestamp(when)] = v
    monthly = pd.DataFrame({
        "date": idx, "inflation_yoy": infl.round(2),
        "food_inflation_yoy": (infl * 1.1 + rng.normal(0, 1, len(idx))).round(2),
        "core_inflation_yoy": (infl * 0.9 + rng.normal(0, 0.8, len(idx))).round(2),
        "fx_ngn_usd": np.exp(logfx).round(2), "mpr": mpr,
    })

    # annual
    years = np.arange(2000, 2025)
    a_infl = np.zeros(len(years))
    a_infl[0] = 14
    for i in range(1, len(years)):
        target = 12 if years[i] < 2023 else 28
        a_infl[i] = 0.5 * a_infl[i - 1] + 0.5 * target + rng.normal(0, 2.5)
    unemp = 6 + np.cumsum(rng.normal(0, 0.25, len(years)))
    unemp[years == 2020] += 3
    gdp = rng.normal(4.5, 2.2, len(years))
    gdp[years == 2016] = -1.6
    gdp[years == 2020] = -1.8
    afx = 100 * np.exp(np.cumsum(rng.normal(0.03, 0.04, len(years))))
    afx[years >= 2016] *= 1.5
    afx[years >= 2023] *= 2.2
    annual = pd.DataFrame({
        "year": years, "inflation_pct": a_infl.round(2), "gdp_growth_pct": gdp.round(2),
        "unemployment_pct": unemp.round(2), "fx_ngn_usd": afx.round(2),
        "gdp_per_capita_usd": (1800 + np.cumsum(rng.normal(40, 120, len(years)))).round(0),
        "current_account_pct_gdp": rng.normal(1, 3.5, len(years)).round(2),
    })
    return Dataset(annual, monthly, True, ["SYNTHETIC sample generated for pipeline testing; "
                                          "values are NOT official statistics."])


def load_verified(path: Path | None = None) -> pd.DataFrame:
    path = path or RAW_DIR / "verified_datapoints.csv"
    return pd.read_csv(path, dtype={"period": str})
