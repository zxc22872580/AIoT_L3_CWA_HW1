"""
app.py
Taiwan Weather Forecast — 台灣天氣預報互動式 Web 儀表板
階段五：Streamlit 互動儀表板 (Web Dashboard)
"""

import os
import sqlite3
import pandas as pd
import altair as alt
import streamlit as st
from datetime import datetime

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
# 1. 頁面基本設定 (Page Config)
# ==========================================
st.set_page_config(
    page_title="Taiwan Weather Forecast — 台灣氣象預報",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自訂 CSS 提升介面精美質感
st.markdown("""
<style>
    /* 主標題與副標題樣式 */
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
    /* 指標卡片美化 */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700;
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


# 載入預報資料
df_all = load_data_from_db(DB_PATH)


# ==========================================
# 3. 側邊欄 (Sidebar) 設定與控制
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
        **核心技術棧**：
        - 🌐 中央氣象署 CWA API
        - 🐍 Python + Pandas
        - 🗄️ SQLite 關聯資料庫
        - 📊 Streamlit + Altair
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
  <br><small>專案循序遵循 24 單元實戰地圖：自 CWA Open Data API 串接、SQLite 冪等入庫至 Streamlit 互動視覺化。</small>
</div>
""", unsafe_allow_html=True)

if df_all.empty:
    st.error("未能載入預報資料，請檢查 .env 中的 CWA_API_KEY 設定或點擊左側「🔄 立即重新擷取 CWA 資料」。")
    st.stop()


# ==========================================
# 5. 地區選擇器 (Region Selector - 單元 13)
# ==========================================
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
    st.stop()


# ==========================================
# 6. 今日氣溫重點指標 (KPI Metric Cards)
# ==========================================
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


# ==========================================
# 7. 一週最高與最低氣溫折線圖 (單元 14)
# ==========================================
st.subheader(f"📈 【{selected_region}】未來一週氣溫走向趨勢圖 (Line Chart)")

# 轉換為適合 Altair 繪製雙折線的長格式 (Melted Format)
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

# 使用 Altair 繪製具備頂級視覺感的折線圖
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


# ==========================================
# 8. 詳細預報資料清單表格 (單元 15 & 16)
# ==========================================
st.subheader(f"📋 【{selected_region}】未來一週氣溫明細表 (Data Table)")

df_display = df_region.copy()
df_display["tempDiff"] = (df_display["maxT"] - df_display["minT"]).round(1)

# 加入舒適度輔助描述
def get_comfort_desc(row):
    avg = (row["minT"] + row["maxT"]) / 2
    if avg < 20:
        return "🔵 偏涼注意保暖"
    elif avg <= 25:
        return "🟢 氣溫舒適宜人"
    elif avg <= 30:
        return "🟡 稍有暖熱"
    else:
        return "🔴 炎熱注意防曬"

df_display["comfortLevel"] = df_display.apply(get_comfort_desc, axis=1)

# 重新命名欄位方便檢視
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

st.markdown("---")
st.caption("Taiwan Weather Forecast Dashboard © 2026 | Powered by Streamlit & CWA Open Data")
