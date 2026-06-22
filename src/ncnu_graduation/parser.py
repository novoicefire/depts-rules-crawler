# HTML 解析模組
import re
from bs4 import BeautifulSoup, NavigableString
from typing import Dict, Any, List

def is_requirement_table(table) -> bool:
    rows = table.find_all("tr")
    if len(rows) < 2:
        return False

    text = table.get_text(" ", strip=True)

    negative_keywords = ["檢視", "修改", "刪除", "搜尋", "查詢", "返回", "上一頁", "下一頁"]
    if any(keyword in text for keyword in negative_keywords) and not any(k in text for k in ["課號", "課名", "學分", "必修", "輔系", "雙主修"]):
        return False

    positive_keywords = ["課號", "課名", "科目", "課程", "學分", "必修", "選修", "輔系", "雙主修", "通識", "先修", "擋修"]
    return any(keyword in text for keyword in positive_keywords)



def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

TITLE_PATTERN = re.compile(
    r"(\d{2,3}\s*學年度入學(?:(?!\d{2,3}\s*學年度入學).){0,160}?(?:清單|一覽表))"
)

def extract_title_from_text(text: str) -> str | None:
    text = normalize_text(text)
    if not text:
        return None

    matches = TITLE_PATTERN.findall(text)
    if matches:
        # 若同一段文字包含多個標題，取最後一個離 table 最近的標題
        return normalize_text(matches[-1])

    return None

def find_group_name(table, fallback: str) -> str:
    chunks = []
    cursor = table.previous_sibling

    while cursor is not None:
        # 遇到上一張表格就停止，避免跨到上一個 group
        if getattr(cursor, "name", None) == "table":
            break

        if isinstance(cursor, NavigableString):
            chunks.append(str(cursor))
        elif getattr(cursor, "name", None) == "br":
            pass
        elif hasattr(cursor, "get_text"):
            chunks.append(cursor.get_text(" ", strip=True))

        cursor = cursor.previous_sibling

    # previous_sibling 是由近到遠，先檢查最近文字
    for text in chunks:
        title = extract_title_from_text(text)
        if title:
            return title

    # 若文字被切碎，再合併嘗試
    combined = " ".join(reversed(chunks))
    title = extract_title_from_text(combined)
    if title:
        return title

    return fallback

def parse_credit_value_from_text(text: str) -> int | float | None:
    text = normalize_text(text)
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*學分", text)
    if not matches:
        return None

    value = float(matches[-1])
    return int(value) if value.is_integer() else value

def infer_required_credits(group: dict) -> int | float | None:
    for row in reversed(group.get("originalRows", [])):
        if isinstance(row, dict):
            row_text = row.get("rawText") or " ".join(row.get("cells", []))
        else:
            row_text = " ".join(row)

        if "合計" in row_text or "小計" in row_text or "至少選修合計" in row_text:
            value = parse_credit_value_from_text(row_text)
            if value is not None:
                return value

    credits = []
    for course in group.get("courses", []):
        c = course.get("credits")
        if isinstance(c, (int, float)):
            credits.append(c)

    if credits:
        total = float(sum(credits))
        return int(total) if total.is_integer() else total

    return None

def parse_html_to_json(html_content: str, entry_year: str, deptid: str, class_code: str, dept_info: Dict[str, str], raw_html_path: str) -> Dict[str, Any]:
    """解析 HTML 並產生結構化 JSON"""
    soup = BeautifulSoup(html_content, "lxml")
    
    result = {
        "requirementSetId": f"{entry_year}-{deptid}-{class_code}",
        "source": "ccweb6_graduation_requirements",
        "entryYear": entry_year,
        "departmentId": deptid,
        "departmentName": dept_info.get("單位中文名稱", ""),
        "departmentShortName": dept_info.get("單位中文簡稱", ""),
        "classCode": class_code,
        "className": dept_info.get("className", ""),
        "rawHtmlPath": raw_html_path,
        "groups": [],
        "notes": []
    }
    
    tables = soup.select("table.ncnu_table1")
    if not tables:
        tables = [table for table in soup.find_all("table") if is_requirement_table(table)]
    
    for i, table in enumerate(tables):
        group: Dict[str, Any] = {
            "groupId": f"group_{i+1:03d}",
            "name": f"group_{i+1:03d}",
            "type": "course_list",
            "requiredCredits": None,
            "courses": [],
            "rules": [],
            "description": "",
            "originalRows": []
        }
        
        group["name"] = find_group_name(table, f"group_{i+1:03d}")
        
        # 自動推斷 type
        group_name = group["name"]
        if "先修" in group_name or "擋修" in group_name:
            group["type"] = "prerequisite_rules"
        elif "輔系" in group_name:
            group["type"] = "minor_courses"
        elif "雙主修" in group_name:
            group["type"] = "double_major_courses"
        elif "校核心" in group_name or "通識" in group_name or "共同" in group_name:
            group["type"] = "core_requirements"
        elif "必修" in group_name:
            group["type"] = "required_courses"
        elif "選修" in group_name:
            group["type"] = "elective_courses"
            
        rows = table.find_all("tr")
        if not rows:
            continue
            
        # 第一列當作 header 尋找對應欄位
        headers = [th.text.strip() for th in rows[0].find_all(["th", "td"])]
            
        course_id_idx = -1
        course_name_idx = -1
        credits_idx = -1
        target_course_id_idx = -1
        target_course_name_idx = -1
        
        for idx, h in enumerate(headers):
            if h in ["課號", "科目代碼"] or (h == "課號" and "先修" not in h):
                course_id_idx = idx
            elif h in ["課名", "課程名稱", "科目名稱"]:
                course_name_idx = idx
            elif "學分" in h:
                credits_idx = idx
            elif h in ["先修課號", "先修課程"]:
                target_course_id_idx = idx
            elif h in ["先修課名", "先修課程名稱"]:
                target_course_name_idx = idx
                
        # 針對先修表格的 fallback，如果 header 有 4 個 (課號, 課名, 先修課號, 先修課名)
        if group["type"] == "prerequisite_rules" and len(headers) >= 4:
            if course_id_idx == -1: course_id_idx = 0
            if course_name_idx == -1: course_name_idx = 1
            if target_course_id_idx == -1: target_course_id_idx = 2
            if target_course_name_idx == -1: target_course_name_idx = 3

        # 解析每一列資料
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            row_texts = [c.text.strip() for c in cells]
            
            if not row_texts or not any(row_texts):
                continue
                
            is_parsed = False
            
            # 如果是先修規則
            if group["type"] == "prerequisite_rules" and target_course_id_idx != -1 and target_course_name_idx != -1:
                if len(cells) > max(course_id_idx, course_name_idx, target_course_id_idx, target_course_name_idx):
                    c_id = cells[course_id_idx].text.strip()
                    c_name = cells[course_name_idx].text.strip()
                    t_id = cells[target_course_id_idx].text.strip()
                    t_name = cells[target_course_name_idx].text.strip()
                    
                    if len(c_name) > 0 and len(c_id) > 2:
                        group["rules"].append({
                            "courseId": c_id,
                            "courseName": c_name,
                            "requiredCourseId": t_id,
                            "requiredCourseName": t_name
                        })
                        is_parsed = True
            
            # 如果是普通的課程清單
            elif group["type"] != "prerequisite_rules" and course_id_idx != -1 and course_name_idx != -1 and len(cells) > max(course_id_idx, course_name_idx):
                course_id = cells[course_id_idx].text.strip()
                course_name = cells[course_name_idx].text.strip()
                
                # 基本驗證是否像一門課
                if len(course_name) > 0 and len(course_id) > 2 and course_id.upper() != "合計":
                    course_credits = None
                    if credits_idx != -1 and len(cells) > credits_idx:
                        credit_str = cells[credits_idx].text.strip()
                        m = re.search(r"\d+(?:\.\d+)?", credit_str)
                        if m:
                            course_credits = float(m.group())
                            if course_credits.is_integer():
                                course_credits = int(course_credits)
                            
                    group["courses"].append({
                        "courseId": course_id,
                        "courseName": course_name,
                        "credits": course_credits
                    })
                    is_parsed = True
                    
            # 若為跨欄的總計或其他無法解析成單一課程的列，放進 originalRows
            if not is_parsed:
                group["originalRows"].append({
                    "cells": row_texts,
                    "rawText": " ".join(row_texts)
                })
            
        group["requiredCredits"] = infer_required_credits(group)
        result["groups"].append(group)
        
    return result
