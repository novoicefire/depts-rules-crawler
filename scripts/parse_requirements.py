import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ncnu_graduation.dept_api import fetch_all_departments
from ncnu_graduation.parser import parse_html_to_json
from ncnu_graduation.storage import save_parsed_json, save_index, save_report
from ncnu_graduation.config import RAW_DIR, CLASS_CODES
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.console import Console

console = Console()

def run_parse(args=None):
    with console.status("[bold cyan]正在取得系所清單以建立名稱對照...[/bold cyan]"):
        try:
            all_depts = fetch_all_departments()
            dept_map = {d["開課單位代碼"]: d for d in all_depts}
        except Exception as e:
            console.print(f"[bold yellow]警告: 取得系所清單失敗，將缺少系所名稱對照 ({e})[/bold yellow]")
            dept_map = {}
    
    raw_files = sorted(RAW_DIR.rglob("*.html"))
    if not raw_files:
        console.print("[bold yellow]找不到任何 HTML 檔案，請先執行 fetch。[/bold yellow]")
        sys.exit(1)
        
    console.print(f"[bold green]找到 {len(raw_files)} 個 HTML 檔案待解析[/bold green]")
    
    parse_summary = {
        "generatedAt": datetime.now().isoformat(),
        "total": len(raw_files),
        "success": 0,
        "failed": 0
    }
    
    parse_errors = []
    index_items = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task_id = progress.add_task("[cyan]解析 HTML 中...", total=len(raw_files))
        
        for path in raw_files:
            parts = path.parts
            if len(parts) < 3:
                continue
            
            entry_year = parts[-3]
            deptid = parts[-2]
            class_code = parts[-1].replace(".html", "")
        
            dept_info = dict(dept_map.get(deptid, {}))
            dept_info["className"] = CLASS_CODES.get(class_code, "")
        
            rel_path = path.relative_to(Path(__file__).resolve().parent.parent).as_posix()
        
            with open(path, "r", encoding="utf-8") as f:
                html_content = f.read()
                try:
                    parsed_data = parse_html_to_json(
                        html_content=html_content,
                        entry_year=entry_year,
                        deptid=deptid,
                        class_code=class_code,
                        dept_info=dept_info,
                        raw_html_path=rel_path
                    )
                
                    out_path = save_parsed_json(entry_year, deptid, class_code, parsed_data)
                    out_rel_path = out_path.relative_to(Path(__file__).resolve().parent.parent).as_posix()
                
                    index_items.append({
                        "requirementSetId": f"{entry_year}-{deptid}-{class_code}",
                        "entryYear": entry_year,
                        "departmentId": deptid,
                        "departmentName": parsed_data["departmentName"],
                        "departmentShortName": parsed_data["departmentShortName"],
                        "classCode": class_code,
                        "className": parsed_data["className"],
                        "path": out_rel_path,
                        "rawHtmlPath": rel_path
                    })
                    parse_summary["success"] += 1
                    progress.console.print(f"[dim]已解析:[/dim] {entry_year}-{deptid}-{class_code}")
                
                except Exception as e:
                    parse_summary["failed"] += 1
                    parse_errors.append({
                        "rawHtmlPath": str(path),
                        "entryYear": entry_year,
                        "departmentId": deptid,
                        "classCode": class_code,
                        "error": str(e)
                    })
                    progress.console.print(f"[bold red]解析失敗 {path}: {e}[/bold red]")
                
                progress.update(task_id, advance=1)
            
    index_items = sorted(
        index_items,
        key=lambda x: (x["entryYear"], x["departmentId"], x["classCode"])
    )
            
    index_data = {
        "generatedAt": datetime.now().isoformat(),
        "source": "ccweb6_graduation_requirements",
        "items": index_items
    }
    save_index(index_data)
    save_report("parse_summary", parse_summary)
    save_report("parse_errors", parse_errors)
    console.print("[bold green]解析完成！索引檔與報告已更新。[/bold green]")

if __name__ == "__main__":
    run_parse()
