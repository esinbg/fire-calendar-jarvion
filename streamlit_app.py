import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np 

st.set_page_config(page_title="Türkiye Burning Activity Calendar", page_icon="🔥", layout="wide")

st.title("Türkiye Burning Activity Calendar")
st.caption("Harmonized MODIS and VIIRS hot spots, 2000-2026.")

df = pd.read_csv("calendar_turkey.csv")
df["note"] = df["note"].fillna("") 
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

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

fig.update_coloraxes(
  colorbar={
    "title": "Hot Spots",
    "tickvals": [0, 1, 2, 3, 4],
    "ticktext": ["1", "10", "100", "1,000", "10,000"],
  }
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

