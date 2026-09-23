"""
fetch_cwa_data.py
中央氣象署 (CWA) 天氣預報資料採集與處理模組 (ETL Pipeline)
- 階段二：資料採集 (Phase 2: Data Extraction)
- 階段三：資料剖析與清洗 (Phase 3: Data Transformation)
"""

import os
import sys
import logging
import requests
import urllib3
from typing import Dict, Any, Optional, List
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
DEFAULT_DATASET_ID = "F-D0047-091"  # 臺灣各縣市未來 1 週天氣預報

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
    timeout: int = 15
) -> Dict[str, Any]:
    """
    【階段二：資料採集】
    從中央氣象署 CWA Open Data API 取得指定資料集之原始 JSON 資料。
    """
    if not api_key:
        api_key = get_api_key()

    url = f"{CWA_API_BASE_URL}/{dataset_id}"
    headers = {
        "Authorization": api_key,
        "accept": "application/json"
    }

    logger.info(f"正在向 CWA API 請求資料集 [{dataset_id}]...")

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.SSLError:
        logger.warning("標準 SSL 驗證失敗，切換為相容模式發送請求...")
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.get(url, headers=headers, verify=False, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"API 請求失敗: {e}")
        raise

    raw_json = response.json()

    is_success = str(raw_json.get("success", "")).lower() == "true"
    if not is_success:
        msg = raw_json.get("message", "API 回應未成功")
        raise RuntimeError(f"CWA API 回應錯誤: {msg}")

    logger.info(f"成功取得資料集 [{dataset_id}]！大小: {len(response.content) / 1024:.2f} KB")
    return raw_json


def parse_weather_data(raw_json: Dict[str, Any], include_counties: bool = True) -> pd.DataFrame:
    """
    【階段三：資料剖析與清洗】
    解析 CWA 原始巢狀 JSON 資料，提取一週各地最高氣溫 (MaxT) 與最低氣溫 (MinT)，
    並依據區域進行彙整計算，回傳乾淨結構化的 Pandas DataFrame。

    :param raw_json: fetch_weather_data 回傳之字典物件
    :param include_counties: 是否一併保留各縣市明細 (預設為 True)
    :return: 包含 regionName, dataDate, minT, maxT 之 DataFrame
    """
    logger.info("開始執行階段三：解析巢狀 JSON 並清洗氣象數據...")

    records = raw_json.get("records", {})
    locations_list = records.get("Locations", records.get("locations", []))

    if not locations_list:
        raise ValueError("JSON 結構異常：找不到 Records.Locations 資料節點")

    location_items = locations_list[0].get("Location", locations_list[0].get("location", []))
    if not location_items:
        raise ValueError("JSON 結構異常：找不到 Location 清單")

    county_rows: List[Dict[str, Any]] = []

    # 1. 逐一縣市提取最低溫與最高溫
    for loc in location_items:
        location_name = loc.get("LocationName", loc.get("locationName", "")).strip()
        weather_elements = loc.get("WeatherElement", loc.get("weatherElement", []))

        # 用於收集各日期的最低溫與最高溫清單
        daily_min: Dict[str, List[float]] = {}
        daily_max: Dict[str, List[float]] = {}

        for elem in weather_elements:
            elem_name = elem.get("ElementName", elem.get("elementName", "")).strip()

            # 最低溫判斷 (MinT / 最低溫度 / MinTemperature)
            if elem_name in ["最低溫度", "MinTemperature", "MinT"]:
                for t in elem.get("Time", elem.get("time", [])):
                    start_time = t.get("StartTime", t.get("startTime", ""))
                    if not start_time:
                        continue
                    date_str = start_time.split("T")[0]
                    vals = t.get("ElementValue", t.get("elementValue", []))
                    if vals:
                        val_raw = vals[0].get("MinTemperature", vals[0].get("value", None))
                        try:
                            val_float = float(val_raw)
                            daily_min.setdefault(date_str, []).append(val_float)
                        except (ValueError, TypeError):
                            continue

            # 最高溫判斷 (MaxT / 最高溫度 / MaxTemperature)
            elif elem_name in ["最高溫度", "MaxTemperature", "MaxT"]:
                for t in elem.get("Time", elem.get("time", [])):
                    start_time = t.get("StartTime", t.get("startTime", ""))
                    if not start_time:
                        continue
                    date_str = start_time.split("T")[0]
                    vals = t.get("ElementValue", t.get("elementValue", []))
                    if vals:
                        val_raw = vals[0].get("MaxTemperature", vals[0].get("value", None))
                        try:
                            val_float = float(val_raw)
                            daily_max.setdefault(date_str, []).append(val_float)
                        except (ValueError, TypeError):
                            continue

        # 計算該縣市當日的總體 minT 與 maxT
        common_dates = sorted(set(daily_min.keys()) & set(daily_max.keys()))
        for d in common_dates:
            county_rows.append({
                "regionName": location_name,
                "dataDate": d,
                "minT": round(float(min(daily_min[d])), 1),
                "maxT": round(float(max(daily_max[d])), 1),
            })

    df_counties = pd.DataFrame(county_rows)
    if df_counties.empty:
        raise ValueError("未能自 API 資料中擷取出任何氣溫記錄，請檢查資料結構。")

    # 2. 彙整計算六大區域預報平均數據 (北部、中部、南部、東北部、東部、東南部、離島)
    regional_rows: List[Dict[str, Any]] = []
    for region_name, county_list in REGION_MAPPING.items():
        sub_df = df_counties[df_counties["regionName"].isin(county_list)]
        if not sub_df.empty:
            grouped = sub_df.groupby("dataDate").agg({"minT": "mean", "maxT": "mean"}).reset_index()
            for _, row in grouped.iterrows():
                regional_rows.append({
                    "regionName": region_name,
                    "dataDate": row["dataDate"],
                    "minT": round(float(row["minT"]), 1),
                    "maxT": round(float(row["maxT"]), 1),
                })

    df_regions = pd.DataFrame(regional_rows)

    # 3. 依參數決定是否合併區域與個別縣市資料
    if include_counties:
        df_final = pd.concat([df_regions, df_counties], ignore_index=True)
    else:
        df_final = df_regions

    # 型態確認與排序
    df_final["regionName"] = df_final["regionName"].astype(str)
    df_final["dataDate"] = df_final["dataDate"].astype(str)
    df_final["minT"] = df_final["minT"].astype(float)
    df_final["maxT"] = df_final["maxT"].astype(float)

    # 依地區與日期排序
    df_final = df_final.sort_values(by=["regionName", "dataDate"]).reset_index(drop=True)

    logger.info(
        f"階段三完成：共產生 {len(df_final)} 筆清洗後預報記錄 "
        f"({len(df_regions)} 筆區域匯總, {len(df_counties)} 筆縣市明細)"
    )
    return df_final


# ==========================================
# 階段四：SQLite 資料庫設計與落庫 (Storage & Loading)
# ==========================================

DB_PATH = "data.db"


def init_database(db_path: str = DB_PATH) -> None:
    """
    初始化 SQLite 資料庫與建立 TemperatureForecasts 資料表。
    設定 UNIQUE(regionName, dataDate) 以支援防重複寫入 (冪等性)。
    """
    import sqlite3
    logger.info(f"正在初始化 SQLite 資料庫 [{db_path}]...")
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS TemperatureForecasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                regionName TEXT NOT NULL,
                dataDate TEXT NOT NULL,
                minT REAL NOT NULL,
                maxT REAL NOT NULL,
                UNIQUE(regionName, dataDate) ON CONFLICT REPLACE
            );
        """)
        conn.commit()
    logger.info("資料庫與資料表結構初始化完成。")


def save_to_database(df: pd.DataFrame, db_path: str = DB_PATH) -> int:
    """
    將清洗後的 DataFrame 資料寫入 SQLite 資料庫。
    使用 INSERT OR REPLACE INTO 確保重複執行不產生重複數據。

    :param df: 包含 regionName, dataDate, minT, maxT 之 DataFrame
    :param db_path: 資料庫檔案路徑
    :return: 成功寫入或更新的筆數
    """
    import sqlite3
    init_database(db_path)

    logger.info(f"正在將 {len(df)} 筆預報數據寫入資料庫 [{db_path}]...")
    records_to_insert = [
        (row["regionName"], row["dataDate"], float(row["minT"]), float(row["maxT"]))
        for _, row in df.iterrows()
    ]

    sql = """
        INSERT INTO TemperatureForecasts (regionName, dataDate, minT, maxT)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(regionName, dataDate) DO UPDATE SET
            minT = excluded.minT,
            maxT = excluded.maxT;
    """

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.executemany(sql, records_to_insert)
        conn.commit()

    logger.info(f"成功落庫 {len(records_to_insert)} 筆數據至 [{db_path}]！")
    return len(records_to_insert)


def verify_database(db_path: str = DB_PATH) -> None:
    """驗證資料庫內容並輸出檢查報告。"""
    import sqlite3
    logger.info(f"正在驗證資料庫 [{db_path}] 落庫內容...")
    with sqlite3.connect(db_path) as conn:
        total_count = conn.execute("SELECT COUNT(*) FROM TemperatureForecasts;").fetchone()[0]
        distinct_regions = [
            row[0] for row in conn.execute(
                "SELECT DISTINCT regionName FROM TemperatureForecasts ORDER BY regionName;"
            ).fetchall()
        ]
        sample_central = pd.read_sql_query(
            "SELECT * FROM TemperatureForecasts WHERE regionName = '中部地區' ORDER BY dataDate ASC;",
            conn
        )

    print("\n" + "=" * 65)
    print("  🗄️ SQLite 資料庫 (Phase 4) 落庫驗證結果")
    print("=" * 65)
    print(f"  • 資料庫路徑   : {os.path.abspath(db_path)}")
    print(f"  • 總儲存筆數   : {total_count} 筆")
    print(f"  • 涵蓋地區數   : {len(distinct_regions)} 個")
    print(f"  • 資料庫地區清單: {', '.join(distinct_regions[:8])} ...")
    print("\n--- 【SQL 查詢驗證：中部地區資料】---")
    print(sample_central.to_string(index=False))
    print("=" * 65 + "\n")


def run_etl_pipeline(db_path: str = DB_PATH) -> pd.DataFrame:
    """執行完整 ETL 管線：採集 ➔ 清洗 ➔ 落庫。"""
    api_key = get_api_key()
    raw_data = fetch_weather_data(api_key=api_key)
    df = parse_weather_data(raw_data, include_counties=True)
    save_to_database(df, db_path=db_path)
    verify_database(db_path=db_path)
    return df


def main():
    """執行完整 ETL 管線：階段二至階段四。"""
    try:
        run_etl_pipeline(DB_PATH)
    except Exception as e:
        logger.error(f"ETL 流程發生錯誤: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

