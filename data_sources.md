# Data sources & how to refresh

| Dataset | Frequency | Where to get it | How this project uses it |
|---|---|---|---|
| Inflation, GDP growth, unemployment, official FX, GDP per capita, current account | Annual | **World Bank WDI API** (`api.worldbank.org/v2/country/NGA/indicator/<CODE>?format=json`) | `make fetch` downloads it to `data/raw/worldbank_nga.csv` (no key needed) |
| Headline / food / core inflation (y/y), CPI index | Monthly | **NBS CPI reports** (nigerianstat.gov.ng) and the **CBN inflation rates table** (cbn.gov.ng/rates/inflrates.asp, has "Export to Excel") | Copy into `data/raw/manual/monthly.csv` |
| Official exchange rate (NGN/USD) | Daily / monthly avg | **CBN** official exchange rates and the CBN "Monthly Average Exchange Rates" page | Monthly average into `monthly.csv` |
| Monetary Policy Rate (MPR) | Per MPC meeting (~6/yr) | **CBN MPC decisions** (cbn.gov.ng/MonetaryPolicy/Decisions.html) | Carry the rate forward month by month in `monthly.csv` |
| Unemployment (national) | Quarterly | NBS Labour Force Survey | See the methodology warning in `data_notes.md` |

Indicator codes used: `FP.CPI.TOTL.ZG`, `NY.GDP.MKTP.KD.ZG`, `SL.UEM.TOTL.ZS`, `PA.NUS.FCRF`,
`NY.GDP.PCAP.CD`, `BN.CAB.XOKA.GD.ZS`.

`data/raw/verified_datapoints.csv` is a hand-verified fact sheet (every row has a source URL and the date it
was checked). It is **not** a complete time series: it powers the "latest official readings" and
real-policy-rate callouts and lets you spot-check any series you assemble.
