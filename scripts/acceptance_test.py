#!/usr/bin/env python3
"""
固定驗收指令腳本
可用於快速執行 depts-rules-crawler 的相關驗收測試。
"""

import subprocess
import sys
import argparse
from pathlib import Path

def run_cmd(cmd: str):
    print(f"\n[執行] {cmd}")
    # 確保以專案根目錄為執行位置
    project_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(cmd, shell=True, cwd=project_root)
    if result.returncode != 0:
        print(f"\n[錯誤] 指令執行失敗 (Return code: {result.returncode}): {cmd}")
        sys.exit(result.returncode)

TESTS = {
    "probe": [
        "python cli.py clean --yes",
        "python scripts/run_probe.py"
    ],
    "year_112": [
        "python cli.py clean --yes",
        "python cli.py all --years 112 --all-depts --class-codes B G P --workers 5 --max-rounds 20 --delay 0.5",
        "python cli.py validate --strict"
    ],
    "all_years": [
        "python cli.py clean --yes",
        "python cli.py all --years 111 112 113 114 --all-depts --class-codes B G P --workers 5 --max-rounds 20 --delay 0.5",
        "python cli.py validate --strict"
    ]
}

def main():
    parser = argparse.ArgumentParser(description="執行固定驗收指令")
    parser.add_argument(
        "test_name", 
        nargs="?", 
        choices=list(TESTS.keys()) + ["all"], 
        default="probe",
        help="選擇要執行的驗收測試 (預設: probe)"
    )
    args = parser.parse_args()

    tests_to_run = list(TESTS.keys()) if args.test_name == "all" else [args.test_name]

    for test in tests_to_run:
        print(f"\n========== 開始驗收測試: {test} ==========")
        for cmd in TESTS[test]:
            run_cmd(cmd)
        print(f"\n========== 驗收測試完成: {test} ==========\n")

if __name__ == "__main__":
    main()
