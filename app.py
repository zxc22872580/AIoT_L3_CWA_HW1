"""
app.py
台灣即時氣象地圖 — 1:1 復刻 taiwan-weather-map.vercel.app
全螢幕 Folium 地圖 + 右上角浮動圖層面板 + 右下角色階圖例
"""

import os
import sys
import sqlite3
from typing import Dict, Tuple
import pandas as pd
import folium
from streamlit_folium import st_folium
import streamlit as st

# 處理 Windows 控制台編碼
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 導入 ETL 模組
try:
    from fetch_cwa_data import run_etl_pipeline, DB_PATH, REGION_MAPPING
except ImportError:
    DB_PATH = "data.db"
    REGION_MAPPING = {
        "北部地區": ["基隆市", "臺北市", "新北市", "桃園市", "新竹市", "新竹縣", "苗栗縣"],
        "中部地區": ["臺中市", "彰化縣", "南投縣", "雲林縣"],
        "南部地區": ["嘉義市", "嘉義縣", "臺南市", "高雄市", "屏東縣"],
        "東北部地區": ["宜蘭縣"],
        "東部地區": ["花蓮縣"],
        "東南部地區": ["臺東縣"],
        "離島地區": ["澎湖縣", "金門縣", "連江縣"],
    }
    run_etl_pipeline = None

COORDINATES: Dict[str, Tuple[float, float]] = {
    "北部地區": (24.98, 121.35), "中部地區": (24.08, 120.70),
    "南部地區": (22.95, 120.35), "東北部地區": (24.70, 121.70),
    "東部地區": (23.85, 121.50), "東南部地區": (22.75, 121.10),
    "離島地區": (23.57, 119.57),
    "基隆市": (25.13, 121.74), "臺北市": (25.04, 121.56),
    "新北市": (25.01, 121.46), "桃園市": (24.99, 121.30),
    "新竹市": (24.81, 120.97), "新竹縣": (24.84, 121.01),
    "苗栗縣": (24.56, 120.82), "臺中市": (24.15, 120.67),
    "彰化縣": (24.08, 120.54), "南投縣": (23.91, 120.69),
    "雲林縣": (23.71, 120.43), "嘉義市": (23.48, 120.45),
    "嘉義縣": (23.45, 120.25), "臺南市": (22.99, 120.21),
    "高雄市": (22.63, 120.30), "屏東縣": (22.67, 120.49),
    "宜蘭縣": (24.75, 121.75), "花蓮縣": (23.99, 121.60),
    "臺東縣": (22.76, 121.14), "澎湖縣": (23.57, 119.57),
    "金門縣": (24.44, 118.37), "連江縣": (26.15, 119.95),
}


def get_windy_color(temp: float) -> str:
    if temp < 10.0:   return "#2c7bb6"
    elif temp < 15.0: return "#5aa2cf"
    elif temp < 20.0: return "#abd9e9"
    elif temp < 24.0: return "#7fcdbb"
    elif temp < 28.0: return "#d9ef8b"
    elif temp < 30.0: return "#fee08b"
    elif temp < 32.0: return "#fdae61"
    elif temp < 34.0: return "#f46d43"
    else:             return "#d73027"


def get_comfort_desc(min_t: float, max_t: float) -> str:
    avg = (min_t + max_t) / 2
    if avg < 20:    return "偏涼注意保暖"
    elif avg <= 25: return "氣溫舒適宜人"
    elif avg <= 30: return "暖熱稍有出汗"
    else:           return "炎熱注意防曬"


# ── 1. Page Config ──
st.set_page_config(
    page_title="台灣即時氣象地圖",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── 2. CSS — 精確複製 taiwan-weather-map.vercel.app ──
st.markdown("""
<style>
  /* Reset Streamlit chrome */
  [data-testid="stToolbar"],
  [data-testid="stHeader"],
  [data-testid="stDecoration"],
  [data-testid="collapsedControl"],
  footer, #MainMenu { display:none !important; visibility:hidden !important; }

  .stApp, [data-testid="stAppViewContainer"],
  [data-testid="stMain"],
  [data-testid="stMainBlockContainer"],
  .block-container {
    padding: 0 !important;
    margin: 0 !important;
    max-width: 100% !important;
    background: rgb(3,7,18) !important;
  }

  [data-testid="stVerticalBlock"],
  [data-testid="element-container"],
  .stMainBlockContainer > div { padding:0 !important; gap:0 !important; }

  body, html { height:100%; margin:0; background:rgb(3,7,18);
    color:rgb(243,244,246);
    font-family:ui-sans-serif,system-ui,sans-serif;
    -webkit-font-smoothing:antialiased; }

  /* bg-panel = rgba(17,24,39,0.85) + backdrop-blur */
  .tw-panel {
    background: rgba(17,24,39,0.85);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border-radius: 0.5rem;
    box-shadow: 0 10px 15px -3px rgba(0,0,0,.4),0 4px 6px -4px rgba(0,0,0,.3);
    color: rgb(229,231,235);
  }

  /* ── Layer Panel (right-top) ── */
  .tw-layer-panel {
    position:fixed; top:1rem; right:1rem; z-index:9999;
    width:14rem; padding:0.75rem; pointer-events:auto;
  }
  .tw-panel-title {
    font-size:0.75rem; font-weight:600; text-transform:uppercase;
    letter-spacing:0.025em; color:rgb(156,163,175); margin-bottom:0.5rem;
  }
  .tw-layer-btn {
    display:flex; align-items:center; gap:0.5rem; width:100%;
    border-radius:0.375rem; padding:0.5rem 0.75rem; font-size:0.875rem;
    text-align:left; cursor:pointer; border:none; margin-bottom:0.25rem;
    transition:background 0.15s;
  }
  .tw-btn-active  { background:rgba(14,165,233,0.9); color:#fff; }
  .tw-btn-inactive{ background:rgba(255,255,255,0.05); color:rgb(229,231,235); }
  .tw-btn-inactive:hover { background:rgba(255,255,255,0.10); }
  .tw-check-row {
    display:flex; align-items:center; gap:0.5rem; border-radius:0.375rem;
    background:rgba(255,255,255,0.05); padding:0.5rem 0.75rem;
    font-size:0.875rem; color:rgb(229,231,235); margin-top:0.5rem; cursor:pointer;
  }
  .tw-basemap-grid {
    display:grid; grid-template-columns:repeat(2,minmax(0,1fr));
    gap:0.25rem; margin-top:0.75rem; padding-top:0.75rem;
    border-top:1px solid rgba(255,255,255,0.10);
  }
  .tw-bm-title {
    font-size:0.75rem; font-weight:600; text-transform:uppercase;
    letter-spacing:0.025em; color:rgb(156,163,175);
    grid-column:1/-1; margin-bottom:0.25rem;
  }
  .tw-bm-active   { background:rgba(14,165,233,0.9); color:#fff;
    border-radius:0.375rem; padding:0.375rem 0.75rem; font-size:0.875rem; border:none; cursor:pointer; }
  .tw-bm-inactive { background:rgba(255,255,255,0.05); color:rgb(229,231,235);
    border-radius:0.375rem; padding:0.375rem 0.75rem; font-size:0.875rem; border:none; cursor:pointer; }
  .tw-locate-btn {
    display:flex; align-items:center; justify-content:center; gap:0.5rem;
    width:100%; border-radius:0.375rem; background:rgba(5,150,105,0.9);
    padding:0.5rem 0.75rem; font-size:0.875rem; color:#fff; border:none;
    cursor:pointer; margin-top:0.75rem; transition:background 0.15s;
  }
  .tw-locate-btn:hover { background:rgb(5,150,105); }

  /* ── Colorbar (bottom-right) ── */
  .tw-colorbar {
    position:fixed; bottom:1rem; right:1rem; z-index:9999;
    width:15rem; padding:0.625rem; pointer-events:auto;
  }
  .tw-colorbar-inner { display:flex; align-items:center; gap:0.5rem; }
  .tw-colorbar-unit  { flex-shrink:0; font-size:0.75rem; font-weight:600; color:rgb(243,244,246); }
  .tw-colorbar-flex  { flex:1; }
  .tw-colorbar-bar   {
    height:0.625rem; width:100%; border-radius:9999px;
    background:linear-gradient(to right,#2c7bb6,#5aa2cf,#abd9e9,#7fcdbb,#d9ef8b,#fee08b,#fdae61,#f46d43,#d73027);
  }
  .tw-colorbar-labels {
    display:flex; justify-content:space-between;
    font-size:9px; font-variant-numeric:tabular-nums;
    color:rgb(156,163,175); margin-top:0.25rem;
  }

  /* ── Date Panel (left-top) ── */
  .tw-date-panel {
    position:fixed; top:1rem; left:1rem; z-index:9999;
    padding:0.625rem 0.875rem; min-width:11rem; pointer-events:auto;
  }
  .tw-date-label {
    font-size:0.7rem; font-weight:600; text-transform:uppercase;
    letter-spacing:0.025em; color:rgb(156,163,175); margin-bottom:0.35rem;
  }
  .tw-date-select {
    background:transparent; border:none; color:rgb(229,231,235);
    font-size:0.875rem; cursor:pointer; width:100%; outline:none;
  }
  .tw-date-select option { background:rgb(17,24,39); color:rgb(229,231,235); }

  /* ── City Info (top-center) ── */
  .tw-topcenter {
    position:fixed; top:1rem; left:50%; transform:translateX(-50%);
    z-index:9999; pointer-events:none; display:flex; justify-content:center;
  }
  .tw-citycard {
    pointer-events:auto; padding:0.75rem 1.25rem; text-align:center; min-width:13rem;
  }
  .tw-city-name { font-size:0.9rem; font-weight:700; color:rgb(243,244,246); margin-bottom:0.15rem; }
  .tw-city-temp { font-size:2rem; font-weight:700; line-height:1; margin:0.25rem 0; }
  .tw-city-range { font-size:0.72rem; color:rgb(156,163,175); }

  /* Full-screen map iframe */
  [data-testid="stCustomComponentV1"] > div, [data-testid="stCustomComponentV1"] iframe {
    height: 100vh !important; min-height:100vh !important; border:none !important;
  }
</style>
""", unsafe_allow_html=True)


# ── 3. Data ──
@st.cache_data(ttl=600)
def load_data_from_db(db_path: str = DB_PATH) -> pd.DataFrame:
    if not os.path.exists(db_path):
        if run_etl_pipeline:
            run_etl_pipeline(db_path)
        else:
            return pd.DataFrame()
    with sqlite3.connect(db_path) as conn:
        try:
            df = pd.read_sql_query(
                "SELECT regionName, dataDate, minT, maxT FROM TemperatureForecasts ORDER BY regionName, dataDate ASC;",
                conn
            )
        except Exception:
            return pd.DataFrame()
    if df.empty and run_etl_pipeline:
        run_etl_pipeline(db_path)
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query(
                "SELECT regionName, dataDate, minT, maxT FROM TemperatureForecasts ORDER BY regionName, dataDate ASC;",
                conn
            )
    return df


df_all = load_data_from_db(DB_PATH)

if df_all.empty:
    st.markdown("""
    <div style="position:fixed;inset:0;background:rgba(3,7,18,0.8);z-index:99999;
      display:flex;align-items:center;justify-content:center;">
      <div class="tw-panel" style="padding:1.5rem 2rem;color:rgb(229,231,235);">
        ⚠️ 無法載入資料，請確認 .env 中的 CWA_API_KEY
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

available_dates = sorted(df_all["dataDate"].unique().tolist())

# URL 日期參數
query_params = st.query_params
if "date" in query_params and query_params["date"] in available_dates:
    selected_date = query_params["date"]
else:
    selected_date = available_dates[0]


# ── 4. Floating Panels HTML ──

# Layer Panel
layer_panel = """
<div class="tw-panel tw-layer-panel">
  <div class="tw-panel-title">圖層</div>
  <button class="tw-layer-btn tw-btn-active">🌡️ 氣溫</button>
  <button class="tw-layer-btn tw-btn-inactive">🌧️ 雨量</button>
  <button class="tw-layer-btn tw-btn-inactive">🛰️ 雷達</button>
  <button class="tw-layer-btn tw-btn-inactive">🌀 颱風</button>
  <button class="tw-layer-btn tw-btn-inactive">💨 風速風向</button>
  <button class="tw-layer-btn tw-btn-inactive">💧 濕度</button>
  <button class="tw-layer-btn tw-btn-inactive">⛅ 天氣</button>
  <button class="tw-layer-btn tw-btn-inactive">📍 測站點位</button>
  <label class="tw-check-row">
    <input type="checkbox" style="accent-color:#0ea5e9;" checked> 縣市界線
  </label>
  <label class="tw-check-row">
    <input type="checkbox" style="accent-color:#0ea5e9;" checked> 氣溫數字標籤
  </label>
  <div class="tw-basemap-grid">
    <div class="tw-bm-title">底圖</div>
    <button class="tw-bm-active">深色</button>
    <button class="tw-bm-inactive">街道圖</button>
  </div>
  <button class="tw-locate-btn">📌 定位我的位置</button>
</div>
"""

# Colorbar
colorbar_panel = """
<div class="tw-panel tw-colorbar">
  <div class="tw-colorbar-inner">
    <span class="tw-colorbar-unit">°C</span>
    <div class="tw-colorbar-flex">
      <div class="tw-colorbar-bar"></div>
      <div class="tw-colorbar-labels">
        <span>5</span><span>10</span><span>15</span>
        <span>20</span><span>24</span><span>28</span>
        <span>32</span><span>36</span>
      </div>
    </div>
  </div>
</div>
"""

# Date Panel
date_opts = "".join(
    f'<option value="{d}"{"selected" if d == selected_date else ""}>{d}</option>'
    for d in available_dates
)
date_panel = f"""
<div class="tw-panel tw-date-panel">
  <div class="tw-date-label">📅 預報日期</div>
  <select class="tw-date-select" onchange="
    var u=new URL(window.location.href);
    u.searchParams.set('date',this.value);
    window.location.href=u.toString();
  ">{date_opts}</select>
</div>
"""

# ── 5. Build Folium Map ──
df_date = df_all[df_all["dataDate"] == selected_date].copy()
df_date["avgT"] = ((df_date["minT"] + df_date["maxT"]) / 2).round(1)

m = folium.Map(
    location=[23.75, 120.95],
    zoom_start=7,
    tiles="https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png",
    attr="&copy; Stadia Maps &copy; OpenMapTiles &copy; OpenStreetMap",
    control_scale=False,
    zoom_control=True,
    prefer_canvas=True,
)
m.options["attributionControl"] = False

for _, row in df_date.iterrows():
    reg_name = row["regionName"]
    min_temp, max_temp, avg_temp = row["minT"], row["maxT"], row["avgT"]
    color = get_windy_color(avg_temp)
    desc = get_comfort_desc(min_temp, max_temp)
    coord = COORDINATES.get(reg_name)
    if not coord:
        continue

    is_core = reg_name in REGION_MAPPING
    radius = 20 if is_core else 14

    popup_html = f"""
    <div style="font-family:ui-sans-serif,system-ui,sans-serif;min-width:165px;
      background:rgba(17,24,39,0.97);color:#f3f4f6;border-radius:8px;padding:2px;">
      <div style="font-weight:700;font-size:14px;color:#38bdf8;
        border-bottom:1px solid rgba(255,255,255,0.12);padding-bottom:6px;margin-bottom:8px;">
        📍 {reg_name}
      </div>
      <div style="font-size:12px;line-height:1.8;">
        <div><span style="color:#9ca3af;">日期：</span>{selected_date}</div>
        <div><span style="color:#9ca3af;">最低溫：</span><b style="color:#38bdf8;">{min_temp}°C</b></div>
        <div><span style="color:#9ca3af;">最高溫：</span><b style="color:#f87171;">{max_temp}°C</b></div>
        <div><span style="color:#9ca3af;">平均溫：</span>
          <b style="color:{color};font-size:16px;">{avg_temp}°C</b></div>
        <div style="margin-top:6px;padding:3px 8px;border-radius:6px;
          background:{color}33;border:1px solid {color}99;
          color:#f1f5f9;font-size:11px;text-align:center;font-weight:600;">{desc}</div>
      </div>
    </div>
    """

    folium.CircleMarker(
        location=[coord[0], coord[1]],
        radius=radius,
        color="rgba(255,255,255,0.6)",
        weight=1.5,
        fill=True,
        fill_color=color,
        fill_opacity=0.88,
        tooltip=folium.Tooltip(
            f"<span style='font-weight:700;color:{color};'>{reg_name}</span> {avg_temp}°C",
            sticky=False
        ),
        popup=folium.Popup(popup_html, max_width=220),
    ).add_to(m)

    # 氣溫數字標籤 (temp-label style)
    folium.Marker(
        location=[coord[0], coord[1]],
        icon=folium.DivIcon(
            html=f"""<div style="
              font-family:ui-sans-serif,system-ui,sans-serif;
              font-size:{'12px' if is_core else '10px'};font-weight:700;
              color:#fff;pointer-events:none;white-space:nowrap;
              text-shadow:0 0 3px rgba(0,0,0,1),0 1px 2px rgba(0,0,0,0.9);
              transform:translate(-50%,-50%);
            ">{avg_temp}°</div>""",
            icon_size=(44, 22),
            icon_anchor=(22, 11),
        ),
    ).add_to(m)


# ── 6. Render ──
st.markdown(layer_panel, unsafe_allow_html=True)
st.markdown(colorbar_panel, unsafe_allow_html=True)
st.markdown(date_panel, unsafe_allow_html=True)

st_folium(
    m,
    width="stretch",
    height=900,
    returned_objects=[],
)
