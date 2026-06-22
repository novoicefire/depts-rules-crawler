import argparse
import sys
import time
from pathlib import Path
from datetime import datetime
import concurrent.futures
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ncnu_graduation.dept_api import fetch_all_departments
from ncnu_graduation.fetcher import fetch_requirements_html, get_detail_url, fetch_available_combinations
from ncnu_graduation.storage import save_raw_html, save_report
from ncnu_graduation.config import CLASS_CODES, RAW_DIR
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.console import Console
from rich import print as rprint

console = Console()

def fetch_with_delay(year, deptid, class_code, timeout, delay):
    if delay and delay > 0:
        time.sleep(delay)
    return fetch_requirements_html(year, deptid, class_code, timeout)

def run_fetch(args):
    if not args.deptids and not args.all_depts:
        console.print("[bold red]錯誤: 必須指定 --deptids 或使用 --all-depts[/bold red]")
        sys.exit(1)
        
    target_deptids = []
    if not args.all_depts:
        if args.deptids:
            target_deptids = args.deptids
        else:
            with console.status("[bold cyan]正在取得系所清單...[/bold cyan]"):
                all_depts = fetch_all_departments()
                target_deptids = [d["開課單位代碼"] for d in all_depts]
    
    summary: Dict[str, Any] = {
        "generatedAt": datetime.now().isoformat(),
        "startedAt": datetime.now().isoformat(),
        "finishedAt": None,
        "durationSeconds": None,
        "years": args.years,
        "classCodes": args.class_codes,
        "allDepts": getattr(args, "all_depts", False),
        "deptids": getattr(args, "deptids", None),
        "workers": getattr(args, "workers", 5),
        "maxRounds": getattr(args, "max_rounds", 20),
        "delay": getattr(args, "delay", 0.5),
        "total": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "successRate": 0,
        "rounds": []
    }
    
    errors = []
    
    tasks = []
    for year in args.years:
        if args.all_depts:
            with console.status(f"[bold cyan]正在取得 {year} 年度的實際有效系所與部別清單...[/bold cyan]"):
                valid_combinations = fetch_available_combinations(year)
                
            if not valid_combinations:
                errors.append({
                    "entryYear": year,
                    "reason": "No available combinations found from list page"
                })
                summary["finishedAt"] = datetime.now().isoformat()
                save_report("fetch_errors", errors)
                save_report("fetch_summary", summary)
                console.print("[bold red]錯誤：all-depts 模式下沒有解析到任何有效組合。[/bold red]")
                sys.exit(1)
                
            for deptid, class_code in valid_combinations:
                if class_code in args.class_codes and class_code in CLASS_CODES:
                    tasks.append((year, deptid, class_code))
        else:
            for deptid in target_deptids:
                for class_code in args.class_codes:
                    if class_code in CLASS_CODES:
                        tasks.append((year, deptid, class_code))
                    
    summary["total"] = len(tasks)
    
    if summary["total"] == 0:
        summary["failed"] = 0
        summary["finishedAt"] = datetime.now().isoformat()
        save_report("fetch_summary", summary)
        console.print("[bold red]錯誤：沒有任何抓取任務。請檢查 years、deptids、class-codes。[/bold red]")
        sys.exit(1)
        
    console.print(f"[bold green]預計執行 {summary['total']} 筆抓取任務...[/bold green]")
    
    pending_tasks = tasks.copy()
    round_num = 1
    
    while pending_tasks and round_num <= args.max_rounds:
        console.print(f"\n[bold magenta]--- 第 {round_num} 回合開始 ---[/bold magenta]")
        console.print(f"本回合預計處理 [bold yellow]{len(pending_tasks)}[/bold yellow] 筆任務...")
        
        current_round_tasks = pending_tasks.copy()
        pending_tasks = []
        
        round_summary = {
            "round": round_num,
            "input": len(current_round_tasks),
            "success": 0,
            "failed": 0,
            "skipped": 0
        }
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task_id = progress.add_task(f"[cyan]回合 {round_num} 抓取中...", total=len(current_round_tasks))
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
                future_to_task = {}
                for year, deptid, class_code in current_round_tasks:
                    target_path = RAW_DIR / str(year) / str(deptid) / f"{class_code}.html"
                    if target_path.exists() and not args.force:
                        progress.console.print(f"[dim][SKIP] 檔案已存在: {target_path}[/dim]")
                        summary["skipped"] += 1
                        round_summary["skipped"] += 1
                        progress.update(task_id, advance=1)
                        continue
                        
                    url = get_detail_url(year, deptid, class_code)
                    future = executor.submit(fetch_with_delay, year, deptid, class_code, args.timeout, getattr(args, "delay", 0.5))
                    future_to_task[future] = (year, deptid, class_code, url)
                    
                for future in concurrent.futures.as_completed(future_to_task):
                    year, deptid, class_code, url = future_to_task[future]
                    prefix = f"[FETCH] {year}-{deptid}-{class_code}"
                    
                    try:
                        status_code, html = future.result()
                        if html:
                            save_raw_html(year, deptid, class_code, html)
                            summary["success"] += 1
                            round_summary["success"] += 1
                            progress.console.print(f"{prefix} -> [bold green]成功[/bold green]")
                        elif html == "":
                            summary["skipped"] += 1
                            round_summary["skipped"] += 1
                            progress.console.print(f"{prefix} -> [yellow]無效頁面或查無資料 (跳過)[/yellow]")
                        else:
                            progress.console.print(f"{prefix} -> [bold red]失敗 (Status: {status_code})[/bold red]")
                            round_summary["failed"] += 1
                            pending_tasks.append((year, deptid, class_code))
                    except Exception as exc:
                        progress.console.print(f"{prefix} -> [bold red]執行例外: {exc}[/bold red]")
                        round_summary["failed"] += 1
                        pending_tasks.append((year, deptid, class_code))
                    
                    progress.update(task_id, advance=1)
                    
        summary["rounds"].append(round_summary)
        
        if pending_tasks:
            wait_seconds = min(2 * round_num, 30)
            console.print(f"[yellow]第 {round_num} 回合結束，還有 {len(pending_tasks)} 筆任務失敗，準備進入下一回合，等待 {wait_seconds} 秒...[/yellow]")
            time.sleep(wait_seconds)
            
        round_num += 1
        
    if pending_tasks:
        console.print(f"\n[bold red]警告: 已達到最大重試次數 ({args.max_rounds})，但仍有 {len(pending_tasks)} 筆失敗。[/bold red]")
        for year, deptid, class_code in pending_tasks:
            url = get_detail_url(year, deptid, class_code)
            summary["failed"] += 1
            errors.append({
                "entryYear": year,
                "departmentId": deptid,
                "classCode": class_code,
                "url": url,
                "statusCode": 500,
                "reason": "Max retries reached"
            })
            
    summary["finishedAt"] = datetime.now().isoformat()
    started_at_dt = datetime.fromisoformat(summary["startedAt"])
    finished_at_dt = datetime.fromisoformat(summary["finishedAt"])
    summary["durationSeconds"] = (finished_at_dt - started_at_dt).total_seconds()
    summary["successRate"] = summary["success"] / summary["total"] if summary["total"] else 0
            
    save_report("fetch_summary", summary)
    save_report("fetch_errors", errors)
    console.print("[bold green]抓取任務完成！報告已儲存於 data/reports。[/bold green]")
    
    if summary["failed"] > 0:
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="抓取暨大修業規則 HTML")
    parser.add_argument("--years", nargs="+", default=["112"], help="入學年度列表")
    parser.add_argument("--deptids", nargs="+", help="開課單位代碼列表")
    parser.add_argument("--all-depts", action="store_true", help="是否抓取所有系所")
    parser.add_argument("--class-codes", nargs="+", default=["B"], help="部別代碼列表")
    parser.add_argument("--workers", type=int, default=5, help="同時執行的執行緒數量")
    parser.add_argument("--max-rounds", type=int, default=20, help="最多重試的回合數")
    parser.add_argument("--timeout", type=int, default=20, help="請求逾時時間(秒)")
    parser.add_argument("--force", action="store_true", help="強制重新抓取已存在的檔案")
    parser.add_argument("--delay", type=float, default=0.5, help="每次請求前的延遲秒數")
    args = parser.parse_args()
    run_fetch(args)
