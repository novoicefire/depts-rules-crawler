import subprocess
import sys
import os
from pathlib import Path
import json

def run_command(cmd_list):
    print(f"\n> 執行: {' '.join(cmd_list)}")
    result = subprocess.run(cmd_list, capture_output=True)
    sys.stdout.buffer.write(result.stdout)
    
    if result.stderr:
        sys.stderr.buffer.write(result.stderr)
            
    if result.returncode != 0:
        print(f"[FAIL] 命令執行失敗，回傳碼: {result.returncode}")
        sys.exit(result.returncode)

def main():
    base_dir = Path(__file__).resolve().parent.parent
    
    fetch_cmd = [
        sys.executable,
        str(base_dir / "cli.py"),
        "all",
        "--years", "112",
        "--deptids", "12",
        "--class-codes", "B",
        "--force",
        "--delay", "0.5",
        "--max-rounds", "20"
    ]
    
    validate_cmd = [
        sys.executable,
        str(base_dir / "cli.py"),
        "validate",
        "--probe"
    ]
    
    print("開始執行一鍵測試樣本 (112 入學年度 / 12 國企系 / B 學士班)...")
    run_command(fetch_cmd)
    run_command(validate_cmd)
    
    print("\n=== 測試完成 ===")
    
    expected_files = [
        "data/raw/112/12/B.html",
        "data/parsed/112/112-12-B.json",
        "data/indexes/curriculum_rules_index.json",
        "data/reports/fetch_summary.json",
        "data/reports/parse_summary.json",
        "data/reports/validation_summary.json"
    ]
    
    all_exist = True
    for f in expected_files:
        f_path = base_dir / f
        status = "[OK] 存在" if f_path.exists() else "[FAIL] 遺失"
        print(f"{status}: {f}")
        if not f_path.exists():
            all_exist = False
            
    if not all_exist:
        print("\n[WARN] 部分檔案未成功產生。")
        sys.exit(1)
        
    print("\n=== 深入檢查 JSON ===")
    
    # 檢查 parsed JSON
    parsed_json_path = base_dir / "data/parsed/112/112-12-B.json"
    try:
        with open(parsed_json_path, "r", encoding="utf-8") as f:
            parsed_data = json.load(f)
            assert parsed_data.get("requirementSetId") == "112-12-B", "requirementSetId 錯誤"
            groups = parsed_data.get("groups", [])
            assert len(groups) > 0, "沒有產生任何 group"
            
            group_names = [g["name"] for g in groups]
            assert len(set(group_names)) > 1, "所有 group name 都相同，標題解析失敗"
            
            assert any("必修課程清單" in name for name in group_names), "缺少必修課程清單"
            assert any("先修" in name or "擋修" in name for name in group_names), "缺少先修/擋修清單"
            assert any("校核心" in name or "通識" in name for name in group_names), "缺少校核心/通識 group"
            assert any("輔系" in name for name in group_names), "缺少輔系 group"
            assert any("雙主修" in name for name in group_names), "缺少雙主修 group"
            
            def find_group(groups_list, keyword):
                for grp in groups_list:
                    if keyword in grp.get("name", ""):
                        return grp
                return None

            major_required = find_group(groups, "學士班必修課程清單")
            assert major_required is not None
            assert major_required.get("requiredCredits") == 53
            
            minor = find_group(groups, "輔系必修")
            assert minor is not None
            assert minor.get("requiredCredits") == 18
            
            double_major = find_group(groups, "雙主修必修")
            assert double_major is not None
            assert double_major.get("requiredCredits") == 41
            
            core_minimum = find_group(groups, "最低學分數")
            assert core_minimum is not None
            assert core_minimum.get("requiredCredits") == 31
            
            core_required = find_group(groups, "校核心必修")
            assert core_required is not None
            assert core_required.get("requiredCredits") == 2
            
            prereq = find_group(groups, "先修")
            assert prereq is not None
            assert prereq.get("type") == "prerequisite_rules"
            assert len(prereq.get("rules", [])) > 0
            assert len(prereq.get("courses", [])) == 0

            valid_group = False
            for g in groups:
                if len(g.get("courses", [])) > 0 or len(g.get("rules", [])) > 0 or len(g.get("originalRows", [])) > 0:
                    valid_group = True
                    break
            assert valid_group, "至少一個 group 要有 courses, rules 或 originalRows"
        print("[OK] parsed JSON 驗證通過")
    except Exception as e:
        print(f"[FAIL] parsed JSON 驗證失敗: {e}")
        sys.exit(1)
        
    # 檢查 index
    index_path = base_dir / "data/indexes/curriculum_rules_index.json"
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index_data = json.load(f)
            items = index_data.get("items", [])
            assert any(i.get("requirementSetId") == "112-12-B" for i in items), "index 內未找到 112-12-B"
        print("[OK] index 驗證通過")
    except Exception as e:
        print(f"[FAIL] index 驗證失敗: {e}")
        sys.exit(1)
        
    # 檢查 fetch_summary
    fetch_path = base_dir / "data/reports/fetch_summary.json"
    try:
        with open(fetch_path, "r", encoding="utf-8") as f:
            fetch_data = json.load(f)
            assert fetch_data.get("success", 0) >= 1, "fetch_summary 成功數小於 1"
        print("[OK] fetch_summary 驗證通過")
    except Exception as e:
        print(f"[FAIL] fetch_summary 驗證失敗: {e}")
        sys.exit(1)
        
    # 檢查 validation_summary
    validate_path = base_dir / "data/reports/validation_summary.json"
    try:
        with open(validate_path, "r", encoding="utf-8") as f:
            validate_data = json.load(f)
            assert validate_data.get("passed") == True, "validation_summary passed != true"
        print("[OK] validation_summary 驗證通過")
    except Exception as e:
        print(f"[FAIL] validation_summary 驗證失敗: {e}")
        sys.exit(1)

    print("\n[SUCCESS] 第一階段驗收條件全部達成！")

if __name__ == "__main__":
    main()
