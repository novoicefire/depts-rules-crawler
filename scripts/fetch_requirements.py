import argparse
import sys
import time
import threading
from pathlib import Path
from datetime import datetime
import concurrent.futures
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ncnu_graduation.dept_api import fetch_all_departments
from ncnu_graduation.fetcher import fetch_requirements_html, get_detail_url, fetch_available_combinations, create_session
from ncnu_graduation.storage import save_raw_html, save_report
from ncnu_graduation.config import CLASS_CODES, RAW_DIR
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.console import Console
from rich import print as rprint

console = Console()

def should_retry_fetch(args, status_code, reason, html):
    if reason in {"timeout", "connection_error"}:
        return True

    if isinstance(reason, str) and reason.startswith("http_error_"):
        return True

    if isinstance(reason, str) and reason.startswith("request_exception"):
        return True

    if status_code is None:
        return True

    if isinstance(status_code, int) and status_code >= 500:
        return True

    if getattr(args, "all_depts", False):
        return True

    return False

class SessionPool:
    """
    requests.Session is not thread-safe.
    Use one session per worker thread to reuse connections without sharing mutable session state across threads.
    A new SessionPool should be created for each retry round.
    """
    def __init__(self):
        self.local = threading.local()
        
    def get_session(self):
        if not hasattr(self.local, "session"):
            self.local.session = create_session()
        return self.local.session

def fetch_with_delay(year, deptid, class_code, timeout, delay, session_pool):
    if delay and delay > 0:
        time.sleep(delay)
    session = session_pool.get_session()
    return fetch_requirements_html(year, deptid, class_code, timeout, session)

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
        "emptyRequirements": 0,
        "attemptWarnings": 0,
        "successRate": 0,
        "rounds": [],
        "byYear": {}
    }
    
    errors = []
    attempt_warnings = []
    
    for year in args.years:
        run_fetch_for_year(year, args, target_deptids, summary, errors, attempt_warnings)
        
    summary["finishedAt"] = datetime.now().isoformat()
    started_at_dt = datetime.fromisoformat(summary["startedAt"])
    finished_at_dt = datetime.fromisoformat(summary["finishedAt"])
    summary["durationSeconds"] = (finished_at_dt - started_at_dt).total_seconds()
    summary["successRate"] = summary["success"] / summary["total"] if summary["total"] else 0
            
    save_report("fetch_summary", summary)
    save_report("fetch_errors", errors)
    save_report("fetch_attempt_warnings", attempt_warnings)
    console.print("[bold green]抓取任務完成！報告已儲存於 data/reports。[/bold green]")
    
    if summary["failed"] > 0:
        sys.exit(1)

def run_fetch_for_year(year: str, args, target_deptids, summary: dict, errors: list, attempt_warnings: list):
    console.print(f"\n[bold blue]=== 開始處理 {year} 年度 ===[/bold blue]")
    
    tasks = []
    if args.all_depts:
        list_session = create_session()
        with console.status(f"[bold cyan]正在取得 {year} 年度的實際有效系所與部別清單...[/bold cyan]"):
            valid_combinations = fetch_available_combinations(year, session=list_session)
            
        if not valid_combinations:
            errors.append({
                "entryYear": year,
                "reason": "No available combinations found from list page"
            })
            console.print(f"[bold red]錯誤：all-depts 模式下沒有解析到 {year} 年度的任何有效組合。[/bold red]")
            summary["byYear"][year] = {"total": 0, "success": 0, "failed": 0, "skipped": 0, "emptyRequirements": 0, "attemptWarnings": 0, "rounds": []}
            summary["failed"] += 1
            return
            
        for deptid, class_code in valid_combinations:
            if class_code in args.class_codes and class_code in CLASS_CODES:
                tasks.append((year, deptid, class_code))
    else:
        for deptid in target_deptids:
            for class_code in args.class_codes:
                if class_code in CLASS_CODES:
                    tasks.append((year, deptid, class_code))
                    
    year_summary = {
        "total": len(tasks),
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "emptyRequirements": 0,
        "attemptWarnings": 0,
        "invalidHtml": 0,
        "requestErrors": 0,
        "rounds": []
    }
    summary["byYear"][year] = year_summary
    summary["total"] += len(tasks)
    
    if year_summary["total"] == 0:
        console.print(f"[bold yellow]警告：{year} 年度沒有任何抓取任務。[/bold yellow]")
        return
        
    console.print(f"[bold green]{year} 年度預計執行 {year_summary['total']} 筆抓取任務...[/bold green]")
    
    pending_tasks = tasks.copy()
    round_num = 1
    
    invalid_samples_dir = Path("data/reports/invalid_samples")
    invalid_samples_dir.mkdir(parents=True, exist_ok=True)
    
    while pending_tasks and round_num <= args.max_rounds:
        console.print(f"\n[bold magenta]--- {year} 年度 第 {round_num} 回合開始 ---[/bold magenta]")
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
        
        session_pool = SessionPool()
        
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
                for _, deptid, class_code in current_round_tasks:
                    target_path = RAW_DIR / str(year) / str(deptid) / f"{class_code}.html"
                    if target_path.exists() and not args.force:
                        progress.console.print(f"[dim][SKIP] 檔案已存在: {target_path}[/dim]")
                        summary["skipped"] += 1
                        year_summary["skipped"] += 1
                        round_summary["skipped"] += 1
                        progress.update(task_id, advance=1)
                        continue
                        
                    url = get_detail_url(year, deptid, class_code)
                    future = executor.submit(fetch_with_delay, year, deptid, class_code, args.timeout, getattr(args, "delay", 0.5), session_pool)
                    future_to_task[future] = (year, deptid, class_code, url)
                    
                for future in concurrent.futures.as_completed(future_to_task):
                    _, deptid, class_code, url = future_to_task[future]
                    prefix = f"[FETCH] {year}-{deptid}-{class_code}"
                    
                    try:
                        status_code, html, is_valid, reason = future.result()
                        if is_valid:
                            save_raw_html(year, deptid, class_code, html)
                            summary["success"] += 1
                            year_summary["success"] += 1
                            round_summary["success"] += 1
                            
                            if reason == "valid_empty_requirements":
                                summary["emptyRequirements"] += 1
                                year_summary["emptyRequirements"] += 1
                                progress.console.print(f"{prefix} -> [bold blue]成功 (空規則頁面)[/bold blue]")
                            else:
                                progress.console.print(f"{prefix} -> [bold green]成功[/bold green]")
                        else:
                            summary["attemptWarnings"] += 1
                            year_summary["attemptWarnings"] += 1
                            
                            if status_code == 200 and html:
                                # HTML fetched but invalid
                                year_summary["invalidHtml"] += 1
                                sample_path = invalid_samples_dir / f"{year}-{deptid}-{class_code}.html"
                                with open(sample_path, "w", encoding="utf-8") as f:
                                    f.write(html)
                                attempt_warnings.append({
                                    "entryYear": year,
                                    "departmentId": deptid,
                                    "classCode": class_code,
                                    "reason": reason,
                                    "statusCode": status_code,
                                    "samplePath": str(sample_path),
                                    "round": round_num
                                })
                                progress.console.print(f"{prefix} -> [yellow]無效頁面: {reason}[/yellow]")
                            else:
                                year_summary["requestErrors"] += 1
                                attempt_warnings.append({
                                    "entryYear": year,
                                    "departmentId": deptid,
                                    "classCode": class_code,
                                    "reason": reason,
                                    "statusCode": status_code,
                                    "round": round_num
                                })
                                progress.console.print(f"{prefix} -> [bold red]請求失敗 (Status: {status_code}, Reason: {reason})[/bold red]")
                            
                            if should_retry_fetch(args, status_code, reason, html):
                                round_summary["failed"] += 1
                                pending_tasks.append((year, deptid, class_code))
                            else:
                                summary["skipped"] += 1
                                year_summary["skipped"] += 1
                                round_summary["skipped"] += 1
                                progress.console.print("  └─ [dim]已略過此組合[/dim]")
                    except Exception as exc:
                        summary["attemptWarnings"] += 1
                        year_summary["attemptWarnings"] += 1
                        year_summary["requestErrors"] += 1
                        attempt_warnings.append({
                            "entryYear": year,
                            "departmentId": deptid,
                            "classCode": class_code,
                            "reason": f"exception: {exc}",
                            "statusCode": 500,
                            "round": round_num
                        })
                        progress.console.print(f"{prefix} -> [bold red]執行例外: {exc}[/bold red]")
                        round_summary["failed"] += 1
                        pending_tasks.append((year, deptid, class_code))
                    
                    progress.update(task_id, advance=1)
                    
        year_summary["rounds"].append(round_summary)
        summary["rounds"].append({**round_summary, "year": year})
        
        if pending_tasks:
            wait_seconds = min(2 * round_num, 30)
            console.print(f"[yellow]第 {round_num} 回合結束，還有 {len(pending_tasks)} 筆任務失敗，準備進入下一回合，等待 {wait_seconds} 秒...[/yellow]")
            time.sleep(wait_seconds)
            
        round_num += 1
        
    if pending_tasks:
        console.print(f"\n[bold red]警告: {year} 年度已達到最大重試次數 ({args.max_rounds})，仍有 {len(pending_tasks)} 筆失敗。[/bold red]")
        for _, deptid, class_code in pending_tasks:
            url = get_detail_url(year, deptid, class_code)
            summary["failed"] += 1
            year_summary["failed"] += 1
            errors.append({
                "entryYear": year,
                "departmentId": deptid,
                "classCode": class_code,
                "url": url,
                "statusCode": 500,
                "reason": "Max retries reached"
            })

    # 年度失敗條件：在 all-depts 模式下，只要有 task 且成功數為 0
    if getattr(args, "all_depts", False):
        if year_summary["total"] > 0 and year_summary["success"] == 0:
            console.print(f"[bold red]{year} 年度抓取判定為失敗 (成功數為 0)。[/bold red]")
            summary["failed"] += 1
            errors.append({
                "entryYear": year,
                "reason": "year_success_zero",
                "total": year_summary["total"]
            })

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
