# Türkiye Burning Activity Calendar

**NASA Space Apps Challenge 2026 · Yalova Local Event · Challenge: Harmonization of MODIS and VIIRS Hot Spots**
**Team JARVION:** Esin BAĞOĞLU, Dicle BİRLEŞ

An interactive web app that converts 26 years of fire hot spot detections from two NASA satellite sensors (MODIS, 2000-2011, 1 km; VIIRS, 2012-today, 375 m) into one consistent unit and shows them as a year × month burning activity calendar for Türkiye, its seven geographic regions, or any area the user defines by coordinates.

## Links

| | |
|---|---|
| 🌐 Live web app | https://fire-calendar-jarvion.streamlit.app/#burning-activity-calendar |
| 🎬 Demo video (30 s) | https://youtu.be/pLGL-RR1104 |
| 📄 Project report | Burning_Activity_Calendar_JARVION_Report.pdf |
| 📓 Data processing notebook | [data_processing/](data_processing/) |
| 🚀 NASA Space Apps project page | [link] |

## What the app does

- **Burning activity calendar:** year × month heat map, 2000-2026, in VIIRS-equivalent units. Each cell shows the count, the uncertainty range (for converted MODIS months), the confidence level and the data source.
- **Hot spot map:** 0.1° grid cells for the selected month, with region borders.
- **Region selection:** all of Türkiye, seven geographic regions, or a custom latitude/longitude box.
- **Selected month vs. other years:** the month compared with the median of the same month in all other complete years; a fair comparison for unfinished months (same first days of the month in every year).
- **Season profile:** the selected year against the median and the normal range (10th-90th percentile) of other years.
- **Period change:** average yearly hot spots, 2017-2025 vs. 2003-2011.
- **CSV download** of any region and year range.

## Method in brief

MODIS counts (2000-2011) are converted to VIIRS-equivalent counts using month-specific factors derived from the 14-year overlap (2012-2025). Leave-one-year-out validation: 13% monthly error, 4% yearly error. Details: see the project report.

## Repository structure

| Path | Content |
|---|---|
| `streamlit_app.py` | The web app (Python, Streamlit, Plotly) |
| `requirements.txt` | Python packages for the app |
| `.streamlit/config.toml` | App theme |
| `calendar_turkey.csv` | Monthly hot spots for Türkiye with range, source, confidence and days with data |
| `grid_turkey.csv` | Monthly hot spots per 0.1° grid cell, province and region |
| `november_1_12.csv` | First 12 days of November in every year, by region (for partial-month comparison) |
| `regions_turkey.geojson` | Borders of the seven geographic regions (map lines only) |
| `data_processing/` | Google Colab notebook: FIRMS data processing and MODIS-to-VIIRS harmonization |
| `docs/` | Project report and presentation |

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Data and resources

- **NASA FIRMS** active fire / hot spot data: MODIS (Collection 6.1) and VIIRS 375 m (Suomi NPP and NOAA-20). https://firms.modaps.eosdis.nasa.gov/
- **Province boundaries** used to build `regions_turkey.geojson`: open GitHub repository cihadturhan/tr-geojson, https://github.com/cihadturhan/tr-geojson. Provinces were merged into seven regions using the province-region mapping in our grid data.
- **Base map:** CARTO Dark Matter (© CARTO, © OpenStreetMap contributors).
- **Software:** Python, Streamlit, pandas, NumPy, Plotly, Google Colab, GitHub, Streamlit Community Cloud.

## Use of AI

We used Claude (Anthropic) as an assistant. For the web app, it generated and explained most of the code in `streamlit_app.py`, helped debug it, and created `regions_turkey.geojson` from open-source province boundaries. For data processing, Claude helped write and debug the Python code in the Colab notebook (reading the FIRMS files, monthly aggregation, the MODIS-to-VIIRS conversion and its validation). Team members entered and tested the code, checked the results, and made the design and methodological decisions.

## License

MIT License, see `LICENSE` 
