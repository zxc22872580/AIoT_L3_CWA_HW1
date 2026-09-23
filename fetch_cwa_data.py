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


def main():
    """執行 ETL Pipeline：驗證階段二 (資料採集) 與 階段三 (資料清洗)。"""
    try:
        api_key = get_api_key()
        masked_key = f"{api_key[:8]}...{api_key[-4:]}"
        logger.info(f"使用 API Key: {masked_key}")

        # 階段二：取得原始 JSON
        data = fetch_weather_data(api_key=api_key)

        # 階段三：資料剖析與清洗
        df = parse_weather_data(data, include_counties=True)

        print("\n" + "=" * 65)
        print("  🌤️ 中央氣象署 (CWA) 資料清洗 (Phase 3) 成果展示")
        print("=" * 65)
        print(f"  • 總預報記錄數 : {len(df)} 筆")
        print(f"  • 不重複地區數 : {df['regionName'].nunique()} 個 (含 7 大分區與 22 縣市)")
        dates = sorted(df["dataDate"].unique())
        print(f"  • 預報日期範圍 : {dates[0]} 至 {dates[-1]} (共 {len(dates)} 天)")
        print("\n--- 【分區預報 (中部地區範例)】---")
        sample_central = df[df["regionName"] == "中部地區"]
        print(sample_central.to_string(index=False))

        print("\n--- 【各分區最新首日預報速覽】---")
        first_date = dates[0]
        region_first_day = df[
            (df["dataDate"] == first_date) & 
            (df["regionName"].isin(REGION_MAPPING.keys()))
        ]
        print(region_first_day[["regionName", "dataDate", "minT", "maxT"]].to_string(index=False))
        print("=" * 65 + "\n")

    except Exception as e:
        logger.error(f"ETL 流程發生錯誤: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
