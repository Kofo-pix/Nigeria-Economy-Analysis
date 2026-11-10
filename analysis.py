"""Time-series and economic analysis. Pure pandas/numpy: no heavy dependencies."""
from __future__ import annotations

import numpy as np
import pandas as pd


# ------------------------------------------------------------------ derived metrics ------
def add_annual_metrics(annual: pd.DataFrame) -> pd.DataFrame:
    a = annual.copy().sort_values("year").reset_index(drop=True)
    a["misery_index"] = a["inflation_pct"] + a["unemployment_pct"]
    a["fx_change_pct"] = a["fx_ngn_usd"].pct_change(fill_method=None) * 100  # % rise in NGN per USD

    # Cumulative price level (first year with inflation data = 100) and purchasing power of NGN 100.
    idx = np.full(len(a), np.nan)
    started = False
    for i, infl in enumerate(a["inflation_pct"]):
        if np.isnan(infl):
            idx[i] = idx[i - 1] if started and i else np.nan
            continue
        idx[i] = 100.0 if not started else idx[i - 1] * (1 + infl / 100)
        started = True
    a["price_index"] = idx
    a["purchasing_power_of_100"] = 100 * 100 / a["price_index"]
    return a


def complete_months(m: pd.DataFrame) -> pd.DataFrame:
    """Reindex to a gap-free monthly calendar (gaps become NaN, never interpolated)."""
    m = m.copy().set_index("date").sort_index()
    return m.reindex(pd.date_range(m.index.min(), m.index.max(), freq="MS")).rename_axis("date")


def add_monthly_metrics(monthly: pd.DataFrame, income_ngn: float = 100_000) -> pd.DataFrame:
    m = complete_months(monthly)
    m["fx_mom_pct"] = m["fx_ngn_usd"].pct_change(fill_method=None) * 100
    m["fx_yoy_pct"] = m["fx_ngn_usd"].pct_change(12, fill_method=None) * 100
    m["real_policy_rate"] = m["mpr"] - m["inflation_yoy"]
    m["inflation_12m_avg"] = m["inflation_yoy"].rolling(12).mean()
    m["inflation_3m_change"] = m["inflation_yoy"].diff(3)
    m["income_usd_equiv"] = income_ngn / m["fx_ngn_usd"]
    return m.reset_index()


# ------------------------------------------------------------------ time series ----------
def classical_decompose(s: pd.Series, period: int = 12) -> pd.DataFrame:
    """Additive classical decomposition: observed = trend + seasonal + residual."""
    s = s.astype(float)
    if s.dropna().shape[0] < 2 * period:
        raise ValueError(f"need at least {2 * period} observations for period={period}")
    trend = s.rolling(period).mean().rolling(2).mean().shift(-(period // 2)) if period % 2 == 0 \
        else s.rolling(period, center=True).mean()
    detr = s - trend
    pos = np.arange(len(s)) % period
    seasonal_means = detr.groupby(pos).mean()
    seasonal_means -= seasonal_means.mean()
    seasonal = pd.Series(seasonal_means.reindex(pos).to_numpy(), index=s.index)
    return pd.DataFrame({"observed": s, "trend": trend, "seasonal": seasonal,
                         "residual": s - trend - seasonal})


def detect_mean_shift(s: pd.Series, trim: float = 0.15) -> dict:
    """Single structural break in the mean (least-squares scan with trimming).

    Reports the break date and how much of the total squared error the two-regime fit removes.
    The F-statistic is descriptive: critical values for an *estimated* break date are non-standard.
    """
    x = s.dropna()
    n = len(x)
    lo, hi = int(n * trim), n - int(n * trim)
    if hi - lo < 2:
        raise ValueError("series too short for break detection")
    v = x.to_numpy(float)
    sse0 = ((v - v.mean()) ** 2).sum()
    best = (np.inf, None)
    for k in range(lo, hi):
        sse = ((v[:k] - v[:k].mean()) ** 2).sum() + ((v[k:] - v[k:].mean()) ** 2).sum()
        if sse < best[0]:
            best = (sse, k)
    sse, k = best
    return {"break_date": x.index[k], "mean_before": float(v[:k].mean()), "mean_after": float(v[k:].mean()),
            "sse_reduction_pct": float(100 * (1 - sse / sse0)) if sse0 else 0.0,
            "f_stat": float((sse0 - sse) / (sse / (n - 2))) if sse else float("inf")}


def lagged_correlation(x: pd.Series, y: pd.Series, max_lag: int = 12) -> pd.DataFrame:
    """corr(x[t-lag], y[t]) for lag = 0..max_lag: how strongly past x lines up with today's y."""
    rows = []
    for lag in range(max_lag + 1):
        pair = pd.concat([x.shift(lag), y], axis=1).dropna()
        rows.append({"lag_months": lag, "correlation": float(pair.iloc[:, 0].corr(pair.iloc[:, 1]))
                     if len(pair) > 5 else np.nan, "n": len(pair)})
    return pd.DataFrame(rows)


def regime_summary(m: pd.DataFrame, cut: str | pd.Timestamp,
                   cols=("inflation_yoy", "fx_yoy_pct", "mpr", "real_policy_rate")) -> pd.DataFrame:
    cut = pd.Timestamp(cut)
    pre, post = m[m["date"] < cut], m[m["date"] >= cut]
    out = []
    for c in cols:
        if c in m and m[c].notna().any():
            out.append({"metric": c, "pre_mean": pre[c].mean(), "post_mean": post[c].mean(),
                        "pre_max": pre[c].max(), "post_max": post[c].max(),
                        "change_in_mean": post[c].mean() - pre[c].mean()})
    return pd.DataFrame(out)


# ------------------------------------------------------------------ narrative facts ------
def verified_real_rates(verified: pd.DataFrame) -> pd.DataFrame:
    """Real policy rate (MPR - headline inflation) wherever both are in the verified fact sheet."""
    pivot = verified.pivot_table(index="period", columns="indicator", values="value", aggfunc="last")
    if not {"mpr", "headline_inflation_yoy"} <= set(pivot.columns):
        return pd.DataFrame()
    both = pivot[["mpr", "headline_inflation_yoy"]].dropna()
    both["real_policy_rate"] = (both["mpr"] - both["headline_inflation_yoy"]).round(2)
    return both.reset_index()


def key_findings(annual: pd.DataFrame, monthly: pd.DataFrame | None, reform_date: str,
                 verified: pd.DataFrame | None = None, is_sample: bool = False) -> list[str]:
    out: list[str] = []
    if is_sample:
        out.append("**WARNING: these findings come from SYNTHETIC SAMPLE data and say nothing about Nigeria.**")
    a = add_annual_metrics(annual)
    if a["inflation_pct"].notna().any():
        r = a.loc[a["inflation_pct"].idxmax()]
        out.append(f"Annual inflation peaked at {r['inflation_pct']:.1f}% in {int(r['year'])}.")
    if a["misery_index"].notna().any():
        r = a.loc[a["misery_index"].idxmax()]
        out.append(f"The misery index (inflation + unemployment) was highest in {int(r['year'])} at {r['misery_index']:.1f} points.")
    pp = a.dropna(subset=["purchasing_power_of_100"])
    if len(pp) > 1:
        first, last = pp.iloc[0], pp.iloc[-1]
        out.append(f"Prices rose {last['price_index'] / 100:.1f}x between {int(first['year'])} and {int(last['year'])}: "
                   f"NGN 100 in {int(first['year'])} had the purchasing power of NGN {last['purchasing_power_of_100']:.1f} by {int(last['year'])}.")
    if monthly is not None:
        m = add_monthly_metrics(monthly)
        s = m.set_index("date")["inflation_yoy"]
        out.append(f"Monthly headline inflation peaked at {s.max():.2f}% in {s.idxmax():%b %Y}; "
                   f"latest reading {s.dropna().iloc[-1]:.2f}% ({s.dropna().index[-1]:%b %Y}).")
        rs = regime_summary(m, reform_date)
        if not rs.empty:
            i = rs.set_index("metric").loc["inflation_yoy"]
            out.append(f"Average inflation was {i['pre_mean']:.1f}% before {pd.Timestamp(reform_date):%b %Y} "
                       f"and {i['post_mean']:.1f}% after.")
        fx = m.set_index("date")["fx_ngn_usd"].dropna()
        if len(fx) > 24:
            pre = fx[fx.index < pd.Timestamp(reform_date)].iloc[-1]
            out.append(f"The official rate moved from {pre:,.0f} to {fx.iloc[-1]:,.0f} NGN/USD, "
                       f"so the naira lost {100 * (1 - pre / fx.iloc[-1]):.0f}% of its USD value since just before the reform date.")
        rr = m["real_policy_rate"].dropna()
        if len(rr):
            out.append(f"The real policy rate was negative in {int((rr < 0).sum())} of {len(rr)} months "
                       f"(latest {rr.iloc[-1]:+.1f} pts).")
        try:
            brk = detect_mean_shift(s)
            out.append(f"Data-driven break in mean inflation: {brk['break_date']:%b %Y} "
                       f"({brk['mean_before']:.1f}% -> {brk['mean_after']:.1f}%), explaining {brk['sse_reduction_pct']:.0f}% of variance.")
        except ValueError:
            pass
        lc = lagged_correlation(m.set_index("date")["fx_yoy_pct"], s)
        if lc["correlation"].notna().any():
            b = lc.loc[lc["correlation"].idxmax()]
            out.append(f"FX depreciation and inflation line up most strongly at a {int(b['lag_months'])}-month lag "
                       f"(r = {b['correlation']:.2f}); descriptive, not causal.")
    return out
