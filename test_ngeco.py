import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ngeco import analysis as A  # noqa: E402
from ngeco import charts, cli, data_sources as D, excel_report, powerbi_export  # noqa: E402
from ngeco.config import WB_INDICATORS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def wb_payload(values):
    rows = [{"indicator": {"id": "X"}, "country": {"id": "NG"}, "countryiso3code": "NGA",
             "date": str(y), "value": v} for y, v in values]
    return [{"page": 1, "pages": 1, "per_page": 1000, "total": len(rows)}, rows]


class WorldBank(unittest.TestCase):
    def test_parse_drops_nulls_and_sorts(self):
        df = D.parse_worldbank(wb_payload([(2024, None), (2023, 28.9), (2022, 18.8)]))
        self.assertEqual(df["year"].tolist(), [2022, 2023])
        self.assertAlmostEqual(df.loc[1, "value"], 28.9)

    def test_parse_api_error_message(self):
        with self.assertRaises(D.DataError):
            D.parse_worldbank([{"message": [{"id": "120", "key": "Invalid value"}]}])

    def test_parse_empty(self):
        self.assertTrue(D.parse_worldbank([{"page": 1}, None]).empty)

    def test_fetch_writes_csv_and_metadata(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(D, "_get_json") as g:
            g.side_effect = lambda url, **kw: wb_payload([(2023, 1.0), (2022, 2.0)])
            df = D.fetch_worldbank(raw_dir=Path(d), start=2022, end=2023)
            self.assertEqual(g.call_count, len(WB_INDICATORS))
            self.assertTrue((Path(d) / "worldbank_nga.csv").exists())
            meta = json.loads((Path(d) / "worldbank_nga.meta.json").read_text())
            self.assertIn("fetched_at", meta)
            self.assertEqual(set(WB_INDICATORS.values()) | {"year"}, set(df.columns))
            self.assertTrue(all(u.startswith("https://api.worldbank.org/") for u in
                                [c.args[0] for c in g.call_args_list]))


class Loading(unittest.TestCase):
    def write(self, d, text):
        p = Path(d) / "m.csv"
        p.write_text(text)
        return p

    def test_monthly_loader_cleans(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.write(d, "# comment\ndate,inflation_yoy,mpr\n2024-02-15,5,10\n2024-01-01,4,10\n2024-02-01,6,11\n")
            m = D.load_monthly(p)
            self.assertEqual(len(m), 2)                       # dedupe on month, keep last
            self.assertEqual(m["date"].tolist(), sorted(m["date"].tolist()))
            self.assertEqual(m.loc[1, "inflation_yoy"], 6)
            self.assertTrue(m["fx_ngn_usd"].isna().all())      # optional column added

    def test_monthly_loader_validation(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(D.DataError):
                D.load_monthly(self.write(d, "date,mpr\n2024-01-01,5\n"))
            with self.assertRaises(D.DataError):
                D.load_monthly(self.write(d, "date,inflation_yoy\nnot-a-date,5\n"))

    def test_official_requires_fetch(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(D.DataError, "make fetch"):
                D.load_official(Path(d))

    def test_official_flags_gaps_and_short_series(self):
        s = D.generate_sample()
        with tempfile.TemporaryDirectory() as d:
            raw = Path(d)
            s.annual.to_csv(raw / "worldbank_nga.csv", index=False)
            (raw / "manual").mkdir()
            s.monthly.drop(index=[5, 6]).to_csv(raw / "manual" / "monthly.csv", index=False)
            ds = D.load_official(raw)
            self.assertFalse(ds.is_sample)
            self.assertIsNotNone(ds.monthly)
            self.assertTrue(any("missing month" in n for n in ds.notes))
            s.monthly.head(10).to_csv(raw / "manual" / "monthly.csv", index=False)
            self.assertIsNone(D.load_official(raw).monthly)

    def test_sample_is_deterministic_and_flagged(self):
        a, b = D.generate_sample(3), D.generate_sample(3)
        pd.testing.assert_frame_equal(a.monthly, b.monthly)
        self.assertTrue(a.is_sample)
        self.assertEqual(a.status, "SYNTHETIC_SAMPLE")


class VerifiedFacts(unittest.TestCase):
    def test_every_row_is_sourced(self):
        v = D.load_verified(ROOT / "data/raw/verified_datapoints.csv")
        self.assertGreater(len(v), 20)
        self.assertTrue(v["source_url"].str.startswith("http").all())
        self.assertTrue(v["period"].str.match(r"^\d{4}-\d{2}$").all())
        self.assertTrue(pd.to_numeric(v["value"], errors="coerce").notna().all())
        self.assertTrue(v["verified_on"].notna().all())

    def test_real_rate_calc(self):
        v = D.load_verified(ROOT / "data/raw/verified_datapoints.csv")
        rr = A.verified_real_rates(v).set_index("period")
        self.assertAlmostEqual(rr.loc["2026-09", "real_policy_rate"], 23.0 - 14.63, places=2)


class Analysis(unittest.TestCase):
    def test_decompose_recovers_seasonality(self):
        idx = pd.date_range("2018-01-01", periods=96, freq="MS")
        season = np.tile([3, 2, 1, 0, -1, -2, -3, -2, -1, 0, 1, 2], 8).astype(float)
        s = pd.Series(np.linspace(10, 20, 96) + season, index=idx)
        dec = A.classical_decompose(s)
        np.testing.assert_allclose(dec["seasonal"].iloc[:12], season[:12] - season[:12].mean(), atol=0.15)
        self.assertLess(dec["residual"].abs().max(), 0.5)
        with self.assertRaises(ValueError):
            A.classical_decompose(s.head(10))

    def test_mean_shift_finds_step(self):
        idx = pd.date_range("2015-01-01", periods=120, freq="MS")
        rng = np.random.default_rng(0)
        s = pd.Series(np.r_[rng.normal(10, 1, 70), rng.normal(25, 1, 50)], index=idx)
        r = A.detect_mean_shift(s)
        self.assertLessEqual(abs((r["break_date"] - idx[70]).days), 62)
        self.assertGreater(r["sse_reduction_pct"], 80)

    def test_lagged_correlation_recovers_lag(self):
        rng = np.random.default_rng(1)
        x = pd.Series(rng.normal(size=200).cumsum())
        y = x.shift(4) + rng.normal(0, 0.3, 200)
        lc = A.lagged_correlation(x, y, 8)
        self.assertEqual(int(lc.loc[lc["correlation"].idxmax(), "lag_months"]), 4)

    def test_annual_purchasing_power(self):
        a = pd.DataFrame({"year": [2000, 2001, 2002], "inflation_pct": [10.0, 10.0, 20.0],
                          "unemployment_pct": [5.0, 6.0, 7.0], "fx_ngn_usd": [100.0, 110.0, 132.0]})
        r = A.add_annual_metrics(a)
        self.assertEqual(r["price_index"].round(2).tolist(), [100.0, 110.0, 132.0])
        self.assertAlmostEqual(r.loc[2, "purchasing_power_of_100"], 100 * 100 / 132)
        self.assertEqual(r["misery_index"].tolist(), [15.0, 16.0, 27.0])
        self.assertAlmostEqual(r.loc[1, "fx_change_pct"], 10.0)

    def test_monthly_metrics_leave_gaps_blank(self):
        m = pd.DataFrame({"date": pd.to_datetime(["2024-01-01", "2024-03-01"]), "inflation_yoy": [5.0, 6.0],
                          "food_inflation_yoy": np.nan, "core_inflation_yoy": np.nan,
                          "fx_ngn_usd": [100.0, 120.0], "mpr": [10.0, 10.0]})
        r = A.add_monthly_metrics(m)
        self.assertEqual(len(r), 3)
        self.assertTrue(np.isnan(r.loc[1, "inflation_yoy"]))
        self.assertAlmostEqual(r.loc[2, "real_policy_rate"], 4.0)

    def test_findings_warn_on_sample(self):
        ds = D.generate_sample()
        f = A.key_findings(ds.annual, ds.monthly, "2023-06-01", is_sample=True)
        self.assertIn("SYNTHETIC", f[0])


class Outputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        cls.ds = D.generate_sample()
        cls.verified = D.load_verified(ROOT / "data/raw/verified_datapoints.csv")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_charts(self):
        paths = charts.build_all(self.ds, self.out / "c", "2023-06-01", "2025-01-01")
        self.assertEqual(len(paths), 7)
        self.assertTrue(all(p.exists() and p.stat().st_size > 5_000 for p in paths))

    def test_annual_only_dataset_skips_monthly_charts(self):
        ds = D.Dataset(self.ds.annual, None, False)
        self.assertEqual(len(charts.build_all(ds, self.out / "c2", "2023-06-01", "2025-01-01")), 2)

    def test_excel_uses_formulas_and_input_colours(self):
        from openpyxl import load_workbook
        p = excel_report.build_workbook(self.ds, self.out / "w.xlsx", "2023-06-01", self.verified)
        wb = load_workbook(p)
        self.assertIn("SAMPLE", wb["About"]["A3"].value)
        monthly = wb["Monthly"]
        self.assertTrue(str(monthly["E20"].value).startswith("="))          # real policy rate is a formula
        self.assertTrue(str(monthly["G20"].value).startswith("=AVERAGE") or "AVERAGE" in str(monthly["G20"].value))
        self.assertEqual(monthly["B20"].font.color.rgb, "000000FF")         # input = blue
        self.assertTrue(str(wb["Regimes"]["B2"].value).startswith("=IFERROR(AVERAGEIFS"))
        self.assertEqual(wb["Assumptions"]["B2"].font.color.rgb, "000000FF")
        n_formulas = sum(1 for ws in wb for row in ws.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("="))
        self.assertGreater(n_formulas, 400)
        self.assertEqual(len(wb["Dashboard"]._charts), 4)

    def test_powerbi_star_schema(self):
        files = powerbi_export.export(self.ds, self.out / "pbi", "2023-06-01", "2025-01-01", self.verified)
        names = {f.name for f in files}
        self.assertTrue({"dim_date.csv", "fact_monthly.csv", "fact_annual.csv", "fact_verified.csv", "theme.json"} <= names)
        dd = pd.read_csv(self.out / "pbi" / "dim_date.csv", parse_dates=["date"])
        self.assertEqual(set(dd["regime"]), {"Pre-reform", "Post-reform"})
        self.assertEqual(set(dd["cpi_base"]), {"Old CPI base (2009)", "New CPI base (2024)"})
        self.assertTrue(dd["date"].is_unique)
        fm = pd.read_csv(self.out / "pbi" / "fact_monthly.csv", parse_dates=["date"])
        self.assertLess(fm["inflation_yoy"].max(), 1.0)                     # exported as fractions
        self.assertEqual(set(fm["date"]), set(dd["date"]))                  # every fact row joins to dim_date
        fv = pd.read_csv(self.out / "pbi" / "fact_verified.csv")
        self.assertTrue(fv["period_date"].notna().all())
        json.loads((self.out / "pbi" / "theme.json").read_text())

    def test_cli_sample_and_missing_official(self):
        with mock.patch.object(cli, "OUTPUT_DIR", self.out / "cli"):
            self.assertEqual(cli.main(["build", "--mode", "sample"]), 0)
            self.assertTrue((self.out / "cli" / "sample" / "findings.md").exists())
        with tempfile.TemporaryDirectory() as d, mock.patch.object(D, "RAW_DIR", Path(d)), \
                mock.patch.object(D, "load_official", side_effect=D.DataError("no data")):
            self.assertEqual(cli.main(["build", "--mode", "official"]), 2)


if __name__ == "__main__":
    unittest.main()
