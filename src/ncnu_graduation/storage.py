# 檔案存取相關邏輯
import json
from pathlib import Path
from .config import RAW_DIR, PARSED_DIR, INDEXES_DIR, REPORTS_DIR

def save_raw_html(entry_year: str, deptid: str, class_code: str, html_content: str) -> Path:
    """保存原始 HTML 檔案"""
    dir_path = RAW_DIR / str(entry_year) / str(deptid)
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{class_code}.html"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return file_path

def save_parsed_json(entry_year: str, deptid: str, class_code: str, data: dict) -> Path:
    """保存解析後的 JSON 檔案"""
    dir_path = PARSED_DIR / str(entry_year)
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{entry_year}-{deptid}-{class_code}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return file_path

def save_index(data: dict) -> Path:
    """保存索引檔"""
    INDEXES_DIR.mkdir(parents=True, exist_ok=True)
    file_path = INDEXES_DIR / "curriculum_rules_index.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return file_path

def save_report(report_name: str, data: dict | list) -> Path:
    """保存報告檔"""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = REPORTS_DIR / f"{report_name}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return file_path

def load_index() -> dict | None:
    """讀取索引檔"""
    file_path = INDEXES_DIR / "curriculum_rules_index.json"
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None
