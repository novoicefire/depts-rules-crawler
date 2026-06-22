import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd_list):
    print(f"\n> 執行: {' '.join(cmd_list)}")
    # Use default encoding by not specifying encoding="utf-8"
    result = subprocess.run(cmd_list, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        print(f"[FAIL] 命令執行失敗，回傳碼: {result.returncode}")
        sys.exit(result.returncode)

def main():
    base_dir = Path(__file__).resolve().parent.parent
    
    fetch_cmd = [
        sys.executable,
        str(base_dir / "scripts" / "fetch_requirements.py"),
        "--years", "112",
        "--deptids", "12",
        "--class-codes", "B",
        "--force"
    ]
    
    parse_cmd = [
        sys.executable,
        str(base_dir / "scripts" / "parse_requirements.py")
    ]
    
    validate_cmd = [
        sys.executable,
        str(base_dir / "scripts" / "validate_requirements.py")
    ]
    
    print("開始執行一鍵測試樣本 (112 入學年度 / 12 國企系 / B 學士班)...")
    run_command(fetch_cmd)
    run_command(parse_cmd)
    run_command(validate_cmd)
    
    print("\n=== 測試完成 ===")
    
    expected_files = [
        "data/raw/112/12/B.html",
        "data/parsed/112/112-12-B.json",
        "data/indexes/curriculum_rules_index.json",
        "data/reports/fetch_summary.json",
        "data/reports/validation_summary.json"
    ]
    
    all_exist = True
    for f in expected_files:
        f_path = base_dir / f
        status = "[OK] 存在" if f_path.exists() else "[FAIL] 遺失"
        print(f"{status}: {f}")
        if not f_path.exists():
            all_exist = False
            
    if all_exist:
        print("\n[SUCCESS] 第一階段驗收條件全部達成！")
    else:
        print("\n[WARN] 部分檔案未成功產生。")

if __name__ == "__main__":
    main()
