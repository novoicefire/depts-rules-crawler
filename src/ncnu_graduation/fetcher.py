# 爬蟲模組
import time
import requests
from typing import Optional, Dict, Tuple, List
import urllib.parse
from bs4 import BeautifulSoup
from .config import DETAIL_URL_TEMPLATE, LIST_URL_TEMPLATE, HEADERS
import logging

logger = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

def is_valid_html(html: str, entry_year: str, deptid: str, class_code: str = "") -> bool:
    """判斷抓回來的 HTML 是否有效"""
    if not html:
        return False

    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)

    if len(text) < 200:
        return False

    blocked_keywords = ["請先登入", "查無資料", "發生錯誤", "錯誤", "Error", "404", "500 Internal Server Error"]
    if any(keyword in text for keyword in blocked_keywords):
        return False

    if str(entry_year) not in text:
        return False

    class_name_map = {
        "B": "學士班",
        "G": "碩士班",
        "P": "博士班"
    }

    if class_code:
        class_name = class_name_map.get(class_code)
        if class_name and class_name not in text:
            return False

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return False

    positive_keywords = ["查詢修業規則", "必修課程", "學分", "課號", "課名", "輔系", "雙主修", "通識", "先修", "擋修"]
    return any(keyword in text for keyword in positive_keywords)

def fetch_requirements_html(entry_year: str, deptid: str, class_code: str, timeout: int = 20) -> Tuple[int, Optional[str]]:
    """
    抓取單筆修業規則 HTML
    回傳 (HTTP 狀態碼, HTML 內容或 None)
    """
    url = DETAIL_URL_TEMPLATE.format(
        entry_year=entry_year,
        deptid=deptid,
        class_code=class_code
    )
    
    try:
        response = SESSION.get(url, timeout=timeout)
        status_code = response.status_code
        response.raise_for_status()
        
        html = response.text
        if is_valid_html(html, entry_year, deptid, class_code):
            return status_code, html
        else:
            return status_code, ""
            
    except requests.RequestException as e:
        status_code = getattr(e.response, "status_code", 500) if hasattr(e, "response") else 500
        return status_code, None

def get_detail_url(entry_year: str, deptid: str, class_code: str) -> str:
    """產生 detail 頁面 URL"""
    return DETAIL_URL_TEMPLATE.format(
        entry_year=entry_year,
        deptid=deptid,
        class_code=class_code
    )

def fetch_available_combinations(entry_year: str) -> List[Tuple[str, str]]:
    """
    從列表頁面抓取該年度所有有效的 (deptid, class_code) 組合，
    取代窮舉法，大幅減少無效的網路請求。
    """
    url = LIST_URL_TEMPLATE.format(entry_year=entry_year)
    for attempt in range(20):
        try:
            response = SESSION.get(url, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            combinations = []
            # 尋找所有檢視連結
            links = soup.select('a[href*="viewview.php"][href*="deptid="][href*="class_code="][href*="entry_year="]')
            for link in links:
                href = link.get('href', '')
                parsed_url = urllib.parse.urlparse(href)
                qs = urllib.parse.parse_qs(parsed_url.query)
                
                href_year = qs.get("entry_year", [""])[0]
                if href_year and href_year != str(entry_year):
                    continue
                
                deptid = qs.get('deptid', [''])[0]
                class_code = qs.get('class_code', [''])[0]
                
                if deptid and class_code:
                    combinations.append((deptid, class_code))
                    
            # 去除重複項並保持順序
            seen = set()
            unique_combinations = []
            for comb in combinations:
                if comb not in seen:
                    unique_combinations.append(comb)
                    seen.add(comb)
                    
            return sorted(unique_combinations, key=lambda x: (x[0], x[1]))
        except Exception as e:
            logger.warning(f"Failed to fetch list for {entry_year} (Attempt {attempt+1}/20): {e}")
            time.sleep(5)
            
    logger.error(f"Completely failed to fetch list for {entry_year} after 20 attempts.")
    return []

