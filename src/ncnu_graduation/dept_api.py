# 開課單位 API 串接模組
import requests
from typing import List, Dict, Any
from .config import DEPT_API_URL, HEADERS

def fetch_all_departments() -> List[Dict[str, Any]]:
    """
    取得所有開課單位代碼。
    回傳範例：
    [
        {
            "開課單位代碼": "12",
            "單位中文名稱": "國際企業學系",
            "單位英文名稱": "International Business Studies",
            "單位中文簡稱": "國企系"
        },
        ...
    ]
    """
    response = requests.get(DEPT_API_URL, headers=HEADERS, timeout=10)
    response.raise_for_status()
    data = response.json()
    return data.get("course_deptId", {}).get("item", [])
