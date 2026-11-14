import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np 

st.set_page_config(page_title="Türkiye Fire Activity Calendar", page_icon="🔥", layout="wide")

st.title("Türkiye Fire Activity Calendar")
st.write("Harmonized MODIS and VIIRS hot spots, 2000-2026.")

df = pd.read_csv("calendar_turkey.csv")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

table = df.pivot(index="year", columns="month", values="hotspots")
table = table.reindex(columns=range(1,13))
table.columns = MONTHS
colors = np.log10(table.clip(lower=1))

st.subheader("Burning Activity Calendar")

fig = px.imshow(
  colors,
  color_continuous_scale="Inferno",
  labels={"x": "Month", "y": "Year", "color": "Hot Spots"},
  aspect="auto",
fig.update_coloraxes(
  colorbar={
    "title": "Hot Spots",
    "tickvals": [0, 1, 2, 3, 4],
    "ticktext": ["1", "10", "100", "1,000", "10,000"],
  }
)
fig.update_yaxes(dtick=1)
fig.update_layout(height=750)

st.plotly_chart(fig)
