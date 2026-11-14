import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import json
import os

st.set_page_config(page_title="Türkiye Burning Activity Calendar", page_icon="🔥", layout="wide")

st.title("Türkiye Burning Activity Calendar")
st.caption("Harmonized MODIS and VIIRS hot spots, 2000-2026.")

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
ALL = "All of Türkiye"
CHART_HEIGHT = 560
CARD_HEIGHT = 230


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

# Size of one grid cell in degrees (works for 0.5 or 0.1 grids)
STEP = round(float(np.diff(np.sort(grid_df["lat"].unique())).min()), 3)

# Default selection: the newest month that is not a partial month
complete = df[~df["note"].str.contains("Partial", case=False)]
default = complete.iloc[-1]

REGIONS = [ALL] + sorted(grid_df["region"].unique())
YEARS = sorted(df["year"].unique(), reverse=True)

st.write(
    "Choose a region, a year and a month to see where satellites detected "
    "fire hot spots. Use the year range to set the years shown in the calendar."
)

# Two columns: left = selectors + map, right = year range + calendar
left_col, right_col = st.columns(2, gap="large")

# ---------- 2. Selectors (left) and year range (right) ----------
with left_col:
    c0, c1, c2 = st.columns(3)
    region = c0.selectbox("Region", REGIONS)
    sel_year = c1.selectbox("Year", YEARS, index=YEARS.index(default["year"]))
    month_name = c2.selectbox("Month", MONTHS, index=int(default["month"]) - 1)
    sel_month = MONTHS.index(month_name) + 1

with right_col:
    y_min, y_max = int(df["year"].min()), int(df["year"].max())
    start_year, end_year = st.slider(
        "Calendar years: left handle = start year, right handle = end year",
        y_min, y_max, (y_min, y_max),
    )

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

# ---------- 4. Map (left) ----------
with left_col:
    st.subheader(f"Hot spot map: {month_name} {sel_year}")

    cells = region_cells[
        (region_cells["year"] == sel_year) & (region_cells["month"] == sel_month)
    ].copy()

    if region == ALL:
        center = {"lat": 39.0, "lon": 35.3}
        zoom = 4.3
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
            height=CHART_HEIGHT,
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
            f"{len(cells):,} cells with hot spots."
        )

# ---------- 5. Calendar (right) ----------
cal_data = monthly[(monthly["year"] >= start_year) & (monthly["year"] <= end_year)]


def grid(column):
    t = cal_data.pivot(index="year", columns="month", values=column)
    return t.reindex(columns=range(1, 13))


with right_col:
    st.subheader(f"Burning activity calendar: {start_year}-{end_year}")

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
    CAL_TICKS = [0, 500, 2000, 5000, 10000, 15000, 20000, 25000]
    fig.update_coloraxes(
        cmin=0,
        cmax=np.sqrt(25000),
        colorbar={"title": "Hot Spots",
                  "tickvals": [np.sqrt(v) for v in CAL_TICKS],
                  "ticktext": [f"{v:,}" for v in CAL_TICKS]},
    )

    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(dtick=1, showgrid=False)

    fig.update_layout(
        height=CHART_HEIGHT,
        margin={"l": 50, "r": 0, "t": 0, "b": 40},
        plot_bgcolor="#BDBDBD",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#FAFAFA",
    )

    st.plotly_chart(fig, theme=None)
    st.caption(f"{region}. Colour uses a square-root scale. Grey cells have no data.")

    csv_text = cal_data[["year", "month", "hotspots", "lower", "upper", "source", "confidence", "note"]].to_csv(index=False)
    st.download_button(
        label=f"Download {start_year}-{end_year} data (CSV)",
        data=csv_text,
        file_name=f"burning_activity_{region.replace(' ', '_')}_{start_year}-{end_year}.csv",
        mime="text/csv",
    )

st.divider()

# Second row: left = selected month vs. other years, right = season profile
info_left, info_right = st.columns(2, gap="large")

# ---------- 6. Selected month vs. other years (left) ----------
def info_card(value, title, text, badge="", badge_color="#FF6B6B"):
    """A box with the explanation on the left and the title + big number on the right."""
    with st.container(border=True, height=CARD_HEIGHT):
        text_col, num_col = st.columns([1, 1], vertical_alignment="center")
        badge_html = ""
        if badge:
            badge_html = (
                f"<div style='display: inline-block; margin-top: 6px; padding: 2px 10px; "
                f"border-radius: 12px; background: {badge_color}33; color: {badge_color}; "
                f"font-size: 0.85rem; white-space: nowrap;'>{badge}</div>"
            )
        text_col.caption(text)
        num_col.markdown(
            f"<div style='text-align: center; padding: 4px 0 8px 0;'>"
            f"<div style='font-size: 0.95rem; font-weight: 600; margin-bottom: 4px;'>{title}</div>"
            f"<div style='font-size: 1.8rem; font-weight: 600; line-height: 1.1; white-space: nowrap;'>{value}</div>"
            f"{badge_html}"
            f"</div>",
            unsafe_allow_html=True,
        )

with info_left:
    st.subheader("Selected month vs. other years")

    same_month = monthly[monthly["month"] == sel_month]
    row = same_month[same_month["year"] == sel_year]
    others = same_month[same_month["year"] != sel_year]
    median = others["hotspots"].median()

    # Four places for the cards: two rows, two columns
    top_left, top_right = st.columns(2)
    bottom_left, bottom_right = st.columns(2)

    if row.empty:
        top_left.info("No data for this month.")
    else:
        current = row["hotspots"].iloc[0]

        # Card 1 (top left): the selected month
        badge, badge_color = "", "#FF6B6B"
        if median > 0:
            change = (current - median) / median * 100
            badge = f"{change:+.0f}% vs. median"
            badge_color = "#FF6B6B" if change > 0 else "#66BB6A"
        extra = ". ".join(t for t in [row["range_text"].iloc[0], row["note"].iloc[0]] if t)
        with top_left:
            info_card(
                f"{current:,.0f}",
                f"{month_name} {sel_year}",
                f"Hot spots in {region} in this month (VIIRS-equivalent), "
                f"compared with the median of other years."
                + (f" {extra}." if extra else ""),
                badge,
                badge_color,
            )

        # Card 2 (top right): the median of the same month in other years
        with top_right:
            info_card(
                f"{median:,.0f}",
                f"Median of other years ({month_name})",
                f"A typical {month_name}: the middle value of {month_name} "
                f"across the other {others['hotspots'].count()} years.",
            )

        # Card 3 (bottom left): confidence
        with bottom_left:
            info_card(
                row["confidence"].iloc[0].capitalize(),
                "Confidence",
                "How reliable this number is. **High:** measured by VIIRS. "
                "**Medium:** converted from MODIS, or near real-time. "
                "**Low:** early MODIS, one satellite only.",
            )

    # Card 4 (bottom right): change between two periods (average yearly hot spots)
    yearly_total = monthly.groupby("year")["hotspots"].sum()
    early = yearly_total.loc[2003:2011].mean()
    late = yearly_total.loc[2017:2025].mean()
    if early > 0:
        period_change = (late - early) / early * 100
        with bottom_right:
            info_card(
                f"{period_change:+.0f}%",
                "2017-2025 vs. 2003-2011",
                f"Change in average yearly hot spots in {region}: "
                f"{early:,.0f} per year in 2003-2011, {late:,.0f} per year in 2017-2025.",
            )
####end of cards

# ---------- 7. Season profile (right) ----------
with info_right:
    st.subheader(f"Season profile: {sel_year}")

    profile = monthly[monthly["year"] != sel_year].groupby("month")["hotspots"]
    p_median = profile.median().reindex(range(1, 13))
    p_low = profile.quantile(0.1).reindex(range(1, 13))
    p_high = profile.quantile(0.9).reindex(range(1, 13))
    this_year = monthly[monthly["year"] == sel_year].set_index("month")["hotspots"].reindex(range(1, 13))

    fig_season = go.Figure()
    fig_season.add_trace(go.Scatter(x=MONTHS, y=p_high, mode="lines", line={"width": 0}, showlegend=False, hoverinfo="skip"))
    fig_season.add_trace(go.Scatter(x=MONTHS, y=p_low, mode="lines", fill="tonexty", fillcolor="rgba(253,141,60,0.25)",
                                    line={"width": 0}, name="Normal range (10-90%)", hoverinfo="skip"))
    fig_season.add_trace(go.Scatter(x=MONTHS, y=p_median, mode="lines", name="Median of other years",
                                    line={"color": "#FD8D3C", "width": 2, "dash": "dash"}))
    fig_season.add_trace(go.Scatter(x=MONTHS, y=this_year, name=str(sel_year),
                                    line={"color": "#FAFAFA", "width": 3}, mode="lines+markers"))
    fig_season.update_layout(
        height=400,
        margin={"l": 50, "r": 0, "t": 10, "b": 0},
        yaxis_title="Hot spots",
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#FAFAFA",
        legend={"orientation": "h", "y": -0.15},
    )
    fig_season.update_xaxes(gridcolor="rgba(255,255,255,0.1)")
    fig_season.update_yaxes(gridcolor="rgba(255,255,255,0.1)")
    st.plotly_chart(fig_season, theme=None)
    st.caption(f"{region}. Shaded band: 80% of the other years fall inside it.")

# ---------- 8. Method ----------
with st.expander("Method"):
    st.write(
        "MODIS counts (2000-2011) are converted to VIIRS-equivalent counts using "
        "month-specific factors derived from the 14-year overlap (2012-2025). "
        "Leave-one-year-out validation: 13% monthly error, 4% yearly error."
    )
