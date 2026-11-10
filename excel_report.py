"""Excel workbook with live formulas (inputs in blue, formulas in black) and native charts."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import analysis as A
from .data_sources import Dataset

FONT = "Arial"
BLUE = Font(name=FONT, color="0000FF")          # hardcoded inputs
BLACK = Font(name=FONT, color="000000")         # formulas
HEAD = Font(name=FONT, bold=True, color="FFFFFF")
HEAD_FILL = PatternFill("solid", fgColor="1D2330")
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
WARN_FILL = PatternFill("solid", fgColor="FDECEB")
THIN = Border(bottom=Side(style="thin", color="E4E7EC"))
PCT, PCT2, NUM, NUM2, DATE = "0.0%;(0.0%);-", "0.00%", "#,##0;(#,##0);-", "#,##0.00", "mmm yyyy"


def _val(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else x


def _header(ws, headers, widths):
    for i, (h, w) in enumerate(zip(headers, widths), start=1):
        c = ws.cell(1, i, h)
        c.font, c.fill = HEAD, HEAD_FILL
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[1].height = 42
    ws.freeze_panes = "B2"


def _font_all(ws):
    for row in ws.iter_rows():
        for c in row:
            if c.font is None or c.font.name != FONT:
                c.font = Font(name=FONT, bold=c.font.bold if c.font else False,
                              color=c.font.color if c.font and c.font.color else None)


def build_workbook(ds: Dataset, out_path: Path, reform_date: str, verified: pd.DataFrame | None = None,
                   income_ngn: float = 100_000) -> Path:
    wb = Workbook()
    about = wb.active
    about.title = "About"
    a = A.add_annual_metrics(ds.annual)
    m = A.add_monthly_metrics(ds.monthly) if ds.monthly is not None else None

    # ---------------------------------------------------------------- Assumptions ----------
    asm = wb.create_sheet("Assumptions")
    asm["A1"], asm["A2"], asm["A3"] = "Assumption", "Reform date (regime split)", "Monthly income used for USD view (NGN)"
    for c in asm[1]:
        c.font, c.fill = HEAD, HEAD_FILL
    asm["A1"].value, asm["B1"].value = "Assumption", "Value"
    asm["B1"].font, asm["B1"].fill = HEAD, HEAD_FILL
    asm["B2"] = pd.Timestamp(reform_date).to_pydatetime()
    asm["B2"].number_format = "dd mmm yyyy"
    asm["B3"] = income_ngn
    asm["B3"].number_format = NUM
    for c in (asm["B2"], asm["B3"]):
        c.font, c.fill = BLUE, INPUT_FILL
    asm["C2"] = "Change this date and the Regimes sheet recalculates. Default: June 2023 (subsidy removal / FX unification)."
    asm["C3"] = "Used in Monthly!H to show a fixed naira income in US$ terms."
    asm.column_dimensions["A"].width, asm.column_dimensions["B"].width, asm.column_dimensions["C"].width = 38, 18, 90

    # ---------------------------------------------------------------- Annual --------------
    wa = wb.create_sheet("Annual")
    _header(wa, ["Year", "Inflation", "GDP growth", "Unemployment", "FX (NGN/USD)", "GDP per capita (US$)",
                 "Misery index (pts)", "FX change y/y", "Price index (first yr = 100)",
                 "Purchasing power of NGN 100", "Data status"],
            [8, 12, 12, 14, 14, 16, 14, 13, 18, 18, 18])
    n_a = len(a)
    first_idx = a["price_index"].first_valid_index()
    for i, row in a.iterrows():
        r = i + 2
        wa.cell(r, 1, int(row["year"]))
        for col, key, scale in ((2, "inflation_pct", 100), (3, "gdp_growth_pct", 100), (4, "unemployment_pct", 100)):
            v = _val(row[key])
            c = wa.cell(r, col, None if v is None else v / scale)
            c.number_format = PCT
        c = wa.cell(r, 5, _val(row["fx_ngn_usd"]))
        c.number_format = NUM2
        c = wa.cell(r, 6, _val(row["gdp_per_capita_usd"]))
        c.number_format = NUM
        for col in range(1, 7):
            wa.cell(r, col).font = BLUE
        wa.cell(r, 7, f'=IF(OR(B{r}="",D{r}=""),"",(B{r}+D{r})*100)').number_format = "0.0"
        wa.cell(r, 8, f'=IF(OR(E{r}="",E{r - 1}=""),"",E{r}/E{r - 1}-1)' if r > 2 else None).number_format = PCT
        if first_idx is not None and i >= first_idx:
            wa.cell(r, 9, 100 if i == first_idx else f'=IF(B{r}="",I{r - 1},I{r - 1}*(1+B{r}))').number_format = "#,##0.0"
            wa.cell(r, 10, f'=IF(I{r}="","",100*100/I{r})').number_format = "#,##0.0"
        wa.cell(r, 11, ds.status)
        for col in range(7, 12):
            wa.cell(r, col).font = BLACK if col not in (9,) or i != first_idx else BLUE
        for col in range(1, 12):
            wa.cell(r, col).border = THIN
    if ds.is_sample:
        wa.sheet_properties.tabColor = "B42318"

    # ---------------------------------------------------------------- Monthly -------------
    n_m = 0
    if m is not None:
        wm = wb.create_sheet("Monthly")
        _header(wm, ["Month", "Headline inflation (y/y)", "FX (NGN/USD)", "MPR", "Real policy rate",
                     "FX change y/y", "Inflation 12m avg", "Fixed income in US$", "Data status"],
                [11, 16, 14, 10, 14, 13, 15, 16, 18])
        n_m = len(m)
        for i, row in m.iterrows():
            r = i + 2
            wm.cell(r, 1, row["date"].to_pydatetime()).number_format = DATE
            v = _val(row["inflation_yoy"]); wm.cell(r, 2, None if v is None else v / 100).number_format = PCT2
            wm.cell(r, 3, _val(row["fx_ngn_usd"])).number_format = NUM2
            v = _val(row["mpr"]); wm.cell(r, 4, None if v is None else v / 100).number_format = PCT2
            for col in range(1, 5):
                wm.cell(r, col).font = BLUE
            wm.cell(r, 5, f'=IF(OR(B{r}="",D{r}=""),"",D{r}-B{r})').number_format = PCT2
            if r >= 14:
                wm.cell(r, 6, f'=IF(OR(C{r}="",C{r - 12}=""),"",C{r}/C{r - 12}-1)').number_format = PCT
            if r >= 13:
                wm.cell(r, 7, f'=IF(COUNT(B{r - 11}:B{r})=12,AVERAGE(B{r - 11}:B{r}),"")').number_format = PCT2
            wm.cell(r, 8, f'=IF(C{r}="","",Assumptions!$B$3/C{r})').number_format = NUM2
            wm.cell(r, 9, ds.status)
            for col in range(5, 10):
                wm.cell(r, col).font = BLACK
        if ds.is_sample:
            wm.sheet_properties.tabColor = "B42318"
        last = n_m + 1

        # ------------------------------------------------------------ Regimes ----------
        wr = wb.create_sheet("Regimes")
        for j, h in enumerate(["Metric", "Before reform date", "On/after reform date", "Change"], start=1):
            c = wr.cell(1, j, h)
            c.font, c.fill = HEAD, HEAD_FILL
        rng = lambda col: f"Monthly!${col}$2:${col}${last}"
        dates = rng("A")
        spec = [
            ("Average headline inflation", "B", PCT2), ("Average real policy rate", "E", PCT2),
            ("Average FX change y/y", "F", PCT), ("Average MPR", "D", PCT2),
        ]
        for k, (label, col, fmt) in enumerate(spec, start=2):
            wr.cell(k, 1, label)
            wr.cell(k, 2, f'=IFERROR(AVERAGEIFS({rng(col)},{dates},"<"&Assumptions!$B$2),"n/a")').number_format = fmt
            wr.cell(k, 3, f'=IFERROR(AVERAGEIFS({rng(col)},{dates},">="&Assumptions!$B$2),"n/a")').number_format = fmt
            wr.cell(k, 4, f'=IFERROR(C{k}-B{k},"n/a")').number_format = fmt
        wr.cell(6, 1, "Months with negative real policy rate")
        wr.cell(6, 2, f'=COUNTIFS({dates},"<"&Assumptions!$B$2,{rng("E")},"<0")').number_format = "0"
        wr.cell(6, 3, f'=COUNTIFS({dates},">="&Assumptions!$B$2,{rng("E")},"<0")').number_format = "0"
        wr.cell(6, 4, "=C6-B6").number_format = "0"
        wr.cell(8, 1, "Peak headline inflation")
        wr.cell(8, 2, f"=MAX({rng('B')})").number_format = PCT2
        wr.cell(9, 1, "Month of peak")
        wr.cell(9, 2, f"=INDEX({dates},MATCH(B8,{rng('B')},0))").number_format = DATE
        wr.cell(10, 1, "Latest headline inflation")
        wr.cell(10, 2, f"=INDEX({rng('B')},MATCH(9.99E+307,{rng('B')}))").number_format = PCT2
        wr.cell(11, 1, "Latest FX (NGN/USD)")
        wr.cell(11, 2, f"=INDEX({rng('C')},MATCH(9.99E+307,{rng('C')}))").number_format = NUM2
        wr.cell(12, 1, "Naira value lost vs. last pre-reform month")
        wr.cell(12, 2, (f'=IFERROR(1-LOOKUP(Assumptions!$B$2-1,{dates},{rng("C")})/B11,"n/a")')).number_format = PCT
        for row in wr.iter_rows(min_row=2, max_row=12, min_col=1, max_col=4):
            for c in row:
                c.font = BLACK
        wr.column_dimensions["A"].width = 44
        for col in "BCD":
            wr.column_dimensions[col].width = 22

        # ------------------------------------------------------------ Pass-through -----
        wp = wb.create_sheet("PassThrough")
        for j, h in enumerate(["Lag (months)", "Correlation: FX change leads inflation"], start=1):
            c = wp.cell(1, j, h)
            c.font, c.fill = HEAD, HEAD_FILL
        for lag in range(13):
            r = lag + 2
            wp.cell(r, 1, lag).font = BLUE
            x_end, y_start = last - lag, 14 + lag
            wp.cell(r, 2, f'=IFERROR(CORREL(Monthly!$F$14:$F${x_end},Monthly!$B${y_start}:$B${last}),"n/a")').number_format = "0.00"
            wp.cell(r, 2).font = BLACK
        wp.cell(16, 1, "Strongest lag (months)")
        wp.cell(16, 2, "=IFERROR(INDEX(A2:A14,MATCH(MAX(B2:B14),B2:B14,0)),\"n/a\")")
        wp.cell(17, 1, "Strongest correlation")
        wp.cell(17, 2, "=IFERROR(MAX(B2:B14),\"n/a\")").number_format = "0.00"
        wp.cell(19, 1, "Descriptive association only: it ignores fuel, food supply and base effects.")
        wp.column_dimensions["A"].width, wp.column_dimensions["B"].width = 28, 38
        for rr in (16, 17):
            for cc in (1, 2):
                wp.cell(rr, cc).font = BLACK

        # ------------------------------------------------------------ Dashboard ---------
        wd = wb.create_sheet("Dashboard", 1)
        wd["A1"] = "Nigeria economy dashboard" + ("  (SAMPLE DATA - NOT OFFICIAL STATISTICS)" if ds.is_sample else "")
        wd["A1"].font = Font(name=FONT, bold=True, size=14, color="B42318" if ds.is_sample else "1D2330")
        wm_ = wb["Monthly"]
        cats = Reference(wm_, min_col=1, min_row=14, max_row=last)

        def line(title, cols, anchor, fmt="0%", y_title=None):
            ch = LineChart()
            ch.title, ch.height, ch.width = title, 8, 16
            for col in cols:
                ch.add_data(Reference(wm_, min_col=col, min_row=13, max_row=last), titles_from_data=False)
            ch.set_categories(Reference(wm_, min_col=1, min_row=13, max_row=last))
            for s, col in zip(ch.series, cols):
                from openpyxl.chart.series import SeriesLabel
                s.tx = SeriesLabel(v=wm_.cell(1, col).value)
                s.smooth, s.graphicalProperties.line.width = False, 18000
            ch.y_axis.number_format = fmt
            ch.x_axis.number_format = "yyyy"
            ch.x_axis.delete = ch.y_axis.delete = False
            ch.legend.position = "b"
            wd.add_chart(ch, anchor)

        line("Headline inflation and 12-month average", [2, 7], "A3")
        line("FX change y/y vs inflation", [6, 2], "K3")
        bar = BarChart()
        bar.title, bar.height, bar.width = "Real policy rate (MPR minus inflation)", 8, 16
        bar.add_data(Reference(wm_, min_col=5, min_row=13, max_row=last), titles_from_data=False)
        bar.set_categories(Reference(wm_, min_col=1, min_row=13, max_row=last))
        bar.y_axis.number_format = "0%"
        bar.x_axis.number_format = "yyyy"
        bar.x_axis.delete = bar.y_axis.delete = False
        bar.x_axis.tickLblPos = "low"
        bar.legend = None
        wd.add_chart(bar, "A20")
        cats = None  # noqa: F841

    # annual charts (placed on Dashboard if it exists, else on Annual)
    host = wb["Dashboard"] if "Dashboard" in wb.sheetnames else wb.create_sheet("Dashboard", 1)
    if m is None:
        host["A1"] = "Nigeria economy dashboard" + ("  (SAMPLE DATA)" if ds.is_sample else "")
        host["A1"].font = Font(name=FONT, bold=True, size=14)
    ach = LineChart()
    ach.title, ach.height, ach.width = "Annual inflation and unemployment", 8, 16
    for col, name in ((2, "Inflation"), (4, "Unemployment")):
        ach.add_data(Reference(wa, min_col=col, min_row=2, max_row=n_a + 1), titles_from_data=False)
        from openpyxl.chart.series import SeriesLabel
        ach.series[-1].tx = SeriesLabel(v=name)
    ach.set_categories(Reference(wa, min_col=1, min_row=2, max_row=n_a + 1))
    ach.y_axis.number_format = "0%"
    ach.x_axis.delete = ach.y_axis.delete = False
    ach.legend.position = "b"
    host.add_chart(ach, "K20")

    # ---------------------------------------------------------------- Verified facts ------
    if verified is not None and len(verified):
        wv = wb.create_sheet("VerifiedFacts")
        cols = ["indicator", "period", "value", "unit", "note", "source_name", "source_url", "verified_on"]
        _header(wv, ["Indicator", "Period", "Value", "Unit", "Note", "Source", "URL", "Checked on"],
                [26, 10, 12, 14, 60, 30, 70, 12])
        for i, rec in enumerate(verified[cols].itertuples(index=False), start=2):
            for j, v in enumerate(rec, start=1):
                c = wv.cell(i, j, None if pd.isna(v) else v)
                c.font = BLUE
        wv.freeze_panes = "A2"

    # ---------------------------------------------------------------- About ---------------
    lines = [
        ("Nigeria Economic & Inflation Analysis", True),
        ("", False),
        (f"Data status: {ds.label}", True),
        ("Colour code: BLUE = input data / assumptions, BLACK = formulas. Yellow cells in Assumptions can be changed.", False),
        ("Percent inputs are stored as fractions and shown as percentages. 'Misery index' is in points (inflation + unemployment).", False),
        ("Price index: first year with inflation data = 100, then compounded by annual inflation.", False),
        ("CPI caveat: NBS rebased its CPI (new base 2024=100 from Jan 2025); y/y across the break is not strictly comparable.", False),
        ("Sheets: Dashboard, Assumptions, Annual, Monthly, Regimes, PassThrough, VerifiedFacts.", False),
        ("Sources: World Bank WDI (annual); NBS and CBN (monthly). See docs/data_sources.md in the repository.", False),
    ]
    for i, (t, b) in enumerate(lines, start=1):
        about.cell(i, 1, t).font = Font(name=FONT, bold=b, size=14 if i == 1 else 10,
                                        color="B42318" if (ds.is_sample and i == 3) else "000000")
    if ds.is_sample:
        about["A3"].fill = WARN_FILL
    about.column_dimensions["A"].width = 130

    for ws in wb.worksheets:
        _font_all(ws)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path
