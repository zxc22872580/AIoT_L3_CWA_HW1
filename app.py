"""
app.py
Taiwan Weather Forecast — 台灣即時氣象地圖儀表板
參考 taiwan-weather-map.vercel.app 現代深色玻璃擬態 (Dark Glassmorphism & Windy Style)
"""

import os
import sys
import sqlite3
from typing import Dict, List, Tuple
import pandas as pd
import altair as alt
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

# 導入 ETL 模組以便隨時重新整理資料庫
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

# ==========================================
# 地理空間座標對照表 (經緯度 Coordinates)
# ==========================================
COORDINATES: Dict[str, Tuple[float, float]] = {
    # 7 大分區中心座標
    "北部地區": (24.98, 121.35),
    "中部地區": (24.08, 120.70),
    "南部地區": (22.95, 120.35),
    "東北部地區": (24.70, 121.70),
    "東部地區": (23.85, 121.50),
    "東南部地區": (22.75, 121.10),
    "離島地區": (23.57, 119.57),
    # 22 縣市座標
    "基隆市": (25.13, 121.74),
    "臺北市": (25.04, 121.56),
    "新北市": (25.01, 121.46),
    "桃園市": (24.99, 121.30),
    "新竹市": (24.81, 120.97),
    "新竹縣": (24.84, 121.01),
    "苗栗縣": (24.56, 120.82),
    "臺中市": (24.15, 120.67),
    "彰化縣": (24.08, 120.54),
    "南投縣": (23.91, 120.69),
    "雲林縣": (23.71, 120.43),
    "嘉義市": (23.48, 120.45),
    "嘉義縣": (23.45, 120.25),
    "臺南市": (22.99, 120.21),
    "高雄市": (22.63, 120.30),
    "屏東縣": (22.67, 120.49),
    "宜蘭縣": (24.75, 121.75),
    "花蓮縣": (23.99, 121.60),
    "臺東縣": (22.76, 121.14),
    "澎湖縣": (23.57, 119.57),
    "金門縣": (24.44, 118.37),
    "連江縣": (26.15, 119.95),
}


def get_windy_color(temp: float) -> str:
    """類 Windy 漸層光譜色票函數 (對應 taiwan-weather-map 漸層色階)。"""
    if temp < 10.0:
        return "#2c7bb6"
    elif temp < 15.0:
        return "#5aa2cf"
    elif temp < 20.0:
        return "#abd9e9"
    elif temp < 24.0:
        return "#7fcdbb"
    elif temp < 28.0:
        return "#d9ef8b"
    elif temp < 30.0:
        return "#fee08b"
    elif temp < 32.0:
        return "#fdae61"
    elif temp < 34.0:
        return "#f46d43"
    else:
        return "#d73027"


def get_comfort_desc(min_t: float, max_t: float) -> str:
    """依據平均溫計算天氣舒適度敘述。"""
    avg = (min_t + max_t) / 2
    if avg < 20:
        return "偏涼注意保暖"
    elif avg <= 25:
        return "氣溫舒適宜人"
    elif avg <= 30:
        return "暖熱稍有出汗"
    else:
        return "炎熱注意防曬"


# ==========================================
# 1. 頁面基本設定 (Page Config)
# ==========================================
st.set_page_config(
    page_title="台灣即時氣象地圖 — Taiwan Weather Map",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入深色玻璃擬態 (Dark Glassmorphism) 核心 CSS
st.markdown("""
<style>
    /* 全域深色背景微調 */
    .stApp {
        background-color: #030712 !important;
        color: #F3F4F6 !important;
    }
    
    /* 頂部標題 */
    .windy-title {
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        background: linear-gradient(135deg, #38BDF8 0%, #818CF8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 4px;
    }
    .windy-subtitle {
        color: #94A3B8;
        font-size: 0.95rem;
        margin-bottom: 14px;
    }
    .windy-quote {
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-left: 4px solid #38BDF8;
        padding: 10px 14px;
        border-radius: 8px;
        font-size: 0.88rem;
        color: #E2E8F0;
        margin-bottom: 18px;
        backdrop-filter: blur(12px);
    }
    
    /* 指標卡片美化 */
    [data-testid="stMetric"] {
        background: rgba(15, 23, 42, 0.75) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
        backdrop-filter: blur(12px) !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4) !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.9rem !important;
        font-weight: 800 !important;
        color: #38BDF8 !important;
    }
    [data-testid="stMetricLabel"] {
        color: #94A3B8 !important;
        font-size: 0.85rem !important;
    }

    /* 漸層色階條樣式 (Windy Spectral Colorbar) */
    .windy-legend-container {
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 10px;
        padding: 12px 18px;
        margin-bottom: 16px;
        backdrop-filter: blur(12px);
    }
    .windy-legend-bar {
        height: 10px;
        width: 100%;
        border-radius: 9999px;
        background: linear-gradient(to right, #2c7bb6, #5aa2cf, #abd9e9, #7fcdbb, #d9ef8b, #fee08b, #fdae61, #f46d43, #d73027);
        margin: 6px 0;
        box-shadow: 0 0 10px rgba(0,0,0,0.5);
    }
    .windy-legend-labels {
        display: flex;
        justify-content: space-between;
        font-size: 11px;
        color: #94A3B8;
        font-family: monospace;
    }

    /* 頁籤微調 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 8px 8px 0 0;
        color: #94A3B8;
        padding: 8px 18px;
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(14, 165, 233, 0.15) !important;
        color: #38BDF8 !important;
        border-bottom: 2px solid #38BDF8 !important;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 2. 資料讀取函式 (Data Access with Cache)
# ==========================================
@st.cache_data(ttl=600)
def load_data_from_db(db_path: str = DB_PATH) -> pd.DataFrame:
    """從 SQLite 資料庫讀取全部氣溫預報資料。若無資料則自動觸發 ETL。"""
    if not os.path.exists(db_path):
        if run_etl_pipeline:
            with st.spinner("正在初始化氣象資料庫 (執行 ETL Pipeline)..."):
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
        with st.spinner("資料庫無記錄，正在自 CWA API 擷取最新氣象數據..."):
            run_etl_pipeline(db_path)
            with sqlite3.connect(db_path) as conn:
                df = pd.read_sql_query(
                    "SELECT regionName, dataDate, minT, maxT FROM TemperatureForecasts ORDER BY regionName, dataDate ASC;",
                    conn
                )
    return df


df_all = load_data_from_db(DB_PATH)


# ==========================================
# 3. 側邊欄 (Sidebar) 控制中心
# ==========================================
with st.sidebar:
    st.markdown("### 🛰️ 氣象控制台")
    st.caption("類 Windy 風格即時地圖系統")
    st.markdown("---")

    # 資料庫指標展示
    if not df_all.empty:
        total_records = len(df_all)
        total_regions = df_all["regionName"].nunique()
        dates_list = sorted(df_all["dataDate"].unique())
        date_range_str = f"{dates_list[0]} ~ {dates_list[-1]}"

        st.metric(label="儲存預報筆數", value=f"{total_records} 筆")
        st.metric(label="涵蓋區域數", value=f"{total_regions} 個")
        st.caption(f"📅 **預報期程**：{date_range_str}")
    else:
        st.warning("目前資料庫中無預報數據。")

    st.markdown("---")

    # 模擬圖層切換 (類 taiwan-weather-map 側邊面板)
    st.markdown("##### 📌 觀測圖層")
    st.button("🌡️ 氣溫預報 (目前使用中)", use_container_width=True, disabled=True)
    if st.button("🌧️ 即時雨量 (準備接入)", use_container_width=True):
        st.toast("雨量雷達資料集準備接入中！")
    if st.button("💨 風速風向 (準備接入)", use_container_width=True):
        st.toast("風場粒子模擬資料集準備接入中！")

    st.markdown("---")

    # 手動更新資料按鈕
    if st.button("🔄 立即重新擷取 CWA 資料", use_container_width=True):
        if run_etl_pipeline:
            with st.spinner("正在向中央氣象署 API 更新資料..."):
                try:
                    run_etl_pipeline(DB_PATH)
                    st.cache_data.clear()
                    st.success("資料庫已成功同步至最新預報！")
                    st.rerun()
                except Exception as e:
                    st.error(f"更新失敗: {e}")
        else:
            st.error("找不到 ETL 模組。")


# ==========================================
# 4. 主畫面橫幅 (Header)
# ==========================================
st.markdown('<div class="windy-title">🌤️ 台灣即時氣象地圖</div>', unsafe_allow_html=True)
st.markdown('<div class="windy-subtitle">中央氣象署開放資料即時視覺化地圖（類 Windy 深色玻璃擬態風格）</div>', unsafe_allow_html=True)

st.markdown("""
<div class="windy-quote">
  💡 <b>煥哥心法引言</b>：<i>「技術可以解決問題，但更重要的是用技術創造更好的未來！」</i>
</div>
""", unsafe_allow_html=True)

if df_all.empty:
    st.error("未能載入預報資料，請檢查 .env 中的 CWA_API_KEY 設定或點擊左側「🔄 立即重新擷取 CWA 資料」。")
    st.stop()


# ==========================================
# 5. 分頁佈局：互動地圖 (預設焦點) vs 區域走勢 vs 系統規格
# ==========================================
tab_map, tab_trend, tab_arch = st.tabs([
    "🗺️ 即時地圖視覺化 (Interactive Map)",
    "📈 區域走勢與數據明細 (Trends & Table)",
    "⚙️ 系統架構與規格 (Architecture)"
])


# ------------------------------------------
# TAB 1: 類 Windy 互動地圖 (Phase 6 強化版)
# ------------------------------------------
with tab_map:
    # Windy 光譜色階說明條
    st.markdown("""
    <div class="windy-legend-container">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="font-size: 0.8rem; font-weight: 700; color: #E2E8F0;">氣溫色階圖例 (°C)</span>
        <span style="font-size: 0.72rem; color: #64748B;">Windy Colormap</span>
      </div>
      <div class="windy-legend-bar"></div>
      <div class="windy-legend-labels">
        <span>5°</span>
        <span>10°</span>
        <span>15°</span>
        <span>20°</span>
        <span>24°</span>
        <span>28°</span>
        <span>32°</span>
        <span>36°+</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    available_dates = sorted(df_all["dataDate"].unique().tolist())

    col_map1, col_map2 = st.columns([1, 1])
    with col_map1:
        selected_date = st.selectbox(
            "📅 選擇預報日期 (Select Date)：",
            options=available_dates,
            index=0,
            help="切換日期以查看該日全台各地溫度分佈"
        )
    with col_map2:
        layer_mode = st.radio(
            "選擇標記圖層：",
            options=["7 大分區中心標記", "22 縣市詳細標記", "全部顯示"],
            index=0,
            horizontal=True
        )

    # 依選定日期篩選數據
    df_date = df_all[df_all["dataDate"] == selected_date].copy()
    df_date["avgT"] = ((df_date["minT"] + df_date["maxT"]) / 2).round(1)

    if layer_mode == "7 大分區中心標記":
        df_map_points = df_date[df_date["regionName"].isin(REGION_MAPPING.keys())]
    elif layer_mode == "22 縣市詳細標記":
        df_map_points = df_date[~df_date["regionName"].isin(REGION_MAPPING.keys())]
    else:
        df_map_points = df_date

    # 建立 Folium 地圖實例 (採用 CartoDB dark_matter 深色地圖)
    m = folium.Map(
        location=[23.75, 120.95],
        zoom_start=7,
        tiles="CartoDB dark_matter",
        control_scale=True
    )

    # 在地圖上逐一添加發光圓點標記
    for _, row in df_map_points.iterrows():
        reg_name = row["regionName"]
        min_temp = row["minT"]
        max_temp = row["maxT"]
        avg_temp = row["avgT"]
        color = get_windy_color(avg_temp)
        desc = get_comfort_desc(min_temp, max_temp)

        coord = COORDINATES.get(reg_name)
        if not coord:
            continue

        popup_html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; min-width: 170px; color: #F8FAFC;">
          <h4 style="margin: 0 0 6px 0; color: #38BDF8; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 4px;">📍 {reg_name}</h4>
          <div style="font-size: 13px; line-height: 1.6;">
            <b>日期：</b>{selected_date}<br>
            <b>最低溫：</b><span style="color: #38BDF8; font-weight: 700;">{min_temp} °C</span><br>
            <b>最高溫：</b><span style="color: #F87171; font-weight: 700;">{max_temp} °C</span><br>
            <b>平均溫：</b><span style="color: #FBBF24; font-weight: 700;">{avg_temp} °C</span><br>
            <div style="margin-top: 6px; padding: 3px 6px; border-radius: 4px; background: {color}; color: #FFFFFF; font-size: 11px; text-align: center; font-weight: 600;">
              {desc}
            </div>
          </div>
        </div>
        """

        folium.CircleMarker(
            location=[coord[0], coord[1]],
            radius=16 if reg_name in REGION_MAPPING else 12,
            color="#FFFFFF",
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.88,
            tooltip=f"<b>{reg_name}</b>: {avg_temp} °C ({desc})",
            popup=folium.Popup(popup_html, max_width=250)
        ).add_to(m)

    st_folium(m, width="100%", height=560, returned_objects=[])


# ------------------------------------------
# TAB 2: 區域氣溫走勢與明細
# ------------------------------------------
with tab_trend:
    all_regions_db = df_all["regionName"].unique().tolist()
    core_regions = ["北部地區", "中部地區", "南部地區", "東北部地區", "東部地區", "東南部地區", "離島地區"]

    sorted_options = [r for r in core_regions if r in all_regions_db]
    county_options = [r for r in all_regions_db if r not in core_regions]
    sorted_options.extend(sorted(county_options))

    col_sel1, col_sel2 = st.columns([2, 1])
    with col_sel1:
        default_index = sorted_options.index("中部地區") if "中部地區" in sorted_options else 0
        selected_region = st.selectbox(
            "📍 請選擇預報區域或縣市 (Select Region)：",
            options=sorted_options,
            index=default_index
        )
    with col_sel2:
        st.write("")
        st.write("")
        is_core_region = selected_region in REGION_MAPPING
        sub_counties = ", ".join(REGION_MAPPING[selected_region]) if is_core_region else selected_region
        st.info(f"涵蓋範圍: **{sub_counties}**")

    df_region = df_all[df_all["regionName"] == selected_region].sort_values("dataDate").copy()

    if not df_region.empty:
        today_row = df_region.iloc[0]
        today_date = today_row["dataDate"]
        today_min = today_row["minT"]
        today_max = today_row["maxT"]
        today_diff = round(today_max - today_min, 1)
        week_avg = round((df_region["minT"].mean() + df_region["maxT"].mean()) / 2, 1)

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric(label=f"今日最低溫 ({today_date})", value=f"{today_min} °C")
        with m2:
            st.metric(label=f"今日最高溫 ({today_date})", value=f"{today_max} °C")
        with m3:
            st.metric(label="今日預估溫差", value=f"{today_diff} °C")
        with m4:
            st.metric(label="未來一週平均溫", value=f"{week_avg} °C")

        st.markdown("---")

        # Altair 深色風格折線圖
        st.markdown(f"#### 📈 【{selected_region}】未來一週氣溫走勢圖")

        df_chart_long = pd.melt(
            df_region,
            id_vars=["dataDate"],
            value_vars=["maxT", "minT"],
            var_name="tempType",
            value_name="temperature"
        )
        df_chart_long["tempType"] = df_chart_long["tempType"].map({
            "maxT": "最高氣溫 (MaxT)",
            "minT": "最低氣溫 (MinT)"
        })

        color_scale = alt.Scale(
            domain=["最高氣溫 (MaxT)", "最低氣溫 (MinT)"],
            range=["#F87171", "#38BDF8"]
        )

        line_chart = alt.Chart(df_chart_long).mark_line(point=True, strokeWidth=2.8).encode(
            x=alt.X("dataDate:N", title="預報日期 (Date)", axis=alt.Axis(labelAngle=0, labelColor="#94A3B8", titleColor="#94A3B8")),
            y=alt.Y(
                "temperature:Q",
                title="氣溫 (°C)",
                scale=alt.Scale(
                    domain=[
                        float(df_region["minT"].min() - 3),
                        float(df_region["maxT"].max() + 3)
                    ]
                ),
                axis=alt.Axis(labelColor="#94A3B8", titleColor="#94A3B8", gridColor="rgba(255,255,255,0.06)")
            ),
            color=alt.Color("tempType:N", scale=color_scale, legend=alt.Legend(title="氣溫要素", titleColor="#E2E8F0", labelColor="#E2E8F0")),
            tooltip=[
                alt.Tooltip("dataDate:N", title="日期"),
                alt.Tooltip("tempType:N", title="要素"),
                alt.Tooltip("temperature:Q", title="氣溫 (°C)", format=".1f")
            ]
        ).properties(
            height=340
        ).interactive()

        st.altair_chart(line_chart, use_container_width=True)

        st.markdown(f"#### 📋 【{selected_region}】預報明細數據")
        df_display = df_region.copy()
        df_display["tempDiff"] = (df_display["maxT"] - df_display["minT"]).round(1)
        df_display["comfortLevel"] = df_display.apply(
            lambda r: get_comfort_desc(r["minT"], r["maxT"]), axis=1
        )

        df_display_clean = df_display.rename(columns={
            "dataDate": "預報日期",
            "minT": "最低氣溫 (°C)",
            "maxT": "最高氣溫 (°C)",
            "tempDiff": "日溫差 (°C)",
            "comfortLevel": "天氣體感"
        })

        st.dataframe(
            df_display_clean[["預報日期", "最低氣溫 (°C)", "最高氣溫 (°C)", "日溫差 (°C)", "天氣體感"]],
            use_container_width=True,
            hide_index=True
        )


# ------------------------------------------
# TAB 3: 系統架構
# ------------------------------------------
with tab_arch:
    st.markdown("#### ⚙️ 系統技術架構規格")
    st.markdown("""
    - **UI 風格**：參考 `taiwan-weather-map.vercel.app` 類 Windy 深色玻璃擬態風格。
    - **底圖圖磚**：CartoDB Dark Matter 深色圖磚套疊。
    - **光譜調色**：Windy Spectral Color Gradient (`#2c7bb6` ➔ `#d73027`)。
    - **雙軌架構**：
      - 本地 / Streamlit Cloud：`app.py`
      - Vercel Serverless：`vercel.json` + `api/index.py`
    """)

st.markdown("---")
st.caption("Taiwan Weather Map © 2026 | Inspired by taiwan-weather-map.vercel.app | Built for AIoT HW1")
