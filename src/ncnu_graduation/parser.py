# HTML 解析模組
import re
from bs4 import BeautifulSoup, NavigableString
from typing import Dict, Any, List

def parse_html_to_json(html_content: str, entry_year: str, deptid: str, class_code: str, dept_info: Dict[str, str], raw_html_path: str) -> Dict[str, Any]:
    """解析 HTML 並產生結構化 JSON"""
    soup = BeautifulSoup(html_content, "lxml")
    
    result = {
        "requirementSetId": f"{entry_year}-{deptid}-{class_code}",
        "source": "ccweb6_graduation_requirements",
        "entryYear": str(entry_year),
        "departmentId": str(deptid),
        "departmentName": dept_info.get("單位中文名稱", ""),
        "departmentShortName": dept_info.get("單位中文簡稱", ""),
        "classCode": str(class_code),
        "className": dept_info.get("className", ""),
        "rawHtmlPath": raw_html_path,
        "groups": [],
        "notes": []
    }
    
    tables = soup.find_all("table")
    
    for i, table in enumerate(tables):
        group = {
            "groupId": f"group_{i+1:03d}",
            "name": f"group_{i+1:03d}",
            "type": "course_list",
            "requiredCredits": None,
            "courses": [],
            "description": "",
            "originalRows": []
        }
        
        # 尋找前方的文字標題
        # 使用 previous_elements 尋找離這個 table 最近的有效純文字節點
        for elem in table.previous_elements:
            if isinstance(elem, NavigableString):
                text = str(elem).strip()
                # 排除過短或顯然不是標題的雜訊
                if len(text) > 3 and len(text) < 100 and "{" not in text and "}" not in text:
                    group["name"] = text
                    break
        
        # 自動推斷 type
        group_name = group["name"]
        if "先修" in group_name or "擋修" in group_name:
            group["type"] = "prerequisite_rules"
        elif "核心" in group_name or "通識" in group_name:
            group["type"] = "core_requirements"
        elif "輔系" in group_name:
            group["type"] = "minor_courses"
        elif "雙主修" in group_name:
            group["type"] = "double_major_courses"
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
            elif "先修課號" in h:
                target_course_id_idx = idx
            elif "先修課名" in h:
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
                        group["courses"].append({
                            "courseId": c_id,
                            "courseName": c_name,
                            "targetCourseId": t_id,
                            "targetCourseName": t_name
                        })
                        is_parsed = True
            
            # 如果是普通的課程清單
            elif course_id_idx != -1 and course_name_idx != -1 and len(cells) > max(course_id_idx, course_name_idx):
                course_id = cells[course_id_idx].text.strip()
                course_name = cells[course_name_idx].text.strip()
                
                # 基本驗證是否像一門課
                if len(course_name) > 0 and len(course_id) > 2 and course_id.upper() != "合計":
                    course_credits = None
                    if credits_idx != -1 and len(cells) > credits_idx:
                        try:
                            credit_str = cells[credits_idx].text.strip()
                            m = re.search(r'\d+', credit_str)
                            if m:
                                course_credits = int(m.group())
                        except ValueError:
                            pass
                            
                    group["courses"].append({
                        "courseId": course_id,
                        "courseName": course_name,
                        "credits": course_credits
                    })
                    is_parsed = True
                    
            # 若為跨欄的總計或其他無法解析成單一課程的列，放進 originalRows
            if not is_parsed:
                group["originalRows"].append(row_texts)
            
        result["groups"].append(group)
        
    return result
