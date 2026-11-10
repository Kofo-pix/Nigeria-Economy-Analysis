"""Matplotlib charts. Every chart is stamped when it is built from synthetic sample data."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from . import analysis as A  # noqa: E402
from .data_sources import Dataset  # noqa: E402

GREEN, DARK, RED, AMBER, GREY, BLUE = "#008751", "#1d2330", "#b42318", "#d98e04", "#98a2b3", "#3b5bdb"

plt.rcParams.update({
    "figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.alpha": 0.25, "axes.titleweight": "bold", "axes.titlesize": 13, "font.size": 10,
    "axes.edgecolor": GREY, "axes.titlelocation": "left",
})


def _finish(fig, ds: Dataset, path: Path, source: str) -> Path:
    fig.text(0.01, 0.005, f"Source: {source}", fontsize=8, color=GREY)
    if ds.is_sample:
        fig.text(0.5, 0.5, "SAMPLE DATA\nNOT OFFICIAL STATISTICS", fontsize=34, color=RED, alpha=0.13,
                 ha="center", va="center", rotation=25, weight="bold")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def _mark_events(ax, reform, rebase, dmin, dmax):
    for when, label, color in ((reform, "Reform date", RED), (rebase, "CPI rebase", AMBER)):
        d = pd.Timestamp(when)
        if dmin <= d <= dmax:
            ax.axvline(d, color=color, ls="--", lw=1.2)
            ax.text(d, ax.get_ylim()[1], f" {label}", color=color, va="top", fontsize=8)


def inflation_timeline(ds, m, out, reform, rebase):
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.plot(m["date"], m["inflation_yoy"], color=GREEN, lw=1.8, label="Headline inflation (y/y)")
    ax.plot(m["date"], m["inflation_12m_avg"], color=DARK, lw=1.4, ls=":", label="12-month average")
    ax.set_ylabel("% year-on-year")
    ax.set_title("Headline inflation: monthly, with 12-month average")
    _mark_events(ax, reform, rebase, m["date"].min(), m["date"].max())
    ax.legend(loc="upper left", frameon=False, bbox_to_anchor=(0, 0.9))
    return _finish(fig, ds, out / "01_inflation_timeline.png", "NBS / CBN (see data_sources.md)")


def fx_vs_inflation(ds, m, out, reform, rebase):
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 6.2), sharex=True, height_ratios=[1.2, 1])
    a1.plot(m["date"], m["fx_ngn_usd"], color=BLUE, lw=1.8)
    a1.set_ylabel("NGN per USD")
    a1.set_title("The naira: official exchange rate")
    a2.plot(m["date"], m["fx_yoy_pct"], color=AMBER, lw=1.5, label="FX change y/y")
    a2.plot(m["date"], m["inflation_yoy"], color=GREEN, lw=1.5, label="Inflation y/y")
    a2.set_ylabel("%")
    a2.set_title("Depreciation vs inflation")
    a2.legend(frameon=False, loc="upper left")
    for ax in (a1, a2):
        _mark_events(ax, reform, rebase, m["date"].min(), m["date"].max())
    return _finish(fig, ds, out / "02_fx_vs_inflation.png", "CBN; NBS")


def real_policy_rate(ds, m, out, reform, rebase):
    r = m.dropna(subset=["real_policy_rate"])
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.bar(r["date"], r["real_policy_rate"], width=25, color=[GREEN if v >= 0 else RED for v in r["real_policy_rate"]])
    ax.axhline(0, color=DARK, lw=0.8)
    ax.set_ylabel("percentage points")
    ax.set_title("Real policy rate (MPR minus inflation): negative means borrowing was 'cheap' in real terms")
    ax.title.set_fontsize(11)
    return _finish(fig, ds, out / "03_real_policy_rate.png", "CBN (MPR); NBS (inflation)")


def annual_overview(ds, a, out):
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    spec = [("inflation_pct", "Inflation (annual %)", GREEN, "line"), ("gdp_growth_pct", "GDP growth (annual %)", BLUE, "bar"),
            ("unemployment_pct", "Unemployment (% of labour force)", AMBER, "line"), ("misery_index", "Misery index (inflation + unemployment)", RED, "bar")]
    for ax, (col, title, color, kind) in zip(axes.ravel(), spec):
        d = a.dropna(subset=[col])
        if kind == "bar":
            ax.bar(d["year"], d[col], color=[color if v >= 0 else DARK for v in d[col]])
        else:
            ax.plot(d["year"], d[col], color=color, lw=2, marker="o", ms=3)
        ax.set_title(title, fontsize=11)
    return _finish(fig, ds, out / "04_annual_overview.png", "World Bank WDI")


def decomposition(ds, m, out):
    dec = A.classical_decompose(m.set_index("date")["inflation_yoy"].dropna())
    fig, axes = plt.subplots(4, 1, figsize=(10, 8), sharex=True)
    for ax, col, color in zip(axes, dec.columns, (DARK, GREEN, BLUE, GREY)):
        ax.plot(dec.index, dec[col], color=color, lw=1.4)
        ax.set_ylabel(col)
    axes[0].set_title("Inflation: trend / seasonal / residual decomposition (additive, 12-month period)")
    return _finish(fig, ds, out / "05_decomposition.png", "Computed from monthly headline inflation")


def passthrough(ds, m, out):
    lc = A.lagged_correlation(m.set_index("date")["fx_yoy_pct"], m.set_index("date")["inflation_yoy"])
    fig, ax = plt.subplots(figsize=(8, 4))
    best = lc["correlation"].idxmax()
    ax.bar(lc["lag_months"], lc["correlation"], color=[GREEN if i == best else GREY for i in lc.index])
    ax.set_xlabel("FX change leads inflation by (months)")
    ax.set_ylabel("correlation")
    ax.set_title("Exchange-rate 'pass-through': when does depreciation show up in prices?")
    ax.title.set_fontsize(11)
    return _finish(fig, ds, out / "06_passthrough.png", "Computed; descriptive, not causal")


def purchasing_power(ds, a, out):
    d = a.dropna(subset=["purchasing_power_of_100"])
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.fill_between(d["year"], d["purchasing_power_of_100"], color=GREEN, alpha=0.25)
    ax.plot(d["year"], d["purchasing_power_of_100"], color=GREEN, lw=2)
    ax.set_ylabel(f"What NGN 100 of {int(d['year'].iloc[0])} still buys")
    ax.set_title("Erosion of purchasing power (cumulative annual inflation)")
    return _finish(fig, ds, out / "07_purchasing_power.png", "World Bank WDI; computed")


def build_all(ds: Dataset, out_dir: Path, reform: str, rebase: str) -> list[Path]:
    a = A.add_annual_metrics(ds.annual)
    paths = [annual_overview(ds, a, out_dir), purchasing_power(ds, a, out_dir)]
    if ds.monthly is not None:
        m = A.add_monthly_metrics(ds.monthly)
        paths += [inflation_timeline(ds, m, out_dir, reform, rebase)]
        if m["fx_ngn_usd"].notna().sum() > 24:
            paths += [fx_vs_inflation(ds, m, out_dir, reform, rebase), passthrough(ds, m, out_dir)]
        if m["real_policy_rate"].notna().sum() > 12:
            paths += [real_policy_rate(ds, m, out_dir, reform, rebase)]
        paths += [decomposition(ds, m, out_dir)]
    return paths
