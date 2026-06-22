# 專案基礎設定與常數
import os
from pathlib import Path

# 專案根目錄
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 資料目錄
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PARSED_DIR = DATA_DIR / "parsed"
INDEXES_DIR = DATA_DIR / "indexes"
REPORTS_DIR = DATA_DIR / "reports"

# API 與目標網址
DEPT_API_URL = "https://api.ncnu.edu.tw/API/get.aspx?json=course_deptId"
DETAIL_URL_TEMPLATE = "https://ccweb6.ncnu.edu.tw/student/aspmaker_dept_student_graduation_requirements_M_viewview.php?showdetail=&deptid={deptid}&class_code={class_code}&entry_year={entry_year}"
LIST_URL_TEMPLATE = "https://ccweb6.ncnu.edu.tw/student/aspmaker_dept_student_graduation_requirements_M_viewlist.php?cmd=search&t=aspmaker_dept_student_graduation_requirements_M_view&z_deptid=%3D&x_deptid=&z_class_desc=%3D&x_class_desc=&z_entry_year=%3D&x_entry_year={entry_year}&recperpage=ALL"

# 部別代碼對照
CLASS_CODES = {
    "B": "學士班",
    "G": "碩士班",
    "P": "博士班"
}

# 爬蟲用 Headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive"
}
