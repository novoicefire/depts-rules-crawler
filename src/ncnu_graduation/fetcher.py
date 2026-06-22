# 爬蟲模組
import time
import requests
from typing import Optional, Dict, Tuple, List
import urllib.parse
from bs4 import BeautifulSoup
from .config import DETAIL_URL_TEMPLATE, LIST_URL_TEMPLATE, HEADERS
import logging

logger = logging.getLogger(__name__)

def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session

def is_valid_html(html: str, entry_year: str, deptid: str, class_code: str = "") -> Tuple[bool, str]:
    """判斷抓回來的 HTML 是否有效"""
    if not html:
        return False, "missing_html"

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    if len(text) < 200:
        return False, "too_short"

    blocked_keywords = [
        "請先登入",
        "500 Internal Server Error",
        "404 Not Found",
        "Fatal error",
        "Warning:"
    ]
    for keyword in blocked_keywords:
        if keyword in text:
            return False, f"blocked_keyword_{keyword}"

    if str(entry_year) not in text:
        return False, "missing_entry_year"

    class_name_map = {
        "B": "學士班",
        "G": "碩士班",
        "P": "博士班"
    }

    class_name = ""
    if class_code:
        class_name = class_name_map.get(class_code, "")
        if class_name and class_name not in text:
            return False, "missing_class_name"

    rule_tables = soup.select("table.ncnu_table1")
    has_rule_table = len(rule_tables) > 0

    import re
    title_pattern = re.compile(
        r"\d{2,3}\s*學年度入學(?:(?!\d{2,3}\s*學年度入學).){0,160}?(?:清單|一覽表)"
    )
    has_rule_title = bool(title_pattern.search(text))

    empty_phrases = [
        "查無必修課程資料",
        "查無系必修(選)課程資料",
        "查無系必修課程資料",
        "查無必修(選)課程資料"
    ]
    has_empty_phrase = any(phrase in text for phrase in empty_phrases)

    if has_rule_table or has_rule_title:
        return True, "ok"

    if has_empty_phrase:
        return True, "valid_empty_requirements"

    positive_keywords = ["課號", "課名", "科目", "課程", "學分", "必修", "選修", "輔系", "雙主修", "通識"]
    if any(keyword in text for keyword in positive_keywords):
        return True, "ok"

    return False, "no_positive_keyword"

def fetch_requirements_html(entry_year: str, deptid: str, class_code: str, timeout: int = 20, session: Optional[requests.Session] = None) -> Tuple[int, Optional[str], bool, str]:
    """
    抓取單筆修業規則 HTML
    回傳 (HTTP 狀態碼, HTML 內容或 None, is_valid, reason)
    """
    url = DETAIL_URL_TEMPLATE.format(
        entry_year=entry_year,
        deptid=deptid,
        class_code=class_code
    )
    
    session = session or create_session()
    try:
        response = session.get(url, timeout=timeout)
        status_code = response.status_code
        response.raise_for_status()
        
        html = response.text
        is_valid, reason = is_valid_html(html, entry_year, deptid, class_code)
        return status_code, html, is_valid, reason
            
    except requests.RequestException as e:
        status_code = getattr(e.response, "status_code", 500) if hasattr(e, "response") else 500
        return status_code, None, False, "request_exception"

def get_detail_url(entry_year: str, deptid: str, class_code: str) -> str:
    """產生 detail 頁面 URL"""
    return DETAIL_URL_TEMPLATE.format(
        entry_year=entry_year,
        deptid=deptid,
        class_code=class_code
    )

def fetch_available_combinations(entry_year: str, session: Optional[requests.Session] = None) -> List[Tuple[str, str]]:
    """
    從列表頁面抓取該年度所有有效的 (deptid, class_code) 組合，
    取代窮舉法，大幅減少無效的網路請求。
    """
    url = LIST_URL_TEMPLATE.format(entry_year=entry_year)
    session = session or create_session()
    for attempt in range(20):
        try:
            response = session.get(url, timeout=20)
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

