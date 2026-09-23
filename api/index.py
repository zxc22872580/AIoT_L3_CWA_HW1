"""
api/index.py
Vercel Serverless Python 入口函式
提供 Taiwan Weather Forecast 現代化 Web 儀表板與 RESTful API
"""

import os
import json
import sqlite3
import urllib.parse
from http.server import BaseHTTPRequestHandler
from typing import Dict, Any, List

# 預設氣象資料 (備援資料，確保即便無資料庫或無網路也能完美呈現畫面)
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
]


def get_forecast_records() -> List[Dict[str, Any]]:
    """自本機 SQLite 資料庫或備援資料集載入預報記錄。"""
    db_path = os.path.join(os.path.dirname(__file__), "..", "data.db")
    if os.path.exists(db_path):
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT regionName, dataDate, minT, maxT FROM TemperatureForecasts ORDER BY regionName, dataDate ASC;")
                rows = cursor.fetchall()
                if rows:
                    return [
                        {"regionName": r[0], "dataDate": r[1], "minT": float(r[2]), "maxT": float(r[3])}
                        for r in rows
                    ]
        except Exception:
            pass
    return FALLBACK_DATA


def generate_html_dashboard(data: List[Dict[str, Any]]) -> str:
    """生成完全自包含的現代化繁體中文氣象儀表板 HTML。"""
    data_json = json.dumps(data, ensure_ascii=False)
    
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Taiwan Weather Forecast — 台灣天氣預報儀表板</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --primary: #1E88E5;
      --primary-light: #E3F2FD;
      --accent: #00C9FF;
      --text-dark: #1A202C;
      --text-muted: #718096;
      --bg-card: #FFFFFF;
      --bg-page: #F7FAFC;
      --border: #E2E8F0;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background-color: var(--bg-page);
      color: var(--text-dark);
      padding: 24px 16px;
      line-height: 1.5;
    }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    
    /* 頂部標題 */
    .header {{
      background: var(--bg-card);
      padding: 24px;
      border-radius: 12px;
      border: 1px solid var(--border);
      margin-bottom: 20px;
      box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    }}
    .title {{
      font-size: 1.8rem;
      font-weight: 800;
      background: linear-gradient(120deg, #1E88E5, #00C9FF);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 6px;
    }}
    .subtitle {{ color: var(--text-muted); font-size: 0.95rem; margin-bottom: 12px; }}
    .quote-box {{
      background: rgba(30, 136, 229, 0.08);
      border-left: 4px solid var(--primary);
      padding: 10px 14px;
      border-radius: 4px;
      font-size: 0.9rem;
      color: #2D3748;
    }}
    
    /* 控制列 */
    .controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      align-items: center;
      margin-bottom: 20px;
      background: var(--bg-card);
      padding: 16px 20px;
      border-radius: 10px;
      border: 1px solid var(--border);
    }}
    .select-label {{ font-weight: 600; font-size: 0.95rem; }}
    select {{
      padding: 8px 14px;
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: 0.95rem;
      background: white;
      cursor: pointer;
      outline: none;
    }}
    select:focus {{ border-color: var(--primary); }}
    
    /* 指標卡片 */
    .metrics-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .metric-card {{
      background: var(--bg-card);
      padding: 18px 20px;
      border-radius: 10px;
      border: 1px solid var(--border);
      box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }}
    .metric-title {{ font-size: 0.85rem; color: var(--text-muted); margin-bottom: 4px; }}
    .metric-val {{ font-size: 1.8rem; font-weight: 800; color: var(--primary); }}
    .metric-sub {{ font-size: 0.8rem; color: #A0AEC0; margin-top: 2px; }}
    
    /* 圖表與地圖網格 */
    .content-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
      margin-bottom: 24px;
    }}
    @media (max-width: 900px) {{
      .content-grid {{ grid-template-columns: 1fr; }}
    }}
    .panel {{
      background: var(--bg-card);
      padding: 20px;
      border-radius: 10px;
      border: 1px solid var(--border);
      box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }}
    .panel-title {{
      font-size: 1.1rem;
      font-weight: 700;
      margin-bottom: 14px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    #map {{ height: 350px; width: 100%; border-radius: 8px; }}
    
    /* 表格 */
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9rem;
      text-align: left;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
    }}
    th {{ background: #F8FAFC; color: #4A5568; font-weight: 600; }}
    tr:hover {{ background: #F7FAFC; }}
    
    /* 標籤 */
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 0.78rem;
      font-weight: 600;
      color: white;
    }}
    .badge-cool {{ background: #1E88E5; }}
    .badge-good {{ background: #43A047; }}
    .badge-warm {{ background: #FDD835; color: #333; }}
    .badge-hot  {{ background: #E53935; }}

    footer {{
      text-align: center;
      margin-top: 30px;
      color: var(--text-muted);
      font-size: 0.85rem;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header class="header">
      <h1 class="title">🌤️ Taiwan Weather Forecast — 台灣天氣預報儀表板</h1>
      <p class="subtitle">AI 創新微課程實戰專案 · CWA Open Data × Python × SQLite × Vercel Serverless</p>
      <div class="quote-box">
        💡 <b>煥哥心法引言</b>：<i>「技術可以解決問題，但更重要的是用技術創造更好的未來！」</i>
      </div>
    </header>

    <div class="controls">
      <span class="select-label">📍 請選擇預報區域：</span>
      <select id="regionSelect" onchange="updateDashboard()">
        <option value="中部地區" selected>中部地區</option>
        <option value="北部地區">北部地區</option>
        <option value="南部地區">南部地區</option>
        <option value="東北部地區">東北部地區</option>
        <option value="東部地區">東部地區</option>
        <option value="東南部地區">東南部地區</option>
        <option value="離島地區">離島地區</option>
      </select>
      <span style="font-size: 0.85rem; color: #718096; margin-left: auto;">
        🚀 部署平台：<b>Vercel Serverless</b> | 資料來源：<b>交通部中央氣象署</b>
      </span>
    </div>

    <!-- 指標區塊 -->
    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-title">今日最低溫 (MinT)</div>
        <div class="metric-val" id="kpiMinT">-- °C</div>
        <div class="metric-sub">清晨 / 夜間預測低溫</div>
      </div>
      <div class="metric-card">
        <div class="metric-title">今日最高溫 (MaxT)</div>
        <div class="metric-val" id="kpiMaxT" style="color: #E53935;">-- °C</div>
        <div class="metric-sub">日間預測最高溫</div>
      </div>
      <div class="metric-card">
        <div class="metric-title">今日預測溫差</div>
        <div class="metric-val" id="kpiDiff" style="color: #43A047;">-- °C</div>
        <div class="metric-sub">日夜溫差注意</div>
      </div>
      <div class="metric-card">
        <div class="metric-title">一週平均氣溫</div>
        <div class="metric-val" id="kpiAvg" style="color: #D97706;">-- °C</div>
        <div class="metric-sub">未來 7 日整體平均</div>
      </div>
    </div>

    <!-- 圖表與地圖 -->
    <div class="content-grid">
      <div class="panel">
        <div class="panel-title">📈 未來一週最高與最低氣溫走勢圖</div>
        <canvas id="tempChart" height="230"></canvas>
      </div>
      <div class="panel">
        <div class="panel-title">🗺️ 台灣互動式氣溫地圖</div>
        <div id="map"></div>
      </div>
    </div>

    <!-- 表格區塊 -->
    <div class="panel">
      <div class="panel-title">📋 一週天氣預報明細數據表</div>
      <table>
        <thead>
          <tr>
            <th>預報日期</th>
            <th>地區名稱</th>
            <th>最低氣溫 (°C)</th>
            <th>最高氣溫 (°C)</th>
            <th>日溫差 (°C)</th>
            <th>天氣體感建議</th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
    </div>

    <footer>
      Taiwan Weather Forecast Dashboard © 2026 | Powered by Vercel Serverless & CWA Open Data
    </footer>
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
      "離島地區": [23.57, 119.57]
    }};

    function getColor(avg) {{
      if (avg < 20) return '#1E88E5';
      if (avg <= 25) return '#43A047';
      if (avg <= 30) return '#FDD835';
      return '#E53935';
    }}

    function getBadge(avg) {{
      if (avg < 20) return '<span class="badge badge-cool">🔵 偏涼注意保暖</span>';
      if (avg <= 25) return '<span class="badge badge-good">🟢 氣溫舒適宜人</span>';
      if (avg <= 30) return '<span class="badge badge-warm">🟡 暖熱稍有出汗</span>';
      return '<span class="badge badge-hot">🔴 炎熱注意防曬</span>';
    }}

    let chartInstance = null;
    let mapInstance = null;
    let markerGroup = null;

    function initMap() {{
      mapInstance = L.map('map').setView([23.75, 120.95], 7);
      L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
        attribution: '&copy; OpenStreetMap &copy; CARTO',
        maxZoom: 18
      }}).addTo(mapInstance);
      markerGroup = L.layerGroup().addTo(mapInstance);
    }}

    function renderMapMarkers() {{
      markerGroup.clearLayers();
      const firstDate = allData[0]?.dataDate;
      const dayData = allData.filter(d => d.dataDate === firstDate);

      dayData.forEach(item => {{
        const pt = coords[item.regionName];
        if (pt) {{
          const avg = ((item.minT + item.maxT) / 2).toFixed(1);
          const color = getColor(avg);
          const circle = L.circleMarker(pt, {{
            radius: 12,
            fillColor: color,
            color: '#FFFFFF',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.85
          }});

          circle.bindPopup(`
            <div style="font-family: sans-serif; min-width: 140px;">
              <h4 style="margin: 0 0 4px 0; color: #1E88E5;">📍 ${{item.regionName}}</h4>
              <b>日期：</b>${{item.dataDate}}<br>
              <b>最低溫：</b>${{item.minT}} °C<br>
              <b>最高溫：</b>${{item.maxT}} °C<br>
              <b>平均溫：</b>${{avg}} °C
            </div>
          `);
          markerGroup.addLayer(circle);
        }}
      }});
    }}

    function updateDashboard() {{
      const selected = document.getElementById('regionSelect').value;
      const rows = allData.filter(d => d.regionName === selected);

      if (rows.length === 0) return;

      // 更新指標
      const today = rows[0];
      const todayDiff = (today.maxT - today.minT).toFixed(1);
      const avgAll = (rows.reduce((acc, cur) => acc + (cur.minT + cur.maxT) / 2, 0) / rows.length).toFixed(1);

      document.getElementById('kpiMinT').innerText = today.minT + ' °C';
      document.getElementById('kpiMaxT').innerText = today.maxT + ' °C';
      document.getElementById('kpiDiff').innerText = todayDiff + ' °C';
      document.getElementById('kpiAvg').innerText = avgAll + ' °C';

      // 更新表格
      const tbody = document.getElementById('tableBody');
      tbody.innerHTML = '';
      rows.forEach(r => {{
        const diff = (r.maxT - r.minT).toFixed(1);
        const avg = (r.minT + r.maxT) / 2;
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><b>${{r.dataDate}}</b></td>
          <td>${{r.regionName}}</td>
          <td style="color: #1E88E5; font-weight: 600;">${{r.minT}} °C</td>
          <td style="color: #E53935; font-weight: 600;">${{r.maxT}} °C</td>
          <td>${{diff}} °C</td>
          <td>${{getBadge(avg)}}</td>
        `;
        tbody.appendChild(tr);
      }});

      // 更新折線圖
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
              label: '最高氣溫 (MaxT)',
              data: maxTemps,
              borderColor: '#E53935',
              backgroundColor: 'rgba(229, 57, 53, 0.1)',
              tension: 0.3,
              fill: false,
              pointRadius: 4,
              borderWidth: 2.5
            }},
            {{
              label: '最低氣溫 (MinT)',
              data: minTemps,
              borderColor: '#1E88E5',
              backgroundColor: 'rgba(30, 136, 229, 0.1)',
              tension: 0.3,
              fill: false,
              pointRadius: 4,
              borderWidth: 2.5
            }}
          ]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{
            legend: {{ position: 'top' }}
          }},
          scales: {{
            y: {{
              title: {{ display: true, text: '氣溫 (°C)' }}
            }}
          }}
        }}
      }});
    }}

    window.addEventListener('DOMContentLoaded', () => {{
      initMap();
      renderMapMarkers();
      updateDashboard();
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

        # 提供 API 端點
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

        # 預設首頁呈現完整氣象儀表板
        data = get_forecast_records()
        html_content = generate_html_dashboard(data).encode("utf-8")
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
