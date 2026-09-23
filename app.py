"""
app.py
Taiwan Weather Forecast — 台灣天氣預報互動式 Web 儀表板
階段五：Streamlit 互動儀表板 (Web Dashboard)
階段六：Folium 地理空間視覺化 (Map Integration)
階段七：程式品質優化與防呆 (Code Quality & Robustness)
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


def get_temperature_color(avg_temp: float) -> str:
    """依據平均氣溫回傳對應的色票代碼 (單元 17 色階規格)。"""
    if avg_temp < 20.0:
        return "#1E88E5"  # 藍色 (偏涼、寒冷)
    elif avg_temp <= 25.0:
        return "#43A047"  # 綠色 (舒適、宜人)
    elif avg_temp <= 30.0:
        return "#FDD835"  # 黃色 (暖熱、晴朗)
    else:
        return "#E53935"  # 紅色 (炎熱、注意防曬)


def get_comfort_desc(min_t: float, max_t: float) -> str:
    """依據平均溫計算天氣舒適度敘述。"""
    avg = (min_t + max_t) / 2
    if avg < 20:
        return "🔵 偏涼注意保暖"
    elif avg <= 25:
        return "🟢 氣溫舒適宜人"
    elif avg <= 30:
        return "🟡 稍有暖熱"
    else:
        return "🔴 炎熱注意防曬"


# ==========================================
# 1. 頁面基本設定 (Page Config)
# ==========================================
st.set_page_config(
    page_title="Taiwan Weather Forecast — 台灣氣象預報",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自訂 CSS 提升介面質感
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
        background: linear-gradient(120deg, #1E88E5, #00C9FF);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .sub-title {
        color: #718096;
        font-size: 1.05rem;
        margin-bottom: 1.2rem;
    }
    .mentor-quote {
        background: rgba(30, 136, 229, 0.08);
        border-left: 4px solid #1E88E5;
        padding: 0.75rem 1rem;
        border-radius: 4px;
        margin-bottom: 1.5rem;
        font-size: 0.95rem;
        color: #2D3748;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700;
    }
    .legend-box {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        margin-bottom: 12px;
        padding: 8px 12px;
        background: #F7FAFC;
        border-radius: 6px;
        border: 1px solid #E2E8F0;
    }
    .legend-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.88rem;
    }
    .legend-badge {
        width: 14px;
        height: 14px;
        border-radius: 50%;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 2. 資料庫安全讀取函式 (Data Access with Cache)
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


# 載入預報資料
df_all = load_data_from_db(DB_PATH)


# ==========================================
# 3. 側邊欄 (Sidebar) 控制中心
# ==========================================
with st.sidebar:
    st.image("https://img.icons8.com/clouds/200/sun.png", width=110)
    st.title("氣象資料中心")
    st.caption("AIoT 創新微課程實戰專案 (HW1)")
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

    st.markdown("---")
    st.markdown(
        """
        **核心實作技術鏈**：
        - 🌐 中央氣象署 CWA API (Requests)
        - 🐍 Python + Pandas (JSON 清洗)
        - 🗄️ SQLite3 (關聯資料庫持久化)
        - 📊 Streamlit + Altair (互動圖表)
        - 🗺️ Folium (台灣地理空間視覺化)
        """
    )


# ==========================================
# 4. 主畫面橫幅與介紹 (Header)
# ==========================================
st.markdown('<div class="main-title">🌤️ Taiwan Weather Forecast — 台灣天氣預報儀表板</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">用程式探索天氣 · 用資料看見台灣 · 用 AI 實現更多可能</div>', unsafe_allow_html=True)

st.markdown("""
<div class="mentor-quote">
  💡 <b>煥哥心法引言</b>：<i>「技術可以解決問題，但更重要的是用技術創造更好的未來！」</i>
  <br><small>專案循序遵循 24 單元實戰地圖：自 CWA Open Data API 串接、SQLite 冪等入庫至 Streamlit 互動視覺化與 Folium 地圖。</small>
</div>
""", unsafe_allow_html=True)

if df_all.empty:
    st.error("未能載入預報資料，請檢查 .env 中的 CWA_API_KEY 設定或點擊左側「🔄 立即重新擷取 CWA 資料」。")
    st.stop()


# ==========================================
# 5. 分頁佈局：圖表趨勢 vs 地理地圖 (Tabs)
# ==========================================
tab_trend, tab_map, tab_arch = st.tabs([
    "📈 區域氣溫趨勢分析 (Regional Trends)",
    "🗺️ 台灣地圖視覺化 (Interactive Map)",
    "⚙️ 系統架構與規格 (Architecture)"
])


# ------------------------------------------
# TAB 1: 區域氣溫趨勢分析 (Phase 5)
# ------------------------------------------
with tab_trend:
    all_regions_db = df_all["regionName"].unique().tolist()
    core_regions = ["北部地區", "中部地區", "南部地區", "東北部地區", "東部地區", "東南部地區", "離島地區"]

    # 排序選單：先放核心區域，再放各縣市
    sorted_options = [r for r in core_regions if r in all_regions_db]
    county_options = [r for r in all_regions_db if r not in core_regions]
    sorted_options.extend(sorted(county_options))

    col_sel1, col_sel2 = st.columns([2, 1])
    with col_sel1:
        default_index = sorted_options.index("中部地區") if "中部地區" in sorted_options else 0
        selected_region = st.selectbox(
            "📍 請選擇預報區域或縣市 (Select Region)：",
            options=sorted_options,
            index=default_index,
            help="支援台灣 7 大分區與 22 縣市切換"
        )

    with col_sel2:
        st.write("")
        st.write("")
        is_core_region = selected_region in REGION_MAPPING
        sub_counties = ", ".join(REGION_MAPPING[selected_region]) if is_core_region else selected_region
        st.info(f"涵蓋範圍: **{sub_counties}**")

    # 篩選選定區域的預報數據
    df_region = df_all[df_all["regionName"] == selected_region].sort_values("dataDate").copy()

    if df_region.empty:
        st.warning(f"目前查無 {selected_region} 的預報資料。")
    else:
        # 今日指標卡片 (KPI)
        today_row = df_region.iloc[0]
        today_date = today_row["dataDate"]
        today_min = today_row["minT"]
        today_max = today_row["maxT"]
        today_diff = round(today_max - today_min, 1)
        week_avg = round((df_region["minT"].mean() + df_region["maxT"].mean()) / 2, 1)

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric(label=f"今日最低溫 ({today_date})", value=f"{today_min} °C", delta="清晨/夜間低溫", delta_color="inverse")
        with m2:
            st.metric(label=f"今日最高溫 ({today_date})", value=f"{today_max} °C", delta="日間高溫")
        with m3:
            st.metric(label="今日預估溫差", value=f"{today_diff} °C", delta="溫差提醒")
        with m4:
            st.metric(label="未來一週平均溫", value=f"{week_avg} °C", delta="一週趨勢")

        st.markdown("---")

        # 一週最高與最低氣溫折線圖
        st.subheader(f"📈 【{selected_region}】未來一週氣溫走向趨勢圖 (Line Chart)")

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
            range=["#FF4B4B", "#1E88E5"]
        )

        line_chart = alt.Chart(df_chart_long).mark_line(point=True, strokeWidth=3).encode(
            x=alt.X("dataDate:N", title="預報日期 (Date)", axis=alt.Axis(labelAngle=0)),
            y=alt.Y(
                "temperature:Q",
                title="氣溫 (°C)",
                scale=alt.Scale(
                    domain=[
                        float(df_region["minT"].min() - 3),
                        float(df_region["maxT"].max() + 3)
                    ]
                )
            ),
            color=alt.Color("tempType:N", scale=color_scale, legend=alt.Legend(title="氣溫要素")),
            tooltip=[
                alt.Tooltip("dataDate:N", title="日期"),
                alt.Tooltip("tempType:N", title="要素"),
                alt.Tooltip("temperature:Q", title="氣溫 (°C)", format=".1f")
            ]
        ).properties(
            height=340
        ).interactive()

        st.altair_chart(line_chart, use_container_width=True)

        # 詳細預報明細表格
        st.subheader(f"📋 【{selected_region}】未來一週氣溫明細表 (Data Table)")
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
            "comfortLevel": "天氣體感建議"
        })

        st.dataframe(
            df_display_clean[["預報日期", "最低氣溫 (°C)", "最高氣溫 (°C)", "日溫差 (°C)", "天氣體感建議"]],
            use_container_width=True,
            hide_index=True
        )


# ------------------------------------------
# TAB 2: 台灣地圖視覺化 (Phase 6 - 單元 17 & 18)
# ------------------------------------------
with tab_map:
    st.subheader("🗺️ 台灣各區互動式氣溫地圖 (Folium Map Visualization)")
    st.caption("點選地圖圓點標記可顯示該地區預報細節；色彩隨平均氣溫動態變化。")

    # 色階圖例說明
    st.markdown("""
    <div class="legend-box">
      <span style="font-weight: 600; margin-right: 8px;">溫度色階圖例：</span>
      <div class="legend-item"><span class="legend-badge" style="background: #1E88E5;"></span>&lt; 20°C 偏涼/寒冷</div>
      <div class="legend-item"><span class="legend-badge" style="background: #43A047;"></span>20 ~ 25°C 舒適宜人</div>
      <div class="legend-item"><span class="legend-badge" style="background: #FDD835;"></span>25 ~ 30°C 暖熱晴朗</div>
      <div class="legend-item"><span class="legend-badge" style="background: #E53935;"></span>&gt; 30°C 炎熱注意防曬</div>
    </div>
    """, unsafe_allow_html=True)

    available_dates = sorted(df_all["dataDate"].unique().tolist())

    col_map_ctrl1, col_map_ctrl2 = st.columns([2, 2])
    with col_map_ctrl1:
        selected_date = st.selectbox(
            "📅 選擇預報日期 (Select Date)：",
            options=available_dates,
            index=0,
            help="切換日期以查看該日全台各地溫度分佈"
        )
    with col_map_ctrl2:
        layer_mode = st.radio(
            "選擇顯示圖層層級：",
            options=["7 大分區中心標記", "22 縣市詳細標記", "全部顯示"],
            index=0,
            horizontal=True
        )

    # 依選定日期篩選數據
    df_date = df_all[df_all["dataDate"] == selected_date].copy()
    df_date["avgT"] = ((df_date["minT"] + df_date["maxT"]) / 2).round(1)

    # 決定地圖要呈現的地點集合
    if layer_mode == "7 大分區中心標記":
        df_map_points = df_date[df_date["regionName"].isin(REGION_MAPPING.keys())]
    elif layer_mode == "22 縣市詳細標記":
        df_map_points = df_date[~df_date["regionName"].isin(REGION_MAPPING.keys())]
    else:
        df_map_points = df_date

    # 建立 Folium 地圖實例 (中心定位於台灣)
    m = folium.Map(
        location=[23.75, 120.95],
        zoom_start=7,
        tiles="CartoDB positron",
        control_scale=True
    )

    # 在地圖上逐一添加圓形標記
    for _, row in df_map_points.iterrows():
        reg_name = row["regionName"]
        min_temp = row["minT"]
        max_temp = row["maxT"]
        avg_temp = row["avgT"]
        color = get_temperature_color(avg_temp)
        desc = get_comfort_desc(min_temp, max_temp)

        # 取得座標
        coord = COORDINATES.get(reg_name)
        if not coord:
            continue

        # HTML 彈窗
        popup_html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto; min-width: 170px;">
          <h4 style="margin: 0 0 6px 0; color: #1E88E5; border-bottom: 2px solid #E2E8F0; padding-bottom: 4px;">📍 {reg_name}</h4>
          <div style="font-size: 13px; line-height: 1.6;">
            <b>預報日期：</b>{selected_date}<br>
            <b>最低氣溫：</b><span style="color: #1E88E5; font-weight: 600;">{min_temp} °C</span><br>
            <b>最高氣溫：</b><span style="color: #E53935; font-weight: 600;">{max_temp} °C</span><br>
            <b>平均氣溫：</b>{avg_temp} °C<br>
            <div style="margin-top: 6px; padding: 4px 8px; border-radius: 4px; background: {color}; color: white; font-size: 12px; text-align: center;">
              {desc}
            </div>
          </div>
        </div>
        """

        folium.CircleMarker(
            location=[coord[0], coord[1]],
            radius=15 if reg_name in REGION_MAPPING else 11,
            color="#FFFFFF",
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.88,
            tooltip=f"<b>{reg_name}</b>: 平均 {avg_temp} °C ({desc})",
            popup=folium.Popup(popup_html, max_width=250)
        ).add_to(m)

    # 渲染 Folium 地圖組件
    st_folium(m, width="100%", height=560, returned_objects=[])


# ------------------------------------------
# TAB 3: 系統架構與規格 (Architecture)
# ------------------------------------------
with tab_arch:
    st.subheader("⚙️ 系統管線架構與規格說明 (System Architecture)")

    col_a1, col_a2 = st.columns(2)
    with col_a1:
        st.markdown("""
        #### 🔄 資料生命週期流程
        1. **資料提取 (Extract)**：
           - 呼叫中央氣象署 CWA API 資料集 `F-D0047-091`
           - 透過 HTTP Authorization 標頭安全認證
        2. **資料轉換 (Transform)**：
           - 拆解多層深層巢狀 JSON 階層
           - 萃取 `MinT` / `MaxT` 並清洗為日期結構
           - 計算全台 7 大分區聚合均值
        3. **資料持久化 (Load)**：
           - SQLite3 `data.db` 檔案儲存
           - `UNIQUE(regionName, dataDate) ON CONFLICT REPLACE` 冪等性防呆
        4. **前端視覺化 (Visualize)**：
           - Streamlit 響應式佈局
           - Altair 雙線動態走勢圖
           - Folium 台灣四階色溫圖層
        """)

    with col_a2:
        st.markdown("""
        #### 🗄️ 資料庫綱要 (Database Schema)
        ```sql
        CREATE TABLE TemperatureForecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            regionName TEXT NOT NULL,
            dataDate TEXT NOT NULL,
            minT REAL NOT NULL,
            maxT REAL NOT NULL,
            UNIQUE(regionName, dataDate) ON CONFLICT REPLACE
        );
        ```
        """)

        st.markdown("""
        #### 🎯 階段完成進度
        - [x] **Phase 1**：環境配置與金鑰取得
        - [x] **Phase 2**：CWA API 資料採集 (Extract)
        - [x] **Phase 3**：JSON 剖析與清洗 (Transform)
        - [x] **Phase 4**：SQLite 資料庫落庫 (Load)
        - [x] **Phase 5**：Streamlit 互動儀表板
        - [x] **Phase 6**：Folium 地圖地理空間視覺化
        - [x] **Phase 7**：程式品質優化與防呆
        - [x] **Phase 8**：Git 版本控制與發布
        """)

st.markdown("---")
st.caption("Taiwan Weather Forecast Dashboard © 2026 | Developed with ❤️ for AIoT Course HW1")
