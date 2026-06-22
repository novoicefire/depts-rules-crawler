# 爬蟲模組
import time
import requests
from typing import Optional, Dict, Tuple, List
import urllib.parse
from bs4 import BeautifulSoup
from .config import DETAIL_URL_TEMPLATE, LIST_URL_TEMPLATE, HEADERS
import logging

logger = logging.getLogger(__name__)

def is_valid_html(html: str, entry_year: str, deptid: str) -> bool:
    """判斷抓回來的 HTML 是否有效"""
    if "查詢修業規則" in html or "必修課程" in html:
        return True
    
    if str(entry_year) in html and str(deptid) in html:
        return True

    if "請先登入" in html or len(html.strip()) < 100:
        return False
        
    return False

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
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        status_code = response.status_code
        response.raise_for_status()
        
        html = response.text
        if is_valid_html(html, entry_year, deptid):
            return status_code, html
        else:
            return status_code, None
            
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
            response = requests.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            combinations = []
            # 尋找所有檢視連結
            links = soup.select('table.ew-table a.ew-row-link.ew-view')
            for link in links:
                href = link.get('href', '')
                parsed_url = urllib.parse.urlparse(href)
                qs = urllib.parse.parse_qs(parsed_url.query)
                
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
                    
            return unique_combinations
        except Exception as e:
            logger.warning(f"Failed to fetch list for {entry_year} (Attempt {attempt+1}/20): {e}")
            time.sleep(5)
            
    logger.error(f"Completely failed to fetch list for {entry_year} after 20 attempts.")
    return []

