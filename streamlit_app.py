import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import json
import os

st.set_page_config(page_title="Türkiye Burning Activity Calendar", page_icon="🔥")

st.markdown(
    """
    <style>
    .st-key-calendar {
        width: 92vw !important;
        max-width: 92vw !important;
        position: relative;
        left: 50%;
        transform: translateX(-50%);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Türkiye Burning Activity Calendar")
st.caption("Harmonized MODIS and VIIRS hot spots, 2000-2026.")

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
ALL = "All of Türkiye"


def log_colorbar(fig, low, high):
    """Colour bar on a log scale, labelled with real numbers from min to max."""
    low = max(low, 1)
    low_log = np.log10(low)
    high_log = np.log10(max(high, low))
    ticks = [low_log]
    labels = [f"{low:,.0f}"]
    for p in range(0, 10):
        if low_log + 0.15 < p < high_log - 0.15:
            ticks.append(p)
            labels.append(f"{10**p:,}")
    ticks.append(high_log)
    labels.append(f"{max(high, low):,.0f}")
    fig.update_coloraxes(
        cmin=low_log,
        cmax=high_log,
        colorbar={"title": "Hot Spots", "tickvals": ticks, "ticktext": labels},
    )


def sqrt_colorbar(fig, high):
    """Colour bar on a square-root scale, labelled with real numbers."""
    top = np.sqrt(max(high, 1))
    ticks = [0]
    labels = ["0"]
    for v in [10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000]:
        if v <= high and np.sqrt(v) - ticks[-1] > 0.08 * top:
            ticks.append(np.sqrt(v))
            labels.append(f"{v:,}")
    fig.update_coloraxes(
        cmin=0,
        cmax=top,
        colorbar={"title": "Hot Spots", "tickvals": ticks, "ticktext": labels},
    )


# ---------- 1. Read the data ----------
@st.cache_data
def load_data(cal_time, grid_time):
    cal = pd.read_csv("calendar_turkey.csv")
    cal["note"] = cal["note"].fillna("")
    cal = cal.sort_values(["year", "month"]).reset_index(drop=True)
    grid_df = pd.read_csv("grid_turkey.csv")
    with open("regions_turkey.geojson", encoding="utf-8") as f:
        regions_geo = json.load(f)
    return cal, grid_df, regions_geo


# File times are passed in so that a newly uploaded file is always re-read
df, grid_df, regions_geo = load_data(
    os.path.getmtime("calendar_turkey.csv"), os.path.getmtime("grid_turkey.csv")
)

# Size of one grid cell in degrees (0.5 now; works if the grid gets finer)
STEP = round(float(np.diff(np.sort(grid_df["lat"].unique())).min()), 3)

# Default selection: the newest month that is not a partial month
complete = df[~df["note"].str.contains("Partial", case=False)]
default = complete.iloc[-1]

REGIONS = [ALL] + sorted(grid_df["region"].unique())
YEARS = sorted(df["year"].unique(), reverse=True)

# ---------- 2. Selection row ----------
c0, c1, c2 = st.columns(3)
region = c0.selectbox("Region", REGIONS)
sel_year = c1.selectbox("Year", YEARS, index=YEARS.index(default["year"]))
month_name = c2.selectbox("Month", MONTHS, index=int(default["month"]) - 1)
sel_month = MONTHS.index(month_name) + 1

# ---------- 3. Monthly table for the selected region ----------
if region == ALL:
    monthly = df.copy()
    region_cells = grid_df
else:
    region_cells = grid_df[grid_df["region"] == region]
    sums = region_cells.groupby(["year", "month"], as_index=False)["hotspots"].sum()
    monthly = df[["year", "month", "source", "confidence", "note"]].merge(
        sums, on=["year", "month"], how="left"
    )
    monthly["hotspots"] = monthly["hotspots"].fillna(0)
    ratio_low = (df["lower"] / df["hotspots"]).where(df["hotspots"] > 0, 1)
    ratio_up = (df["upper"] / df["hotspots"]).where(df["hotspots"] > 0, 1)
    monthly["lower"] = monthly["hotspots"] * ratio_low
    monthly["upper"] = monthly["hotspots"] * ratio_up

    yearly = monthly.groupby("year")["hotspots"].sum()
    if yearly.median() < 300:
        st.warning("Small area: estimates are less reliable.")

# Range text: empty when lower and upper are the same number
monthly["range_text"] = [
    "" if round(lo) == round(up) else f"Range: {lo:,.0f} to {up:,.0f}"
    for lo, up in zip(monthly["lower"], monthly["upper"])
]
monthly["range_hover"] = [t + "<br>" if t else "" for t in monthly["range_text"]]

# ---------- 4. Map ----------
st.subheader("Hot spot map")

cells = region_cells[
    (region_cells["year"] == sel_year) & (region_cells["month"] == sel_month)
].copy()

if region == ALL:
    center = {"lat": 39.0, "lon": 35.3}
    zoom = 4.4
else:
    # Fit the whole region on the map: centre of its outer edges, zoom from its size
    lat_min, lat_max = region_cells["lat"].min(), region_cells["lat"].max() + STEP
    lon_min, lon_max = region_cells["lon"].min(), region_cells["lon"].max() + STEP
    center = {"lat": (lat_min + lat_max) / 2, "lon": (lon_min + lon_max) / 2}
    zoom_lon = np.log2(600 * 360 / (512 * (lon_max - lon_min)))
    zoom_lat = np.log2(450 * 360 / (512 * (lat_max - lat_min) * 1.3))
    zoom = min(zoom_lon, zoom_lat) - 0.3

if cells.empty:
    st.info("No hot spots on the map for this month.")
else:
    cells["center_lat"] = cells["lat"] + STEP / 2
    cells["center_lon"] = cells["lon"] + STEP / 2
    cells["color"] = np.log10(cells["hotspots"].clip(lower=1))

    fig_map = px.scatter_map(
        cells,
        lat="center_lat",
        lon="center_lon",
        color="color",
        color_continuous_scale="YlOrRd",
        hover_name="province",
        hover_data={"hotspots": ":,.1f", "region": True, "lat": True, "lon": True,
                    "center_lat": False, "center_lon": False, "color": False},
        center=center,
        zoom=zoom,
        height=550,
        map_style="carto-darkmatter",
    )
    fig_map.update_traces(marker={"size": max(4, STEP * 12), "opacity": 0.9})

    # Region borders: thin lines for all regions, thick line for the selected one
    border_layers = [
        {"sourcetype": "geojson", "source": regions_geo, "type": "line",
         "color": "#FFFFFF", "line": {"width": 1.2}},
    ]
    if region != ALL:
        selected = {"type": "FeatureCollection",
                    "features": [f for f in regions_geo["features"]
                                 if f["properties"]["region"] == region]}
        border_layers.append(
            {"sourcetype": "geojson", "source": selected, "type": "line",
             "color": "#FFD54F", "line": {"width": 3}}
        )
    fig_map.update_layout(map={"layers": border_layers})
    # Fixed colour scale for the map: 1 to 1,000 hot spots per cell
    fig_map.update_coloraxes(
        cmin=0,
        cmax=3,
        colorbar={"title": "Hot Spots", "tickvals": [0, 1, 2, 3],
                  "ticktext": ["1", "10", "100", "1,000+"]},
    )
    fig_map.update_layout(
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#FAFAFA",
    )

    st.plotly_chart(fig_map, theme=None)
    st.caption(
        f"Each dot is a {STEP:g}° x {STEP:g}° grid cell. White lines are region borders. "
        f"{len(cells):,} cells with hot spots in {month_name} {sel_year}."
    )

# ---------- 5. Selected month vs. other years ----------
st.subheader("Selected month vs. other years")

same_month = monthly[monthly["month"] == sel_month]
row = same_month[same_month["year"] == sel_year]
others = same_month[same_month["year"] != sel_year]
median = others["hotspots"].median()

if row.empty:
    st.info("No data for this month.")
else:
    current = row["hotspots"].iloc[0]
    m1, m2, m3 = st.columns(3)
    if median > 0:
        change = (current - median) / median * 100
        m1.metric(f"{month_name} {sel_year}", f"{current:,.0f}", f"{change:+.0f}% vs. median", delta_color="inverse", border=True)
    else:
        m1.metric(f"{month_name} {sel_year}", f"{current:,.0f}", border=True)
    m2.metric(f"Median of other years ({month_name})", f"{median:,.0f}", border=True)
    m3.metric("Confidence", row["confidence"].iloc[0].capitalize(), border=True)
    details_text = ". ".join(t for t in [row["range_text"].iloc[0], row["note"].iloc[0]] if t)
    if details_text:
        st.caption(details_text)

# Change between two periods: average yearly hot spots
yearly_total = monthly.groupby("year")["hotspots"].sum()
early = yearly_total.loc[2003:2011].mean()
late = yearly_total.loc[2017:2025].mean()
if early > 0:
    period_change = (late - early) / early * 100
    st.metric(
        "Average yearly hot spots, 2017-2025 vs. 2003-2011",
        f"{period_change:+.0f}%",
        help=f"2003-2011: {early:,.0f} per year. 2017-2025: {late:,.0f} per year.",
        border=True,
    )

# ---------- 6. Calendar ----------
st.subheader("Burning activity calendar")

y_min, y_max = int(df["year"].min()), int(df["year"].max())
start_year, end_year = st.slider("Years", y_min, y_max, (y_min, y_max))
cal_data = monthly[(monthly["year"] >= start_year) & (monthly["year"] <= end_year)]


def grid(column):
    t = cal_data.pivot(index="year", columns="month", values=column)
    return t.reindex(columns=range(1, 13))


table = grid("hotspots")
table.columns = MONTHS
colors = np.sqrt(table)

details = np.dstack(
    [grid(c) for c in ["hotspots", "range_hover", "confidence", "source", "note"]]
)

fig = px.imshow(
    colors,
    color_continuous_scale="YlOrRd",
    labels={"x": "Month", "y": "Year", "color": "Hot Spots"},
    aspect="auto",
)

fig.update_traces(
    customdata=details,
    hovertemplate=(
        "<b>%{x} %{y}</b><br>"
        "Hot spots: %{customdata[0]:,.0f}<br>"
        "%{customdata[1]}"
        "Confidence: %{customdata[2]}<br>"
        "Source: %{customdata[3]}<br>"
        "%{customdata[4]}<extra></extra>"
    ),
)

# Fixed colour scale: the same colours mean the same numbers in every region
CAL_TICKS = [0, 500, 2000, 5000, 10000, 20000]
fig.update_coloraxes(
    cmin=0,
    cmax=np.sqrt(20000),
    colorbar={"title": "Hot Spots",
              "tickvals": [np.sqrt(v) for v in CAL_TICKS],
              "ticktext": [f"{v:,}" for v in CAL_TICKS]},
)

fig.update_xaxes(showgrid=False)
fig.update_yaxes(dtick=1, showgrid=False)

fig.update_layout(
    height=750,
    plot_bgcolor="#BDBDBD",
    paper_bgcolor="rgba(0,0,0,0)",
    font_color="#FAFAFA",
)

with st.container(key="calendar"):
    st.plotly_chart(fig, theme=None)

st.caption(f"{region}, {start_year}-{end_year}. Colour uses a square-root scale. Grey cells have no data.")

csv_text = cal_data[["year", "month", "hotspots", "lower", "upper", "source", "confidence", "note"]].to_csv(index=False)
st.download_button(
    label="Download this table (CSV)",
    data=csv_text,
    file_name=f"burning_activity_{region.replace(' ', '_')}_{start_year}-{end_year}.csv",
    mime="text/csv",
)

# ---------- 7. Season profile ----------
st.subheader("Season profile")

profile = monthly[monthly["year"] != sel_year].groupby("month")["hotspots"]
p_median = profile.median().reindex(range(1, 13))
p_low = profile.quantile(0.1).reindex(range(1, 13))
p_high = profile.quantile(0.9).reindex(range(1, 13))
this_year = monthly[monthly["year"] == sel_year].set_index("month")["hotspots"].reindex(range(1, 13))

fig_season = go.Figure()
fig_season.add_trace(go.Scatter(x=MONTHS, y=p_high, line={"width": 0}, showlegend=False, hoverinfo="skip"))
fig_season.add_trace(go.Scatter(x=MONTHS, y=p_low, fill="tonexty", fillcolor="rgba(253,141,60,0.25)",
                                line={"width": 0}, name="Normal range (10-90%)", hoverinfo="skip"))
fig_season.add_trace(go.Scatter(x=MONTHS, y=p_median, name="Median of other years",
                                line={"color": "#FD8D3C", "width": 2, "dash": "dash"}))
fig_season.add_trace(go.Scatter(x=MONTHS, y=this_year, name=str(sel_year),
                                line={"color": "#FAFAFA", "width": 3}, mode="lines+markers"))
fig_season.update_layout(
    height=400,
    yaxis_title="Hot spots",
    hovermode="x unified",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#FAFAFA",
    legend={"orientation": "h", "y": -0.15},
)
st.plotly_chart(fig_season, theme=None)
st.caption(f"{region}. Shaded band: 80% of the other years fall inside it.")

# ---------- 8. Method ----------
with st.expander("Method"):
    st.write(
        "MODIS counts (2000-2011) are converted to VIIRS-equivalent counts using "
        "month-specific factors derived from the 14-year overlap (2012-2025). "
        "Leave-one-year-out validation: 13% monthly error, 4% yearly error."
    )
