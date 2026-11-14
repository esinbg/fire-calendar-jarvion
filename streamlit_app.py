import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

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


@st.cache_data
def load_data():
    cal = pd.read_csv("calendar_turkey.csv")
    cal["note"] = cal["note"].fillna("")
    cal = cal.sort_values(["year", "month"]).reset_index(drop=True)
    grid_df = pd.read_csv("grid_turkey.csv")
    return cal, grid_df


df, grid_df = load_data()

complete = df[~df["note"].str.contains("Partial", case=False)]
default = complete.iloc[-1]

REGIONS = [ALL] + sorted(grid_df["region"].unique())
YEARS = sorted(df["year"].unique(), reverse=True)

c0, c1, c2 = st.columns(3)
region = c0.selectbox("Region", REGIONS)
sel_year = c1.selectbox("Year", YEARS, index=YEARS.index(default["year"]))
month_name = c2.selectbox("Month", MONTHS, index=int(default["month"]) - 1)
sel_month = MONTHS.index(month_name) + 1

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

st.subheader("Hot spot map")

cells = region_cells[
    (region_cells["year"] == sel_year) & (region_cells["month"] == sel_month)
].copy()

if region == ALL:
    center = {"lat": 39.0, "lon": 35.3}
    zoom = 4.8
else:
    center = {"lat": region_cells["lat"].mean() + 0.25, "lon": region_cells["lon"].mean() + 0.25}
    zoom = 5.8

if cells.empty:
    st.info("No hot spots on the map for this month.")
else:
    cells["center_lat"] = cells["lat"] + 0.25
    cells["center_lon"] = cells["lon"] + 0.25
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
    fig_map.update_traces(marker={"size": 11, "opacity": 0.85})
    log_colorbar(fig_map, cells["hotspots"].min(), cells["hotspots"].max())
    fig_map.update_layout(
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#FAFAFA",
    )

    st.plotly_chart(fig_map, theme=None)
    st.caption(
        f"Each dot is a 0.5° x 0.5° grid cell (about 50 km). "
        f"{len(cells):,} cells with hot spots in {month_name} {sel_year}."
    )

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
    st.caption(f"Range: {row['lower'].iloc[0]:,.0f} to {row['upper'].iloc[0]:,.0f}. {row['note'].iloc[0]}")

st.subheader("Burning activity calendar")


def grid(column):
    t = monthly.pivot(index="year", columns="month", values=column)
    return t.reindex(columns=range(1, 13))


table = grid("hotspots")
table.columns = MONTHS
colors = np.log10(table.clip(lower=1))

details = np.dstack(
    [grid(c) for c in ["hotspots", "lower", "upper", "confidence", "source", "note"]]
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
        "Range: %{customdata[1]:,.0f} to %{customdata[2]:,.0f}<br>"
        "Confidence: %{customdata[3]}<br>"
        "Source: %{customdata[4]}<br>"
        "%{customdata[5]}<extra></extra>"
    ),
)

log_colorbar(fig, table.min().min(), table.max().max())

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

st.caption(f"{region}. Colour uses a logarithmic scale. Grey cells have no data.")
