import argparse
import sys
import shutil
from pathlib import Path

# Add src and scripts to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from fetch_requirements import run_fetch
from parse_requirements import run_parse
from validate_requirements import run_validate
from rich.console import Console
from rich.prompt import IntPrompt, Prompt, Confirm

console = Console()

def main():
    parser = argparse.ArgumentParser(
        description="暨大修業規則爬蟲與解析 CLI 工具",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用指令")
    
    # --- Fetch Command ---
    fetch_parser = subparsers.add_parser("fetch", help="抓取原始 HTML")
    fetch_parser.add_argument("--years", nargs="+", default=["112"], help="入學年度列表")
    fetch_parser.add_argument("--deptids", nargs="+", help="開課單位代碼列表")
    fetch_parser.add_argument("--all-depts", action="store_true", help="是否抓取所有系所")
    fetch_parser.add_argument("--class-codes", nargs="+", default=["B"], help="部別代碼列表 (B/G/P)")
    fetch_parser.add_argument("--workers", type=int, default=5, help="同時執行的執行緒數量")
    fetch_parser.add_argument("--max-rounds", type=int, default=20, help="最多重試的回合數")
    fetch_parser.add_argument("--timeout", type=int, default=20, help="請求逾時時間(秒)")
    fetch_parser.add_argument("--force", action="store_true", help="強制重新抓取已存在的檔案")
    fetch_parser.add_argument("--delay", type=float, default=0.5, help="每次請求前的延遲秒數")
    
    # --- Parse Command ---
    parse_parser = subparsers.add_parser("parse", help="將 HTML 解析為 JSON")
    
    # --- Validate Command ---
    validate_parser = subparsers.add_parser("validate", help="驗證解析後的 JSON 格式")
    validate_parser.add_argument("--probe", action="store_true", help="以 probe 模式驗證，要求 112-12-B 存在")
    validate_parser.add_argument("--strict", action="store_true", help="嚴格驗證 group 與課程資料結構")
    
    # --- Clean Command ---
    clean_parser = subparsers.add_parser("clean", help="清除所有已抓取與解析的舊資料")
    clean_parser.add_argument("--yes", action="store_true", help="不詢問確認，直接清除 data 目錄")
    
    # --- All Command ---
    all_parser = subparsers.add_parser("all", help="執行抓取、解析、驗證一條龍流程")
    all_parser.add_argument("--years", nargs="+", default=["112"], help="入學年度列表")
    all_parser.add_argument("--deptids", nargs="+", help="開課單位代碼列表")
    all_parser.add_argument("--all-depts", action="store_true", help="是否抓取所有系所")
    all_parser.add_argument("--class-codes", nargs="+", default=["B"], help="部別代碼列表 (B/G/P)")
    all_parser.add_argument("--workers", type=int, default=5, help="同時執行的執行緒數量")
    all_parser.add_argument("--max-rounds", type=int, default=20, help="最多重試的回合數")
    all_parser.add_argument("--timeout", type=int, default=20, help="請求逾時時間(秒)")
    all_parser.add_argument("--force", action="store_true", help="強制重新抓取已存在的檔案")
    all_parser.add_argument("--delay", type=float, default=0.5, help="每次請求前的延遲秒數")

    args = parser.parse_args()
    
    if args.command is None:
        console.print("[bold cyan]暨大修業規則爬蟲與解析 CLI 工具[/bold cyan]")
        console.print("1. [bold green]Fetch[/bold green]: 抓取原始 HTML")
        console.print("2. [bold yellow]Parse[/bold yellow]: 將 HTML 解析為 JSON")
        console.print("3. [bold blue]Validate[/bold blue]: 驗證解析後的 JSON 格式")
        console.print("4. [bold magenta]All[/bold magenta]: 執行抓取、解析、驗證一條龍流程")
        console.print("5. [bold red]Clean[/bold red]: 清除所有已抓取與解析的舊資料")
        console.print("0. [bold red]Exit[/bold red]: 離開")
        
        choice = IntPrompt.ask("請選擇要執行的功能", choices=["0", "1", "2", "3", "4", "5"], show_choices=False)
        
        if choice == 0:
            sys.exit(0)
            
        years = ["112"]
        deptids = None
        all_depts = False
        class_codes = ["B", "G", "P"]
        
        if choice in [1, 2, 3, 4]:
            console.print("\n[bold cyan]--- 設定執行參數 ---[/bold cyan]")
            # 讓使用者輸入年度
            year_input = Prompt.ask("請輸入入學年度 (多個年度請用空白分隔)", default="112")
            if year_input.strip():
                years = year_input.split()
                
            # 讓使用者輸入部別
            class_input = Prompt.ask("請輸入部別代碼 (B=學士, G=碩士, P=博士, 用空白分隔)", default="B G P")
            if class_input.strip():
                class_codes = class_input.split()
            
            # 讓使用者輸入系所
            dept_input = Prompt.ask("請輸入系所代碼 (留白代表抓取『全部系所』)", default="")
            if dept_input.strip() == "":
                deptids = None
                all_depts = True
                console.print(f"[dim]=> 將抓取全部系所的 {class_codes}[/dim]")
            else:
                deptids = dept_input.split()
                all_depts = False
                console.print(f"[dim]=> 將抓取系所: {deptids} 的 {class_codes}[/dim]")
                
            console.print("-" * 30 + "\n")
            
        # 建立預設參數
        default_args = argparse.Namespace(
            years=years,
            deptids=deptids,
            all_depts=all_depts,
            class_codes=class_codes,
            workers=5,
            max_rounds=20,
            timeout=20,
            force=False,
            delay=0.5
        )
        
        if choice == 1:
            run_fetch(default_args)
        elif choice == 2:
            run_parse(default_args)
        elif choice == 3:
            success = run_validate(default_args)
            if not success: sys.exit(1)
        elif choice == 4:
            console.print("[bold magenta]=== 階段 1: Fetch ===[/bold magenta]")
            run_fetch(default_args)
            console.print("\n[bold magenta]=== 階段 2: Parse ===[/bold magenta]")
            run_parse(default_args)
            console.print("\n[bold magenta]=== 階段 3: Validate ===[/bold magenta]")
            success = run_validate(default_args)
            if not success: sys.exit(1)
            console.print("\n[bold green]所有階段執行完畢！🎉[/bold green]")
        elif choice == 5:
            from ncnu_graduation.config import DATA_DIR
            if Confirm.ask(f"[bold red]確定要刪除 {DATA_DIR} 底下所有資料嗎？這將無法復原！[/bold red]"):
                if DATA_DIR.exists():
                    shutil.rmtree(DATA_DIR)
                    console.print(f"[bold green]已成功清除 {DATA_DIR}[/bold green]")
                else:
                    console.print("[bold yellow]沒有發現 data 目錄，無需清除。[/bold yellow]")
        return
        
    if args.command == "fetch":
        run_fetch(args)
    elif args.command == "parse":
        run_parse(args)
    elif args.command == "validate":
        success = run_validate(args)
        if not success:
            sys.exit(1)
    elif args.command == "all":
        console.print("[bold magenta]=== 階段 1: Fetch ===[/bold magenta]")
        run_fetch(args)
        console.print("\n[bold magenta]=== 階段 2: Parse ===[/bold magenta]")
        run_parse(args)
        console.print("\n[bold magenta]=== 階段 3: Validate ===[/bold magenta]")
        success = run_validate(args)
        if not success:
            sys.exit(1)
        console.print("\n[bold green]所有階段執行完畢！[/bold green]")
    elif args.command == "clean":
        from ncnu_graduation.config import DATA_DIR
        if getattr(args, "yes", False) or Confirm.ask(f"[bold red]確定要刪除 {DATA_DIR} 底下所有資料嗎？這將無法復原！[/bold red]"):
            if DATA_DIR.exists():
                shutil.rmtree(DATA_DIR)
                console.print(f"[bold green]已成功清除 {DATA_DIR}[/bold green]")
            else:
                console.print("[bold yellow]沒有發現 data 目錄，無需清除。[/bold yellow]")

if __name__ == "__main__":
    main()
