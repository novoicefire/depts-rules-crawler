# 驗證模組
import json
from pathlib import Path
from typing import Dict, Any, List
import logging
from .config import BASE_DIR, INDEXES_DIR

logger = logging.getLogger(__name__)

def is_meta_group_name(name: str) -> bool:
    if not name:
        return True

    has_meta = all(k in name for k in ["系所", "部別", "入學年度"])
    has_real_title = any(k in name for k in ["清單", "一覽表", "必修", "先修", "擋修", "輔系", "雙主修", "校核心", "通識"])

    return has_meta and not has_real_title

def validate_all(probe: bool = False, strict: bool = False) -> Dict[str, Any]:
    """執行完整驗證並回傳報告"""
    report = {
        "index_exists": False,
        "index_readable": False,
        "total_items": 0,
        "duplicate_ids": [],
        "missing_files": [],
        "invalid_schema": [],
        "specific_check_112_12_B": "Not Found",
        "passed": False
    }
    
    index_path = INDEXES_DIR / "curriculum_rules_index.json"
    if not index_path.exists():
        logger.error("Index file not found.")
        return report
        
    report["index_exists"] = True
    
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index_data = json.load(f)
        report["index_readable"] = True
    except Exception as e:
        logger.error(f"Failed to read index: {e}")
        return report
        
    items = index_data.get("items", [])
    report["total_items"] = len(items)
    
    if not items:
        report["invalid_schema"].append({
            "id": "index",
            "error": "Index contains no items"
        })
    
    seen_ids = set()
    
    for item in items:
        req_id = item.get("requirementSetId")
        if req_id in seen_ids:
            report["duplicate_ids"].append(req_id)
        seen_ids.add(req_id)
        
        parsed_path_str = item.get("path")
        if not parsed_path_str:
            report["missing_files"].append(req_id)
            continue
            
        parsed_path = BASE_DIR / parsed_path_str
        if not parsed_path.exists():
            report["missing_files"].append(parsed_path_str)
            continue
            
        # Check schema
        try:
            with open(parsed_path, "r", encoding="utf-8") as f:
                parsed_json = json.load(f)
                
            required_keys = ["requirementSetId", "entryYear", "departmentId", "classCode", "groups"]
            missing_keys = [k for k in required_keys if k not in parsed_json]
            
            if missing_keys:
                report["invalid_schema"].append({
                    "id": req_id,
                    "missing": missing_keys
                })
                
            # Check consistency between index and parsed JSON
            checks = ["requirementSetId", "entryYear", "departmentId", "classCode"]
            for c in checks:
                if parsed_json.get(c) != item.get(c):
                    report["invalid_schema"].append({
                        "id": req_id,
                        "error": f"Inconsistent {c}: index={item.get(c)}, json={parsed_json.get(c)}"
                    })
                    
            # Check groups schema
            groups = parsed_json.get("groups")
            if not isinstance(groups, list):
                report["invalid_schema"].append({
                    "id": req_id,
                    "error": "groups must be a list"
                })
            else:
                group_names = [g.get("name", "") for g in groups]
                
                if strict and len(groups) > 1 and len(set(group_names)) == 1:
                    report["invalid_schema"].append({
                        "id": req_id,
                        "error": "all group names are identical"
                    })
                    
                if strict and not any(("清單" in name or "一覽表" in name) for name in group_names):
                    report["invalid_schema"].append({
                        "id": req_id,
                        "error": "no group name contains 清單 or 一覽表"
                    })

                for idx, g in enumerate(groups):
                    missing = []
                    for k in ["groupId", "name", "type", "courses", "originalRows"]:
                        if k not in g:
                            missing.append(k)
                            
                    if missing:
                        report["invalid_schema"].append({
                            "id": req_id,
                            "error": f"group {idx} missing keys: {missing}"
                        })
                        continue
                        
                    if not isinstance(g.get("courses"), list):
                        report["invalid_schema"].append({
                            "id": req_id,
                            "error": f"group {idx} courses must be a list"
                        })
                        
                    if not isinstance(g.get("originalRows"), list):
                        report["invalid_schema"].append({
                            "id": req_id,
                            "error": f"group {idx} originalRows must be a list"
                        })
                        
                    if "requiredCredits" in g and g["requiredCredits"] is not None and not isinstance(g["requiredCredits"], (int, float)):
                        report["invalid_schema"].append({
                            "id": req_id,
                            "error": f"group {idx} requiredCredits must be number or null"
                        })
                        
                    if strict:
                        if is_meta_group_name(g.get("name", "")):
                            report["invalid_schema"].append({
                                "id": req_id,
                                "error": f"group {idx} name looks like page metadata, not a rule title: {g.get('name', '')}"
                            })

                        has_courses = len(g.get("courses", [])) > 0
                        has_rules = len(g.get("rules", [])) > 0
                        has_orig = len(g.get("originalRows", [])) > 0
                        
                        if not (has_courses or has_rules or has_orig):
                            report["invalid_schema"].append({
                                "id": req_id,
                                "error": f"group {idx} is completely empty (strict mode)"
                            })
                
            # Specific check for 112-12-B
            if req_id == "112-12-B":
                if isinstance(groups, list) and len(groups) > 0:
                    report["specific_check_112_12_B"] = "Passed"
                else:
                    report["specific_check_112_12_B"] = "Failed (No groups found)"
                    
        except Exception as e:
            report["invalid_schema"].append({
                "id": req_id,
                "error": str(e)
            })
            
    # Determine overall pass
    if (report["index_exists"] and 
        report["index_readable"] and 
        len(report["duplicate_ids"]) == 0 and 
        len(report["missing_files"]) == 0 and 
        len(report["invalid_schema"]) == 0):
        
        if probe and report["specific_check_112_12_B"] != "Passed":
            report["passed"] = False
        else:
            report["passed"] = True
            
    return report
