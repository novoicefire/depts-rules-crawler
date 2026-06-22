# 驗證模組
import json
from pathlib import Path
from typing import Dict, Any, List
import logging
from .config import BASE_DIR, INDEXES_DIR

logger = logging.getLogger(__name__)

def validate_all() -> Dict[str, Any]:
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
                
            # Specific check for 112-12-B
            if req_id == "112-12-B":
                if len(parsed_json.get("groups", [])) > 0:
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
        
        # If 112-12-B was found, it must pass
        if report["specific_check_112_12_B"] in ["Passed", "Not Found"]:
            report["passed"] = True
            
    return report
