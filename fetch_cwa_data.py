"""
fetch_cwa_data.py
中央氣象署 (CWA) 天氣預報資料採集與處理模組 (ETL Pipeline)
階段二：資料採集 (Phase 2: Data Extraction)
"""

import os
import sys
import logging
import requests
import urllib3
from typing import Dict, Any, Optional
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
    從中央氣象署 CWA Open Data API 取得指定資料集之原始 JSON 資料。

    :param api_key: CWA 授權金鑰，若為 None 則自環境變數讀取
    :param dataset_id: 資料集識別代碼，預設為 F-D0047-091 (一週天氣預報)
    :param timeout: HTTP 請求逾時秒數 (預設 15 秒)
    :return: 解析後之 Python 字典物件 (JSON)
    :raises requests.RequestException: 網路連線或 API 呼叫失敗時拋出
    """
    if not api_key:
        api_key = get_api_key()

    url = f"{CWA_API_BASE_URL}/{dataset_id}"
    headers = {
        "Authorization": api_key,
        "accept": "application/json"
    }

    logger.info(f"正在向 CWA API 請求資料集 [{dataset_id}]...")
    
    # 發送 GET 請求，處理 SSL 憑證相容性
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

    # 驗證 API 回傳狀態
    is_success = str(raw_json.get("success", "")).lower() == "true"
    if not is_success:
        msg = raw_json.get("message", "API 回應未成功")
        raise RuntimeError(f"CWA API 回應錯誤: {msg}")

    logger.info(f"成功取得資料集 [{dataset_id}]！資料大小: {len(response.content) / 1024:.2f} KB")
    return raw_json


def main():
    """階段二執行入口：測試資料採集並輸出摘要資訊。"""
    try:
        api_key = get_api_key()
        masked_key = f"{api_key[:8]}...{api_key[-4:]}"
        logger.info(f"使用 API Key: {masked_key}")

        data = fetch_weather_data(api_key=api_key)

        # 檢視採集到的資料概要
        records = data.get("records", {})
        locations_list = records.get("Locations", records.get("locations", []))

        if locations_list:
            top_locations = locations_list[0]
            desc = top_locations.get("DatasetDescription", "無描述")
            loc_items = top_locations.get("Location", top_locations.get("location", []))
            
            print("\n" + "=" * 55)
            print("  🌤️ 中央氣象署 (CWA) 資料採集 (Phase 2) 驗證成功！")
            print("=" * 55)
            print(f"  • 資料集名稱 : {desc}")
            print(f"  • 涵蓋縣市數 : {len(loc_items)} 個")
            if loc_items:
                sample_names = [loc.get("LocationName", loc.get("locationName")) for loc in loc_items[:5]]
                print(f"  • 前 5 個地區 : {', '.join(sample_names)}")
                sample_elements = loc_items[0].get("WeatherElement", loc_items[0].get("weatherElement", []))
                elem_names = [e.get("ElementName", e.get("elementName")) for e in sample_elements[:6]]
                print(f"  • 氣象要素範例: {', '.join(elem_names)} 等共 {len(sample_elements)} 項")
            print("=" * 55 + "\n")
        else:
            logger.warning("回傳資料結構中未找到預期的 Locations 欄位。")

    except Exception as e:
        logger.error(f"階段二資料採集發生錯誤: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
