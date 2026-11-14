import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Türkiye Fire Activity Calendar", page_icon="🔥", layout="wide")

st.title("Türkiye Fire Activity Calendar")
st.write("Harmonized MODIS and VIIRS hot spots, 2000-2026.")

df = pd.read_csv("calendar_turkey.csv")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

table = df.pivot(index="year", columns="month", values="hotspots")
table = table.reindex(columns=range(1,13))
table.columns = MONTHS

st.subheader("Burning Activity Calendar")

fig = px.imshow(
  table,
  color_continuous_scale="Inferno",
  labels={"x": "Month", "y": "Year", "color": "Hot Spots"},
  aspect="auto",
)
fig.update_yaxes(dtick=1)
fig.update_layout(height=750)

st.plotly_chart(fig)
