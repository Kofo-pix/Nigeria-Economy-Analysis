"""python -m ngeco fetch | build | all"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import analysis as A
from . import charts, data_sources, excel_report, powerbi_export
from .config import CPI_REBASE_DATE, OUTPUT_DIR, RAW_DIR, REFORM_DATE


def write_findings(ds, out: Path, reform: str, verified) -> Path:
    lines = [f"# Findings ({ds.label})", ""]
    if ds.is_sample:
        lines += ["> These results were computed from **synthetic sample data** to demonstrate the pipeline. "
                  "They are not statements about Nigeria.", ""]
    lines += ["## What the data shows", ""] + [f"- {f}" for f in A.key_findings(ds.annual, ds.monthly, reform, verified, ds.is_sample)]
    if verified is not None and len(verified):
        lines += ["", "## Latest verified official readings (always real; see data/raw/verified_datapoints.csv)", "",
                  "| Indicator | Period | Value | Source |", "|---|---|---|---|"]
        latest = verified.sort_values("period").groupby("indicator").tail(1)
        for r in latest.itertuples():
            lines.append(f"| {r.indicator} | {r.period} | {r.value:g} {r.unit} | {r.source_name} |")
        rr = A.verified_real_rates(verified)
        if len(rr):
            lines += ["", "### Real policy rate from verified points (MPR minus headline inflation)", "",
                      "| Period | MPR | Inflation | Real rate (pts) |", "|---|---|---|---|"]
            lines += [f"| {r.period} | {r.mpr:g} | {r.headline_inflation_yoy:g} | {r.real_policy_rate:+.2f} |" for r in rr.itertuples()]
    if ds.notes:
        lines += ["", "## Notes", ""] + [f"- {n}" for n in ds.notes]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def build(mode: str, reform: str, rebase: str) -> int:
    ds = data_sources.generate_sample() if mode == "sample" else data_sources.load_official()
    try:
        verified = data_sources.load_verified()
    except FileNotFoundError:
        verified = None
    out = OUTPUT_DIR / mode
    out.mkdir(parents=True, exist_ok=True)
    print(f"[{ds.label}] building outputs in {out}")
    for note in ds.notes:
        print("  note:", note)
    charts_made = charts.build_all(ds, out / "charts", reform, rebase)
    xlsx = excel_report.build_workbook(ds, out / "nigeria_economy_analysis.xlsx", reform, verified)
    pbi = powerbi_export.export(ds, out / "powerbi_data", reform, rebase, verified)
    find = write_findings(ds, out / "findings.md", reform, verified)
    print(f"  {len(charts_made)} charts, Excel workbook ({xlsx.name}), {len(pbi)} Power BI files, findings.md")
    print("  Next: recalc the workbook (make recalc) and follow docs/powerbi_guide.md")
    return 0 if find.exists() else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ngeco", description="Nigeria economic & inflation analysis")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch", help="download World Bank annual indicators (needs internet)")
    for name in ("build", "all"):
        b = sub.add_parser(name, help="build charts, Excel workbook, Power BI data, findings")
        b.add_argument("--mode", choices=["official", "sample"], default="official")
        b.add_argument("--reform-date", default=REFORM_DATE)
        b.add_argument("--rebase-date", default=CPI_REBASE_DATE)
    args = p.parse_args(argv)
    try:
        if args.cmd == "fetch":
            df = data_sources.fetch_worldbank(raw_dir=RAW_DIR)
            print(f"Saved {len(df)} annual rows ({int(df.year.min())}-{int(df.year.max())}) to {RAW_DIR / 'worldbank_nga.csv'}")
            return 0
        if args.cmd == "all" and args.mode == "official" and not (RAW_DIR / "worldbank_nga.csv").exists():
            data_sources.fetch_worldbank(raw_dir=RAW_DIR)
        return build(args.mode, args.reform_date, args.rebase_date)
    except data_sources.DataError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
