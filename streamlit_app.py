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
CUSTOM = "Custom area (lat/lon)"
CHART_HEIGHT = 560
CARD_HEIGHT = 230


# ---------- 1. Read the data ----------
CAL_COLUMNS = ["year", "month", "hotspots", "lower", "upper", "source",
               "confidence", "note", "days_with_data", "days_in_month"]
GRID_COLUMNS = ["year", "month", "lat", "lon", "region", "province", "hotspots"]


def check_columns(table, needed, file_name):
    """Stop the page with a clear message if a needed column is missing."""
    missing = [c for c in needed if c not in table.columns]
    if missing:
        st.error(f"{file_name} is missing these columns: {', '.join(missing)}")
        st.stop()


@st.cache_data
def load_data(cal_time, grid_time):
    cal = pd.read_csv("calendar_turkey.csv")
    grid_df = pd.read_csv("grid_turkey.csv")
    with open("regions_turkey.geojson", encoding="utf-8") as f:
        regions_geo = json.load(f)
    return cal, grid_df, regions_geo


# File times are passed in so that a newly uploaded file is always re-read
df, grid_df, regions_geo = load_data(
    os.path.getmtime("calendar_turkey.csv"), os.path.getmtime("grid_turkey.csv")
)
check_columns(df, CAL_COLUMNS, "calendar_turkey.csv")
check_columns(grid_df, GRID_COLUMNS, "grid_turkey.csv")

# Repeated rows would crash the calendar: keep the first one
df = df.drop_duplicates(subset=["year", "month"], keep="first")
grid_df = grid_df.drop_duplicates(subset=["year", "month", "lat", "lon", "province"], keep="first")

df["note"] = df["note"].fillna("")
df = df.sort_values(["year", "month"]).reset_index(drop=True)

# A month is complete when every day has data
df["complete"] = df["days_with_data"] == df["days_in_month"]

# Size of one grid cell in degrees (works for 0.5 or 0.1 grids)
STEP = round(float(np.diff(np.sort(grid_df["lat"].unique())).min()), 3)

# Default selection: the newest complete month
default = df[df["complete"]].iloc[-1]

REGIONS = [ALL] + sorted(grid_df["region"].unique()) + [CUSTOM]
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

    if region == CUSTOM:
        st.caption("Enter the edges of a box in decimal degrees (Türkiye: about 36-42 N, 26-45 E).")
        b1, b2, b3, b4 = st.columns(4)
        south = b1.number_input("South (lat)", 35.0, 43.0, 36.5, 0.1, format="%.1f")
        north = b2.number_input("North (lat)", 35.0, 43.0, 37.5, 0.1, format="%.1f")
        west = b3.number_input("West (lon)", 25.0, 46.0, 30.0, 0.1, format="%.1f")
        east = b4.number_input("East (lon)", 25.0, 46.0, 32.0, 0.1, format="%.1f")
        if south >= north or west >= east:
            st.error("North must be bigger than South, and East bigger than West.")
            st.stop()

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
    if region == CUSTOM:
        # Grid cells whose south-west corner is inside the box
        region_cells = grid_df[
            (grid_df["lat"] >= south) & (grid_df["lat"] < north)
            & (grid_df["lon"] >= west) & (grid_df["lon"] < east)
        ]
    else:
        region_cells = grid_df[grid_df["region"] == region]
    sums = region_cells.groupby(["year", "month"], as_index=False)["hotspots"].sum()
    monthly = df[["year", "month", "source", "confidence", "note",
                  "days_with_data", "days_in_month", "complete"]].merge(
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

# Name used in texts on the page
if region == CUSTOM:
    place = f"the box {south:.1f}-{north:.1f}°N, {west:.1f}-{east:.1f}°E"
else:
    place = region

# Range text: empty when lower and upper are the same number
monthly["range_text"] = [
    "" if round(lo) == round(up) else f"Range: {lo:,.0f} to {up:,.0f}"
    for lo, up in zip(monthly["lower"], monthly["upper"])
]
monthly["range_hover"] = [t + "<br>" if t else "" for t in monthly["range_text"]]
monthly["days_hover"] = [
    "" if done else f"Data for {d} of {n} days<br>"
    for done, d, n in zip(monthly["complete"], monthly["days_with_data"], monthly["days_in_month"])
]

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
        # Fit the whole area on the map: centre of its outer edges, zoom from its size
        if region == CUSTOM:
            lat_min, lat_max, lon_min, lon_max = south, north, west, east
        else:
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
        if region == CUSTOM:
            box = {"type": "Feature", "properties": {}, "geometry": {
                "type": "Polygon",
                "coordinates": [[[west, south], [east, south], [east, north],
                                 [west, north], [west, south]]]}}
            border_layers.append(
                {"sourcetype": "geojson", "source": box, "type": "line",
                 "color": "#FFD54F", "line": {"width": 3}}
            )
        elif region != ALL:
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
def nice_top(value):
    """Round up to a tidy number: 1, 2, 2.5 or 5 times a power of ten."""
    value = max(float(value), 10)
    power = 10 ** np.floor(np.log10(value))
    for step in [1, 2, 2.5, 5, 10]:
        if step * power >= value:
            return int(step * power)


def scale_ticks(top):
    """Tick values for a square-root colour scale from 0 to top."""
    ticks = [0]
    for share in [0.02, 0.08, 0.2, 0.4, 0.6, 0.8, 1.0]:
        v = int(nice_top(top * share)) if share < 1 else top
        if v > ticks[-1] and np.sqrt(v) - np.sqrt(ticks[-1]) > 0.08 * np.sqrt(top) and v <= top:
            ticks.append(v)
    if ticks[-1] != top:
        ticks.append(top)
    return ticks


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
        [grid(c) for c in ["hotspots", "days_hover", "range_hover", "confidence", "source", "note"]]
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
            "%{customdata[2]}"
            "Confidence: %{customdata[3]}<br>"
            "Source: %{customdata[4]}<br>"
            "%{customdata[5]}<extra></extra>"
        ),
    )

    # Colour scale: fixed 0-25,000 for all of Türkiye; fitted to the area otherwise
    if region == ALL:
        top = 25000
    else:
        top = nice_top(monthly["hotspots"].max())
    ticks = scale_ticks(top)
    labels = [f"{v:,}" for v in ticks]
    if region == ALL and table.max().max() > top:
        labels[-1] = labels[-1] + "+"
    fig.update_coloraxes(
        cmin=0,
        cmax=np.sqrt(top),
        colorbar={"title": "Hot Spots",
                  "tickvals": [np.sqrt(v) for v in ticks],
                  "ticktext": labels},
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
    scale_note = ("Fixed scale for all of Türkiye" if region == ALL
                  else f"Scale fitted to this area (0 to {top:,})")
    st.caption(f"{place[0].upper() + place[1:]}. Colour uses a square-root scale. {scale_note}. Grey cells have no data.")

    csv_text = cal_data[["year", "month", "hotspots", "lower", "upper", "source", "confidence", "note", "days_with_data", "days_in_month"]].to_csv(index=False)
    st.download_button(
        label=f"Download {start_year}-{end_year} data (CSV)",
        data=csv_text,
        file_name=f"burning_activity_{'custom_area' if region == CUSTOM else region.replace(' ', '_')}_{start_year}-{end_year}.csv",
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
            f"<div style='font-size: 2.4rem; font-weight: 600; line-height: 1.1; white-space: nowrap;'>{value}</div>"
            f"{badge_html}"
            f"</div>",
            unsafe_allow_html=True,
        )


FULL_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]


def partial_comparison(month, days, year, region_name):
    """Same first days of the month in every year, from a file like november_1_12.csv.
    Returns (value this year, median of other years, number of other years) or None."""
    file_name = f"{FULL_MONTHS[month - 1].lower()}_1_{days}.csv"
    if not os.path.exists(file_name):
        return None
    early_days = pd.read_csv(file_name)
    column = "Turkey" if region_name == ALL else region_name
    if column not in early_days.columns or "year" not in early_days.columns:
        return None
    this = early_days.loc[early_days["year"] == year, column]
    other = early_days.loc[early_days["year"] != year, column].dropna()
    if this.empty or other.empty:
        return None
    return this.iloc[0], other.median(), len(other)


with info_left:
    st.subheader("Selected month vs. other years")

    same_month = monthly[monthly["month"] == sel_month]
    row = same_month[same_month["year"] == sel_year]
    # Only complete months go into the median
    others = same_month[(same_month["year"] != sel_year) & same_month["complete"]]
    median = others["hotspots"].median()

    # Four places for the cards: two rows, two columns
    top_left, top_right = st.columns(2)
    bottom_left, bottom_right = st.columns(2)

    if row.empty:
        top_left.info("No data for this month.")
    else:
        current = row["hotspots"].iloc[0]
        is_complete = bool(row["complete"].iloc[0])
        days = int(row["days_with_data"].iloc[0])
        days_total = int(row["days_in_month"].iloc[0])
        extra = ". ".join(t for t in [row["range_text"].iloc[0], row["note"].iloc[0]] if t)
        full_name = FULL_MONTHS[sel_month - 1]

        if is_complete:
            # Card 1 and 2 for a complete month: whole month vs. median of whole months
            badge, badge_color = "", "#FF6B6B"
            if median > 0:
                change = (current - median) / median * 100
                badge = f"{change:+.0f}% vs. median"
                badge_color = "#FF6B6B" if change > 0 else "#66BB6A"
            with top_left:
                info_card(
                    f"{current:,.0f}",
                    f"{month_name} {sel_year}",
                    f"Hot spots in {place} in this month (VIIRS-equivalent), "
                    f"compared with the median of other years."
                    + (f" {extra}." if extra else ""),
                    badge,
                    badge_color,
                )
            with top_right:
                info_card(
                    f"{median:,.0f}",
                    f"Median of other years ({month_name})",
                    f"A typical {month_name}: the middle value of {month_name} "
                    f"across the other {others['hotspots'].count()} complete years.",
                )
        else:
            # Card 1 and 2 for a partial month: same first days in every year
            result = partial_comparison(sel_month, days, sel_year, region)
            if result is None:
                with top_left:
                    info_card(
                        f"{current:,.0f}",
                        f"{month_name} {sel_year} (1-{days})",
                        f"Partial month: {days} of {days_total} days. "
                        f"No same-days data to compare with, so no percentage is shown.",
                    )
            else:
                early_now, early_median, n_years = result
                badge, badge_color = "", "#FF6B6B"
                if early_median > 0:
                    change = (early_now - early_median) / early_median * 100
                    word = "above" if change > 0 else "below"
                    badge = f"{abs(change):.0f}% {word} the median"
                    badge_color = "#FF6B6B" if change > 0 else "#66BB6A"
                with top_left:
                    info_card(
                        f"{early_now:,.0f}",
                        f"{month_name} 1-{days}, {sel_year}",
                        f"Partial month: {days} of {days_total} days. Hot spots in the "
                        f"first {days} days of {full_name} {sel_year} in {place}, compared "
                        f"with the same {days} days in other years.",
                        badge,
                        badge_color,
                    )
                with top_right:
                    info_card(
                        f"{early_median:,.0f}",
                        f"Median, {month_name} 1-{days}",
                        f"The middle value of the first {days} days of {full_name} "
                        f"across the other {n_years} years.",
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

    # Card 4 (bottom right): change between two periods, complete years only
    full_years = monthly[monthly["complete"]].groupby("year")["month"].count()
    full_years = full_years[full_years == 12].index
    yearly_total = monthly[monthly["year"].isin(full_years)].groupby("year")["hotspots"].sum()
    early_years = yearly_total.loc[2003:2011]
    late_years = yearly_total.loc[2017:2025]
    if len(early_years) > 0 and len(late_years) > 0 and early_years.mean() > 0:
        early, late = early_years.mean(), late_years.mean()
        period_change = (late - early) / early * 100
        with bottom_right:
            info_card(
                f"{period_change:+.0f}%",
                "2017-2025 vs. 2003-2011",
                f"Change in average yearly hot spots in {place}: "
                f"{early:,.0f} per year in 2003-2011, {late:,.0f} per year in 2017-2025 "
                f"({len(early_years) + len(late_years)} complete years).",
            )

# ---------- 7. Season profile (right) ----------
with info_right:
    st.subheader(f"Season profile: {sel_year}")
    st.caption(
        f"How each month of {sel_year} (white line) compares with a normal year in {place}. "
        "Orange dashed line: the median of the other years. Shaded band: the range where "
        "80% of the other years fall. A white point above the band means an unusually active month."
    )

    # Normal range and median: complete months of other years only
    profile = monthly[(monthly["year"] != sel_year) & monthly["complete"]].groupby("month")["hotspots"]
    p_median = profile.median().reindex(range(1, 13))
    p_low = profile.quantile(0.1).reindex(range(1, 13))
    p_high = profile.quantile(0.9).reindex(range(1, 13))

    year_rows = monthly[monthly["year"] == sel_year].set_index("month").reindex(range(1, 13))
    year_done = year_rows["complete"].fillna(False).astype(bool)
    year_part = year_rows["hotspots"].notna() & ~year_done
    # Solid line: complete months. Dashed line: from the last complete month to a partial month.
    this_year = year_rows["hotspots"].where(year_done)
    dashed = year_rows["hotspots"].where(year_part | year_part.shift(-1, fill_value=False))

    # One clear hover box per month, attached to the median line
    hover_text = []
    for m in range(1, 13):
        value = year_rows.loc[m, "hotspots"]
        if pd.isna(value):
            year_line = f"{sel_year}: no data"
        elif year_part[m]:
            year_line = (f"{sel_year}: {value:,.0f} (partial month, "
                         f"{int(year_rows.loc[m, 'days_with_data'])} of "
                         f"{int(year_rows.loc[m, 'days_in_month'])} days)")
        else:
            year_line = f"{sel_year}: {value:,.0f}"
        hover_text.append(
            f"<b>{FULL_MONTHS[m - 1]}</b><br>{year_line}<br>"
            f"Median of other years: {p_median[m]:,.0f}<br>"
            f"Normal range: {p_low[m]:,.0f} to {p_high[m]:,.0f}"
        )

    fig_season = go.Figure()
    fig_season.add_trace(go.Scatter(x=MONTHS, y=p_high, mode="lines", line={"width": 0}, showlegend=False, hoverinfo="skip"))
    fig_season.add_trace(go.Scatter(x=MONTHS, y=p_low, mode="lines", fill="tonexty", fillcolor="rgba(253,141,60,0.25)",
                                    line={"width": 0}, name="Normal range (10-90%)", hoverinfo="skip"))
    fig_season.add_trace(go.Scatter(x=MONTHS, y=p_median, mode="lines", name="Median of other years",
                                    line={"color": "#FD8D3C", "width": 2, "dash": "dash"},
                                    text=hover_text, hovertemplate="%{text}<extra></extra>"))
    fig_season.add_trace(go.Scatter(x=MONTHS, y=this_year, name=str(sel_year),
                                    line={"color": "#FAFAFA", "width": 3}, mode="lines+markers",
                                    hoverinfo="skip"))
    if year_part.any():
        fig_season.add_trace(go.Scatter(
            x=MONTHS, y=dashed, name=f"{sel_year} (partial month)", mode="lines+markers",
            line={"color": "#FAFAFA", "width": 2, "dash": "dot"},
            marker={"symbol": "circle-open",
                    "size": [11 if p else 0 for p in year_part], "color": "#FAFAFA"},
            hoverinfo="skip",
        ))
    fig_season.update_layout(
        height=400,
        margin={"l": 50, "r": 0, "t": 10, "b": 0},
        yaxis_title="Hot spots",
        hovermode="x",
        hoverlabel={"bgcolor": "#262730", "bordercolor": "#FD8D3C",
                    "font": {"color": "#FAFAFA"}, "align": "left"},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#FAFAFA",
        legend={"orientation": "h", "y": -0.15},
    )
    fig_season.update_xaxes(gridcolor="rgba(255,255,255,0.1)")
    fig_season.update_yaxes(gridcolor="rgba(255,255,255,0.1)")
    st.plotly_chart(fig_season, theme=None)

# ---------- 8. Method ----------
with st.expander("Method"):
    st.write(
        "MODIS counts (2000-2011) are converted to VIIRS-equivalent counts using "
        "month-specific factors derived from the 14-year overlap (2012-2025). "
        "Leave-one-year-out validation: 13% monthly error, 4% yearly error."
    )
