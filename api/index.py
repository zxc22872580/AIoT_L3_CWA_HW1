"""
api/index.py
Taiwan Weather Forecast — 類 Windy 風格台灣即時氣象地圖儀表板
參考 taiwan-weather-map.vercel.app 現代深色玻璃擬態 (Dark Glassmorphism) 設計
相容 Vercel Serverless Function 與本機獨立執行
"""

import os
import json
import sqlite3
import urllib.parse
from http.server import BaseHTTPRequestHandler
from typing import Dict, Any, List

# 備援資料 (確保在任何伺服器冷啟動或離線狀況下皆可立即秒級渲染)
FALLBACK_DATA = [
    {"regionName": "中部地區", "dataDate": "2026-09-23", "minT": 25.5, "maxT": 32.5},
    {"regionName": "中部地區", "dataDate": "2026-09-24", "minT": 25.5, "maxT": 32.8},
    {"regionName": "中部地區", "dataDate": "2026-09-25", "minT": 24.5, "maxT": 32.8},
    {"regionName": "中部地區", "dataDate": "2026-09-26", "minT": 24.5, "maxT": 32.8},
    {"regionName": "中部地區", "dataDate": "2026-09-27", "minT": 24.5, "maxT": 33.0},
    {"regionName": "中部地區", "dataDate": "2026-09-28", "minT": 25.2, "maxT": 33.0},
    {"regionName": "中部地區", "dataDate": "2026-09-29", "minT": 25.5, "maxT": 33.5},
    {"regionName": "北部地區", "dataDate": "2026-09-23", "minT": 22.9, "maxT": 31.1},
    {"regionName": "北部地區", "dataDate": "2026-09-24", "minT": 23.7, "maxT": 31.1},
    {"regionName": "北部地區", "dataDate": "2026-09-25", "minT": 23.7, "maxT": 31.1},
    {"regionName": "北部地區", "dataDate": "2026-09-26", "minT": 24.0, "maxT": 31.0},
    {"regionName": "北部地區", "dataDate": "2026-09-27", "minT": 23.7, "maxT": 31.7},
    {"regionName": "北部地區", "dataDate": "2026-09-28", "minT": 23.9, "maxT": 30.7},
    {"regionName": "北部地區", "dataDate": "2026-09-29", "minT": 24.7, "maxT": 30.9},
    {"regionName": "南部地區", "dataDate": "2026-09-23", "minT": 25.8, "maxT": 32.6},
    {"regionName": "南部地區", "dataDate": "2026-09-24", "minT": 26.0, "maxT": 33.0},
    {"regionName": "南部地區", "dataDate": "2026-09-25", "minT": 25.4, "maxT": 32.8},
    {"regionName": "南部地區", "dataDate": "2026-09-26", "minT": 25.4, "maxT": 33.0},
    {"regionName": "南部地區", "dataDate": "2026-09-27", "minT": 25.0, "maxT": 33.0},
    {"regionName": "南部地區", "dataDate": "2026-09-28", "minT": 25.5, "maxT": 33.0},
    {"regionName": "南部地區", "dataDate": "2026-09-29", "minT": 25.8, "maxT": 33.2},
    {"regionName": "東北部地區", "dataDate": "2026-09-23", "minT": 23.0, "maxT": 30.0},
    {"regionName": "東部地區", "dataDate": "2026-09-23", "minT": 24.0, "maxT": 30.0},
    {"regionName": "東南部地區", "dataDate": "2026-09-23", "minT": 25.0, "maxT": 31.0},
    {"regionName": "離島地區", "dataDate": "2026-09-23", "minT": 25.3, "maxT": 29.3},
    {"regionName": "臺北市", "dataDate": "2026-09-23", "minT": 24.0, "maxT": 31.5},
    {"regionName": "新北市", "dataDate": "2026-09-23", "minT": 23.5, "maxT": 31.0},
    {"regionName": "臺中市", "dataDate": "2026-09-23", "minT": 25.0, "maxT": 32.5},
    {"regionName": "臺南市", "dataDate": "2026-09-23", "minT": 25.5, "maxT": 32.0},
    {"regionName": "高雄市", "dataDate": "2026-09-23", "minT": 26.0, "maxT": 32.8},
]


def get_forecast_records() -> List[Dict[str, Any]]:
    """自本機 SQLite 資料庫或備援資料集載入預報記錄。"""
    db_path = os.path.join(os.path.dirname(__file__), "..", "data.db")
    if os.path.exists(db_path):
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT regionName, dataDate, minT, maxT FROM TemperatureForecasts ORDER BY regionName, dataDate ASC;"
                )
                rows = cursor.fetchall()
                if rows:
                    return [
                        {"regionName": r[0], "dataDate": r[1], "minT": float(r[2]), "maxT": float(r[3])}
                        for r in rows
                    ]
        except Exception:
            pass
    return FALLBACK_DATA


def generate_windy_style_html(data: List[Dict[str, Any]]) -> str:
    """生成完全參照 taiwan-weather-map.vercel.app 風格的深色流線 Web 儀表板 HTML。"""
    data_json = json.dumps(data, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
  <title>台灣即時氣象地圖 — Taiwan Weather Map</title>
  <meta name="description" content="中央氣象署開放資料即時視覺化地圖（類 Windy 深色玻璃擬態風格）" />
  
  <!-- Leaflet CSS & JS -->
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <!-- Chart.js -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <!-- Google Fonts: Inter -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">

  <style>
    :root {{
      --bg-dark: #030712;
      --panel-bg: rgba(15, 23, 42, 0.82);
      --panel-border: rgba(255, 255, 255, 0.12);
      --text-main: #F3F4F6;
      --text-muted: #9CA3AF;
      --accent-sky: #0EA5E9;
      --accent-sky-hover: #0284C7;
      --accent-emerald: #10B981;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{
      width: 100vw;
      height: 100vh;
      overflow: hidden;
      background-color: var(--bg-dark);
      color: var(--text-main);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }}

    /* 全螢幕地圖底層 */
    #map {{
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      z-index: 1;
      background-color: #0b0f19;
    }}

    /* 玻璃擬態通用面板 */
    .glass-panel {{
      background: var(--panel-bg);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid var(--panel-border);
      border-radius: 12px;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.6), 0 8px 10px -6px rgba(0, 0, 0, 0.6);
      pointer-events: auto;
      transition: all 0.2s ease;
    }}

    /* 左上角品牌與標題卡片 */
    .top-left-brand {{
      position: absolute;
      top: 16px;
      left: 16px;
      z-index: 1000;
      padding: 16px 20px;
      max-width: 380px;
    }}
    .brand-title {{
      font-size: 1.25rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      display: flex;
      align-items: center;
      gap: 8px;
      background: linear-gradient(135deg, #38BDF8 0%, #818CF8 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}
    .brand-desc {{
      font-size: 0.78rem;
      color: var(--text-muted);
      margin-top: 4px;
      line-height: 1.4;
    }}
    .mentor-pill {{
      margin-top: 10px;
      padding: 6px 10px;
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid rgba(56, 189, 248, 0.25);
      border-radius: 6px;
      font-size: 0.75rem;
      color: #7DD3FC;
      line-height: 1.4;
    }}

    /* 右上角圖層控制面板 (參考 taiwan-weather-map 右側邊欄) */
    .top-right-controls {{
      position: absolute;
      top: 16px;
      right: 16px;
      z-index: 1000;
      width: 250px;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .panel-section-title {{
      font-size: 0.68rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #64748B;
      margin-bottom: 6px;
    }}
    .layer-btn-grid {{
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}
    .layer-btn {{
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 0.85rem;
      font-weight: 500;
      border: none;
      background: rgba(255, 255, 255, 0.05);
      color: #E2E8F0;
      cursor: pointer;
      text-align: left;
      transition: all 0.15s ease;
    }}
    .layer-btn:hover {{
      background: rgba(255, 255, 255, 0.12);
      color: #FFFFFF;
    }}
    .layer-btn.active {{
      background: #0284C7;
      color: #FFFFFF;
      box-shadow: 0 0 14px rgba(14, 165, 233, 0.5);
    }}

    /* 下拉選單樣式 */
    .styled-select {{
      width: 100%;
      padding: 8px 10px;
      border-radius: 6px;
      background: rgba(15, 23, 42, 0.95);
      border: 1px solid rgba(255, 255, 255, 0.18);
      color: #F8FAFC;
      font-size: 0.82rem;
      outline: none;
      cursor: pointer;
    }}
    .styled-select:focus {{
      border-color: #38BDF8;
    }}

    /* 右下角溫度色階條 (Windy-style Spectral Colorbar) */
    .bottom-right-legend {{
      position: absolute;
      bottom: 24px;
      right: 16px;
      z-index: 1000;
      width: 290px;
      padding: 12px 16px;
    }}
    .legend-bar {{
      height: 10px;
      width: 100%;
      border-radius: 9999px;
      background: linear-gradient(to right, #2c7bb6, #5aa2cf, #abd9e9, #7fcdbb, #d9ef8b, #fee08b, #fdae61, #f46d43, #d73027);
      margin-top: 4px;
      box-shadow: 0 0 10px rgba(0,0,0,0.5);
    }}
    .legend-labels {{
      display: flex;
      justify-content: space-between;
      font-size: 10px;
      color: #94A3B8;
      font-family: monospace;
      margin-top: 6px;
    }}

    /* 底部展開式圖表抽屜 (Drawer / Chart Overlay) */
    .bottom-left-drawer {{
      position: absolute;
      bottom: 24px;
      left: 16px;
      z-index: 1000;
      width: 480px;
      max-width: calc(100vw - 32px);
      padding: 16px 20px;
    }}
    .drawer-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }}
    .drawer-title {{
      font-size: 0.95rem;
      font-weight: 700;
      color: #F8FAFC;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .metric-row {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px;
      margin-bottom: 14px;
    }}
    .mini-metric {{
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 8px;
      padding: 8px;
      text-align: center;
    }}
    .mini-label {{ font-size: 0.68rem; color: #94A3B8; }}
    .mini-value {{ font-size: 1.15rem; font-weight: 700; color: #38BDF8; margin-top: 2px; }}

    /* 地圖自訂 Popup 樣式 */
    .leaflet-popup-content-wrapper {{
      background: rgba(15, 23, 42, 0.94) !important;
      backdrop-filter: blur(12px) !important;
      border: 1px solid rgba(255, 255, 255, 0.15) !important;
      color: #F8FAFC !important;
      border-radius: 10px !important;
      box-shadow: 0 10px 25px rgba(0,0,0,0.7) !important;
    }}
    .leaflet-popup-tip {{
      background: rgba(15, 23, 42, 0.94) !important;
    }}

    /* 氣溫數值標籤 (Marker Labels) */
    .temp-marker-label {{
      background: rgba(15, 23, 42, 0.9);
      border: 1px solid rgba(255, 255, 255, 0.25);
      border-radius: 12px;
      padding: 2px 7px;
      font-size: 11px;
      font-weight: 700;
      color: #FFFFFF;
      box-shadow: 0 2px 8px rgba(0,0,0,0.6);
      white-space: nowrap;
      display: flex;
      align-items: center;
      gap: 4px;
    }}

    @media (max-width: 768px) {{
      .top-right-controls {{ width: calc(100vw - 32px); top: auto; bottom: 80px; right: 16px; display: none; }}
      .bottom-left-drawer {{ width: calc(100vw - 32px); bottom: 16px; }}
      .bottom-right-legend {{ display: none; }}
    }}
  </style>
</head>
<body>
  <!-- Leaflet 底層全屏地圖 -->
  <div id="map"></div>

  <!-- 左上角品牌資訊 -->
  <div class="glass-panel top-left-brand">
    <div class="brand-title">
      <span>🌤️</span> 台灣即時氣象地圖
    </div>
    <div class="brand-desc">
      中央氣象署開放資料即時視覺化地圖（類 Windy 風格）
    </div>
    <div class="mentor-pill">
      💡 <b>煥哥心法</b>：<i>「技術可以解決問題，但更重要的是用技術創造更好的未來！」</i>
    </div>
  </div>

  <!-- 右上角控制圖層面板 -->
  <div class="glass-panel top-right-controls">
    <div>
      <div class="panel-section-title">氣象資料圖層</div>
      <div class="layer-btn-grid">
        <button class="layer-btn active" id="btnTemp"><span>🌡️</span><span>氣溫預報</span></button>
        <button class="layer-btn" onclick="alert('雨量雷達資料集已預備接入')"><span>🌧️</span><span>即時雨量</span></button>
        <button class="layer-btn" onclick="alert('風速風向資料集已預備接入')"><span>💨</span><span>風速風向</span></button>
      </div>
    </div>

    <div>
      <div class="panel-section-title">預報日期挑選</div>
      <select class="styled-select" id="dateSelect" onchange="onDateChanged()">
      </select>
    </div>

    <div>
      <div class="panel-section-title">焦點區域切換</div>
      <select class="styled-select" id="regionSelect" onchange="onRegionChanged()">
        <option value="中部地區" selected>中部地區</option>
        <option value="北部地區">北部地區</option>
        <option value="南部地區">南部地區</option>
        <option value="東北部地區">東北部地區</option>
        <option value="東部地區">東部地區</option>
        <option value="東南部地區">東南部地區</option>
        <option value="離島地區">離島地區</option>
      </select>
    </div>

    <button class="layer-btn" style="background: rgba(16, 185, 129, 0.85); justify-content: center; font-weight: 600;" onclick="locateTaiwan()">
      <span>🎯</span><span>重設視角至全台</span>
    </button>
  </div>

  <!-- 左下角氣溫走向抽屜卡片 -->
  <div class="glass-panel bottom-left-drawer">
    <div class="drawer-header">
      <div class="drawer-title">
        <span id="drawerRegionTitle">📍 中部地區</span> · 未來一週走勢
      </div>
      <span style="font-size: 0.72rem; color: #38BDF8; font-weight: 600;">CWA Open Data API</span>
    </div>

    <div class="metric-row">
      <div class="mini-metric">
        <div class="mini-label">今日最低</div>
        <div class="mini-value" id="kpiMinT" style="color: #38BDF8;">--°C</div>
      </div>
      <div class="mini-metric">
        <div class="mini-label">今日最高</div>
        <div class="mini-value" id="kpiMaxT" style="color: #F87171;">--°C</div>
      </div>
      <div class="mini-metric">
        <div class="mini-label">預估溫差</div>
        <div class="mini-value" id="kpiDiff" style="color: #34D399;">--°C</div>
      </div>
      <div class="mini-metric">
        <div class="mini-label">一週平均</div>
        <div class="mini-value" id="kpiAvg" style="color: #FBBF24;">--°C</div>
      </div>
    </div>

    <div style="height: 140px; width: 100%;">
      <canvas id="tempChart"></canvas>
    </div>
  </div>

  <!-- 右下角 Windy 漸層圖例色條 -->
  <div class="glass-panel bottom-right-legend">
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <span style="font-size: 0.75rem; font-weight: 700; color: #E2E8F0;">氣溫色階圖例 (°C)</span>
      <span style="font-size: 0.7rem; color: #64748B;">Windy Colormap</span>
    </div>
    <div class="legend-bar"></div>
    <div class="legend-labels">
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

  <script>
    const allData = {data_json};

    // 區域座標定義
    const coords = {{
      "北部地區": [24.98, 121.35],
      "中部地區": [24.08, 120.70],
      "南部地區": [22.95, 120.35],
      "東北部地區": [24.70, 121.70],
      "東部地區": [23.85, 121.50],
      "東南部地區": [22.75, 121.10],
      "離島地區": [23.57, 119.57],
      "基隆市": [25.13, 121.74],
      "臺北市": [25.04, 121.56],
      "新北市": [25.01, 121.46],
      "桃園市": [24.99, 121.30],
      "新竹市": [24.81, 120.97],
      "新竹縣": [24.84, 121.01],
      "苗栗縣": [24.56, 120.82],
      "臺中市": [24.15, 120.67],
      "彰化縣": [24.08, 120.54],
      "南投縣": [23.91, 120.69],
      "雲林縣": [23.71, 120.43],
      "嘉義市": [23.48, 120.45],
      "嘉義縣": [23.45, 120.25],
      "臺南市": [22.99, 120.21],
      "高雄市": [22.63, 120.30],
      "屏東縣": [22.67, 120.49],
      "宜蘭縣": [24.75, 121.75],
      "花蓮縣": [23.99, 121.60],
      "臺東縣": [22.76, 121.14],
      "澎湖縣": [23.57, 119.57],
      "金門縣": [24.44, 118.37],
      "連江縣": [26.15, 119.95]
    }};

    // 類 Windy 漸層調色盤
    function getWindyColor(temp) {{
      if (temp < 10) return '#2c7bb6';
      if (temp < 15) return '#5aa2cf';
      if (temp < 20) return '#abd9e9';
      if (temp < 24) return '#7fcdbb';
      if (temp < 28) return '#d9ef8b';
      if (temp < 30) return '#fee08b';
      if (temp < 32) return '#fdae61';
      if (temp < 34) return '#f46d43';
      return '#d73027';
    }}

    let mapInstance = null;
    let markerLayerGroup = null;
    let chartInstance = null;

    function initMap() {{
      // 使用 CartoDB Dark Matter 深色地圖圖磚
      mapInstance = L.map('map', {{
        zoomControl: false,
        attributionControl: false
      }}).setView([23.75, 120.95], 7.5);

      L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
        subdomains: 'abcd',
        maxZoom: 19
      }}).addTo(mapInstance);

      // 移動縮放控制器到右上
      L.control.zoom({{ position: 'topright' }}).addTo(mapInstance);

      markerLayerGroup = L.layerGroup().addTo(mapInstance);
    }}

    function locateTaiwan() {{
      mapInstance.flyTo([23.75, 120.95], 7.5, {{ duration: 1.2 }});
    }}

    function populateDateSelect() {{
      const dateSelect = document.getElementById('dateSelect');
      const uniqueDates = Array.from(new Set(allData.map(d => d.dataDate))).sort();
      dateSelect.innerHTML = '';
      uniqueDates.forEach((d, i) => {{
        const opt = document.createElement('option');
        opt.value = d;
        opt.textContent = (i === 0) ? `${{d}} (今日)` : d;
        dateSelect.appendChild(opt);
      }});
    }}

    function renderMarkers() {{
      markerLayerGroup.clearLayers();
      const curDate = document.getElementById('dateSelect').value;
      const dayData = allData.filter(d => d.dataDate === curDate);

      dayData.forEach(item => {{
        const pt = coords[item.regionName];
        if (!pt) return;

        const avg = ((item.minT + item.maxT) / 2).toFixed(1);
        const col = getWindyColor(parseFloat(avg));

        // 發光氣泡圓標 (Glowing Marker)
        const circle = L.circleMarker(pt, {{
          radius: 14,
          fillColor: col,
          color: '#FFFFFF',
          weight: 2,
          opacity: 0.9,
          fillOpacity: 0.85
        }});

        // HTML 彈窗
        const popupContent = `
          <div style="font-family: inherit; font-size: 13px; line-height: 1.6; padding: 2px;">
            <div style="font-size: 15px; font-weight: 800; color: #38BDF8; margin-bottom: 4px;">📍 ${{item.regionName}}</div>
            <div><b>預報日期：</b>${{item.dataDate}}</div>
            <div><b>最低氣溫：</b><span style="color: #38BDF8; font-weight: 700;">${{item.minT}} °C</span></div>
            <div><b>最高氣溫：</b><span style="color: #F87171; font-weight: 700;">${{item.maxT}} °C</span></div>
            <div><b>平均氣溫：</b><span style="color: #FBBF24; font-weight: 700;">${{avg}} °C</span></div>
          </div>
        `;

        circle.bindPopup(popupContent);
        circle.bindTooltip(`<b>${{item.regionName}}</b>: ${{avg}}°C`, {{
          direction: 'top',
          permanent: false
        }});

        circle.on('click', () => {{
          const sel = document.getElementById('regionSelect');
          if (Array.from(sel.options).some(o => o.value === item.regionName)) {{
            sel.value = item.regionName;
            updateDrawer();
          }}
        }});

        markerLayerGroup.addLayer(circle);
      }});
    }}

    function updateDrawer() {{
      const selected = document.getElementById('regionSelect').value;
      document.getElementById('drawerRegionTitle').innerText = '📍 ' + selected;

      const rows = allData.filter(d => d.regionName === selected);
      if (rows.length === 0) return;

      const today = rows[0];
      const todayDiff = (today.maxT - today.minT).toFixed(1);
      const avgAll = (rows.reduce((acc, cur) => acc + (cur.minT + cur.maxT) / 2, 0) / rows.length).toFixed(1);

      document.getElementById('kpiMinT').innerText = today.minT + '°';
      document.getElementById('kpiMaxT').innerText = today.maxT + '°';
      document.getElementById('kpiDiff').innerText = todayDiff + '°';
      document.getElementById('kpiAvg').innerText = avgAll + '°';

      // 繪製 Chart.js 趨勢線圖
      const labels = rows.map(r => r.dataDate.slice(5));
      const minTemps = rows.map(r => r.minT);
      const maxTemps = rows.map(r => r.maxT);

      if (chartInstance) chartInstance.destroy();

      const ctx = document.getElementById('tempChart').getContext('2d');
      chartInstance = new Chart(ctx, {{
        type: 'line',
        data: {{
          labels: labels,
          datasets: [
            {{
              label: '最高溫 (MaxT)',
              data: maxTemps,
              borderColor: '#F87171',
              backgroundColor: 'rgba(248, 113, 113, 0.15)',
              tension: 0.35,
              fill: true,
              pointRadius: 3.5,
              borderWidth: 2
            }},
            {{
              label: '最低溫 (MinT)',
              data: minTemps,
              borderColor: '#38BDF8',
              backgroundColor: 'rgba(56, 189, 248, 0.15)',
              tension: 0.35,
              fill: true,
              pointRadius: 3.5,
              borderWidth: 2
            }}
          ]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{
            legend: {{
              labels: {{
                color: '#94A3B8',
                boxWidth: 10,
                font: {{ size: 10 }}
              }}
            }}
          }},
          scales: {{
            x: {{
              ticks: {{ color: '#64748B', font: {{ size: 10 }} }},
              grid: {{ display: false }}
            }},
            y: {{
              ticks: {{ color: '#64748B', font: {{ size: 10 }} }},
              grid: {{ color: 'rgba(255, 255, 255, 0.05)' }}
            }}
          }}
        }}
      }});
    }}

    function onDateChanged() {{
      renderMarkers();
    }}

    function onRegionChanged() {{
      updateDrawer();
      const selected = document.getElementById('regionSelect').value;
      const pt = coords[selected];
      if (pt) {{
        mapInstance.flyTo(pt, 9, {{ duration: 1 }});
      }}
    }}

    window.addEventListener('DOMContentLoaded', () => {{
      initMap();
      populateDateSelect();
      renderMarkers();
      updateDrawer();
    }});
  </script>
</body>
</html>
"""


class handler(BaseHTTPRequestHandler):
    """Vercel Serverless Function HTTP Request Handler"""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # REST API 端點
        if path.startswith("/api/forecast") or path.startswith("/api"):
            data = get_forecast_records()
            content = json.dumps({"success": True, "records": data}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        # 預設首頁呈現類 Windy 深色玻璃擬態氣象儀表板
        data = get_forecast_records()
        html_content = generate_windy_style_html(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_content)))
        self.end_headers()
        self.wfile.write(html_content)


if __name__ == "__main__":
    from http.server import HTTPServer
    server = HTTPServer(("localhost", 3000), handler)
    print("Vercel dev server running on http://localhost:3000")
    server.serve_forever()
