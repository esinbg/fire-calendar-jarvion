import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

st.set_page_config(page_title="Türkiye Burning Activity Calendar", page_icon="🔥")

st.title("Türkiye Burning Activity Calendar")
st.caption("Harmonized MODIS and VIIRS hot spots, 2000-2026.")

df = pd.read_csv("calendar_turkey.csv")
df["note"] = df["note"].fillna("")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Sort the table by date, so "newest" always means the latest month
df = df.sort_values(["year", "month"]).reset_index(drop=True)

# Default selection: the newest month that is not a partial month
complete = df[~df["note"].str.contains("Partial", case=False)]
default = complete.iloc[-1]

REGIONS = ["Türkiye", "Marmara", "Black Sea", "Central Anatolia",
           "Eastern Anatolia", "Southeastern Anatolia", "Mediterranean", "Aegean"]
YEARS = sorted(df["year"].unique(), reverse=True)

c0, c1, c2 = st.columns(3)
region = c0.selectbox("Region", REGIONS)
sel_year = c1.selectbox("Year", YEARS, index=YEARS.index(default["year"]))
month_name = c2.selectbox("Month", MONTHS, index=int(default["month"]) - 1)
sel_month = MONTHS.index(month_name) + 1

if region != "All of Türkiye":
    st.info("Regional data is not connected yet. Showing all of Türkiye.")

st.subheader("Hot spot map")
st.info("Map coming next.")

st.subheader("Selected month vs. other years")

same_month = df[df["month"] == sel_month]
row = same_month[same_month["year"] == sel_year]
others = same_month[same_month["year"] != sel_year]
median = others["hotspots"].median()

if row.empty:
    st.info("No data for this month.")
else:
    current = row["hotspots"].iloc[0]
    change = (current - median) / median * 100
    m1, m2, m3 = st.columns(3)
    m1.metric(f"{month_name} {sel_year}", f"{current:,.0f}", f"{change:+.0f}% vs. median", delta_color="inverse", border=True)
    m2.metric(f"Median of other years ({month_name})", f"{median:,.0f}", border=True)
    m3.metric("Confidence", row["confidence"].iloc[0].capitalize(), border=True)
    st.caption(f"Range: {row['lower'].iloc[0]:,.0f} to {row['upper'].iloc[0]:,.0f}. {row['note'].iloc[0]}")

st.subheader("Burning activity calendar")

table = df.pivot(index="year", columns="month", values="hotspots")
table = table.reindex(columns=range(1,13))
table.columns = MONTHS
colors = np.log10(table.clip(lower=1))

def grid(column):
  t = df.pivot(index="year", columns="month", values=column)
  return t.reindex(columns=range(1, 13))

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

low = table.min().min()
high = table.max().max()
low_log = np.log10(max(low, 1))
high_log = np.log10(high)

ticks = [low_log]
labels = [f"{low:,.0f}"]
for p in range(0, 10):
    if low_log + 0.15 < p < high_log - 0.15:
        ticks.append(p)
        labels.append(f"{10**p:,}")
ticks.append(high_log)
labels.append(f"{high:,.0f}")

fig.update_coloraxes(
  cmin=low_log,
  cmax=high_log,
  colorbar={"title": "Hot Spots", "tickvals": ticks, "ticktext": labels},
)

fig.update_xaxes(showgrid=False)
fig.update_yaxes(dtick=1, showgrid=False)

fig.update_layout(
  height=750,
  plot_bgcolor="#BDBDBD",
  paper_bgcolor="rgba(0,0,0,0)",
  font_color="#FAFAFA",
)

st.plotly_chart(fig, theme=None)

st.caption("Colour uses a logarithmic scale. Grey cells have no data.")
