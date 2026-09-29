"""
fetch_cwa_data.py
中央氣象署 (CWA) 即時自動氣象站觀測資料採集與處理模組 (ETL Pipeline)
- 資料集：O-A0003-001 (自動氣象站-現在天氣觀測報告)
- 提供：即時氣溫、今日高低溫、精確站點 GPS 座標、濕度、風速、雨量
"""

import os
import sys
import logging
import requests
import urllib3
from typing import Dict, Any, Optional, List, Tuple
import pandas as pd
from dotenv import load_dotenv

# 處理 Windows 控制台編碼問題
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 設定日誌格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# 載入 .env 環境變數
load_dotenv()

# 氣象署 Open Data API 常數定義
CWA_API_BASE_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"
DEFAULT_DATASET_ID = "O-A0003-001"  # 自動氣象站 - 現在天氣觀測報告 (即時)


# 台灣區域與縣市映射關係 (依據中央氣象預報分區標準)
REGION_MAPPING: Dict[str, List[str]] = {
    "北部地區": ["基隆市", "臺北市", "新北市", "桃園市", "新竹市", "新竹縣", "苗栗縣"],
    "中部地區": ["臺中市", "彰化縣", "南投縣", "雲林縣"],
    "南部地區": ["嘉義市", "嘉義縣", "臺南市", "高雄市", "屏東縣"],
    "東北部地區": ["宜蘭縣"],
    "東部地區": ["花蓮縣"],
    "東南部地區": ["臺東縣"],
    "離島地區": ["澎湖縣", "金門縣", "連江縣"],
}


def get_api_key() -> str:
    """取得 CWA API 金鑰，若未設定則拋出例外。"""
    api_key = os.getenv("CWA_API_KEY", "").strip()
    if not api_key or api_key == "CWA-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX":
        raise ValueError(
            "未找到有效的 CWA_API_KEY！請在 .env 檔案中設定 CWA_API_KEY=您的金鑰，"
            "或設定環境變數。"
        )
    return api_key


def fetch_weather_data(
    api_key: Optional[str] = None,
    dataset_id: str = DEFAULT_DATASET_ID,
    timeout: int = 20
) -> Dict[str, Any]:
    """
    【階段二：資料採集】
    從中央氣象署 CWA Open Data API 取得 O-A0003-001 即時觀測原始 JSON 資料。
    """
    if not api_key:
        api_key = get_api_key()

    url = f"{CWA_API_BASE_URL}/{dataset_id}"
    params = {"Authorization": api_key, "format": "JSON"}

    logger.info(f"正在向 CWA API 請求資料集 [{dataset_id}] (即時自動氣象站觀測)...")

    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.SSLError:
        logger.warning("標準 SSL 驗證失敗，切換為相容模式...")
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.get(url, params=params, verify=False, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"API 請求失敗: {e}")
        raise

    raw_json = response.json()
    is_success = str(raw_json.get("success", "")).lower() == "true"
    if not is_success:
        raise RuntimeError(f"CWA API 回應錯誤: {raw_json.get('message', '未知錯誤')}")

    station_count = len(raw_json.get("records", {}).get("Station", []))
    logger.info(f"成功取得 [{dataset_id}]！共 {station_count} 個氣象站。")
    return raw_json


def _safe_float(value: Any, sentinel: float = -90.0) -> Optional[float]:
    """安全轉換為 float，低於 sentinel（無效值）回傳 None。"""
    try:
        f = float(value)
        return None if f <= sentinel else f
    except (ValueError, TypeError):
        return None


def parse_observation_data(raw_json: Dict[str, Any]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    【階段三：資料剖析與清洗 — O-A0003-001 專用】
    解析自動氣象站即時觀測 JSON，提取：
    - 站名、縣市、精確 WGS84 GPS 座標
    - 即時氣溫、今日高低溫、濕度、風速、雨量、天氣描述

    回傳 (df_stations, df_summary)：
    - df_stations : 完整站點明細 (每站一行)
    - df_summary  : 縣市 + 七大分區彙整 (相容舊版 TemperatureForecasts 結構)
    """
    logger.info("開始執行階段三：解析 O-A0003-001 即時觀測 JSON...")

    stations = raw_json.get("records", {}).get("Station", [])
    if not stations:
        raise ValueError("JSON 結構異常：找不到 records.Station 資料節點")

    rows: List[Dict[str, Any]] = []
    for s in stations:
        try:
            station_name = s.get("StationName", "").strip()
            county_name  = s.get("GeoInfo", {}).get("CountyName", "").strip()
            obs_time     = s.get("ObsTime", {}).get("DateTime", "")

            # WGS84 座標
            lat = lon = None
            for coord in s.get("GeoInfo", {}).get("Coordinates", []):
                if coord.get("CoordinateName") == "WGS84":
                    lat = _safe_float(coord.get("StationLatitude"))
                    lon = _safe_float(coord.get("StationLongitude"))
                    break
            if lat is None or lon is None:
                continue

            we = s.get("WeatherElement", {})
            obs_temp     = _safe_float(we.get("AirTemperature"))
            humidity     = _safe_float(we.get("RelativeHumidity"))
            wind_speed   = _safe_float(we.get("WindSpeed"))
            precipitation = _safe_float(we.get("Now", {}).get("Precipitation"))
            weather_desc = we.get("Weather", "")

            max_t = _safe_float(
                we.get("DailyExtreme", {}).get("DailyHigh", {})
                  .get("TemperatureInfo", {}).get("AirTemperature")
            ) or obs_temp
            min_t = _safe_float(
                we.get("DailyExtreme", {}).get("DailyLow", {})
                  .get("TemperatureInfo", {}).get("AirTemperature")
            ) or obs_temp

            rows.append({
                "stationName": station_name,
                "countyName":  county_name,
                "lat": lat, "lon": lon,
                "obsTime": obs_time,
                "dataDate": obs_time[:10] if obs_time else "",
                "obsTemp": round(obs_temp, 1) if obs_temp is not None else None,
                "minT":    round(min_t, 1)    if min_t    is not None else None,
                "maxT":    round(max_t, 1)    if max_t    is not None else None,
                "humidity": humidity,
                "windSpeed": wind_speed,
                "precipitation": precipitation,
                "weather": weather_desc,
            })
        except Exception as ex:
            logger.warning(f"解析站點 [{s.get('StationName','')}] 失敗，跳過: {ex}")

    df_stations = pd.DataFrame(rows).dropna(subset=["obsTemp"])
    if df_stations.empty:
        raise ValueError("未能自 O-A0003-001 擷取出任何有效站點記錄")
    logger.info(f"有效站點：{len(df_stations)} 個")

    # ── 縣市彙整 ──
    county_agg = (
        df_stations.dropna(subset=["minT", "maxT"])
        .groupby(["countyName", "dataDate"])
        .agg(obsTemp=("obsTemp", "mean"), minT=("minT", "min"), maxT=("maxT", "max"))
        .reset_index().rename(columns={"countyName": "regionName"})
    )
    for col in ["obsTemp", "minT", "maxT"]:
        county_agg[col] = county_agg[col].round(1)

    # ── 七大分區彙整 ──
    regional_rows: List[Dict[str, Any]] = []
    for region_name, county_list in REGION_MAPPING.items():
        sub = county_agg[county_agg["regionName"].isin(county_list)]
        if not sub.empty:
            for date, grp in sub.groupby("dataDate"):
                regional_rows.append({
                    "regionName": region_name, "dataDate": date,
                    "obsTemp": round(float(grp["obsTemp"].mean()), 1),
                    "minT":    round(float(grp["minT"].min()),    1),
                    "maxT":    round(float(grp["maxT"].max()),    1),
                })

    df_regions  = pd.DataFrame(regional_rows)
    df_summary  = pd.concat([df_regions, county_agg], ignore_index=True)
    df_summary  = df_summary.sort_values(["regionName", "dataDate"]).reset_index(drop=True)

    logger.info(
        f"階段三完成：{len(df_stations)} 站點 → "
        f"{len(df_regions)} 區域 + {len(county_agg)} 縣市 彙整記錄"
    )
    return df_stations, df_summary


def parse_weather_data(raw_json: Dict[str, Any], include_counties: bool = True) -> pd.DataFrame:
    """向後相容包裝：回傳彙整 DataFrame，供舊版 app.py 呼叫。"""
    _, df_summary = parse_observation_data(raw_json)
    return df_summary


# ==========================================
# 階段四：SQLite 資料庫設計與落庫 (Storage & Loading)
# ==========================================

DB_PATH = "data.db"


def init_database(db_path: str = DB_PATH) -> None:
    """初始化 SQLite 資料庫，建立彙整表與站點觀測表。"""
    import sqlite3
    logger.info(f"正在初始化 SQLite 資料庫 [{db_path}]...")
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        # 彙整溫度表 (相容舊版，新增 obsTemp 欄)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS TemperatureForecasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                regionName TEXT NOT NULL,
                dataDate TEXT NOT NULL,
                obsTemp REAL,
                minT REAL NOT NULL,
                maxT REAL NOT NULL,
                UNIQUE(regionName, dataDate) ON CONFLICT REPLACE
            );
        """)
        # 即時站點觀測表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS StationObservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stationName TEXT NOT NULL,
                countyName TEXT,
                lat REAL, lon REAL,
                obsTime TEXT, dataDate TEXT,
                obsTemp REAL, minT REAL, maxT REAL,
                humidity REAL, windSpeed REAL, precipitation REAL, weather TEXT,
                UNIQUE(stationName, obsTime) ON CONFLICT REPLACE
            );
        """)
        conn.commit()
    logger.info("資料庫初始化完成。")


def save_to_database(
    df: pd.DataFrame,
    db_path: str = DB_PATH,
    stations_df: pd.DataFrame = None
) -> int:
    """將彙整 DataFrame 寫入 TemperatureForecasts，並選擇性地寫入站點明細。"""
    import sqlite3
    init_database(db_path)
    logger.info(f"正在將 {len(df)} 筆彙整數據寫入 [{db_path}]...")

    with sqlite3.connect(db_path) as conn:
        records = [
            (
                str(row.get("regionName", "")),
                str(row.get("dataDate", "")),
                float(row["obsTemp"]) if pd.notna(row.get("obsTemp")) else None,
                float(row["minT"]) if pd.notna(row.get("minT")) else 0.0,
                float(row["maxT"]) if pd.notna(row.get("maxT")) else 0.0,
            )
            for _, row in df.iterrows()
        ]
        conn.executemany("""
            INSERT INTO TemperatureForecasts (regionName, dataDate, obsTemp, minT, maxT)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(regionName, dataDate) DO UPDATE SET
                obsTemp = excluded.obsTemp,
                minT = excluded.minT,
                maxT = excluded.maxT;
        """, records)

        if stations_df is not None and not stations_df.empty:
            st_recs = [
                (
                    str(r.get("stationName", "")), str(r.get("countyName", "")),
                    float(r["lat"]) if pd.notna(r.get("lat")) else None,
                    float(r["lon"]) if pd.notna(r.get("lon")) else None,
                    str(r.get("obsTime", "")), str(r.get("dataDate", "")),
                    float(r["obsTemp"]) if pd.notna(r.get("obsTemp")) else None,
                    float(r["minT"])    if pd.notna(r.get("minT"))    else None,
                    float(r["maxT"])    if pd.notna(r.get("maxT"))    else None,
                    float(r["humidity"]) if pd.notna(r.get("humidity")) else None,
                    float(r["windSpeed"]) if pd.notna(r.get("windSpeed")) else None,
                    float(r["precipitation"]) if pd.notna(r.get("precipitation")) else None,
                    str(r.get("weather", "")),
                )
                for _, r in stations_df.iterrows()
            ]
            conn.executemany("""
                INSERT INTO StationObservations
                    (stationName,countyName,lat,lon,obsTime,dataDate,
                     obsTemp,minT,maxT,humidity,windSpeed,precipitation,weather)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(stationName,obsTime) DO UPDATE SET
                    obsTemp=excluded.obsTemp, minT=excluded.minT, maxT=excluded.maxT,
                    humidity=excluded.humidity, windSpeed=excluded.windSpeed,
                    precipitation=excluded.precipitation, weather=excluded.weather;
            """, st_recs)
            logger.info(f"站點資料落庫：{len(st_recs)} 筆")

        conn.commit()

    logger.info(f"彙整資料落庫完成：{len(records)} 筆")
    return len(records)


def verify_database(db_path: str = DB_PATH) -> None:
    """驗證資料庫內容並輸出檢查報告。"""
    import sqlite3
    logger.info(f"正在驗證資料庫 [{db_path}]...")
    with sqlite3.connect(db_path) as conn:
        total_count = conn.execute("SELECT COUNT(*) FROM TemperatureForecasts;").fetchone()[0]
        try:
            station_count = conn.execute("SELECT COUNT(*) FROM StationObservations;").fetchone()[0]
        except Exception:
            station_count = 0
        distinct_regions = [
            row[0] for row in conn.execute(
                "SELECT DISTINCT regionName FROM TemperatureForecasts ORDER BY regionName;"
            ).fetchall()
        ]
        sample = pd.read_sql_query(
            "SELECT regionName, dataDate, obsTemp, minT, maxT "
            "FROM TemperatureForecasts "
            "WHERE regionName IN ('北部地區','中部地區','南部地區') "
            "ORDER BY regionName, dataDate LIMIT 9;",
            conn
        )

    print("\n" + "=" * 65)
    print("  🗄️  SQLite 資料庫 (O-A0003-001 即時站點) 落庫驗證結果")
    print("=" * 65)
    print(f"  • 資料庫路徑    : {os.path.abspath(db_path)}")
    print(f"  • 彙整記錄筆數  : {total_count} 筆")
    print(f"  • 站點觀測筆數  : {station_count} 筆")
    print(f"  • 涵蓋地區 ({len(distinct_regions)}): {', '.join(distinct_regions)}")
    print("\n--- 【分區彙整樣本：北/中/南部地區】---")
    print(sample.to_string(index=False))
    print("=" * 65 + "\n")


def run_etl_pipeline(db_path: str = DB_PATH) -> pd.DataFrame:
    """執行完整 ETL 管線：採集 O-A0003-001 ➔ 解析 ➔ 落庫。"""
    api_key = get_api_key()
    raw_data = fetch_weather_data(api_key=api_key, dataset_id=DEFAULT_DATASET_ID)
    df_stations, df_summary = parse_observation_data(raw_data)
    save_to_database(df_summary, db_path=db_path, stations_df=df_stations)
    verify_database(db_path=db_path)
    return df_summary


def main():
    """執行完整 ETL 管線：階段二至階段四。"""
    try:
        run_etl_pipeline(DB_PATH)
    except Exception as e:
        logger.error(f"ETL 流程發生錯誤: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

