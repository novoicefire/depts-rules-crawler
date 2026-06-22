import sys
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ncnu_graduation.validator import validate_all
from ncnu_graduation.storage import save_report
from rich.console import Console
from rich.panel import Panel

console = Console()

def run_validate(args=None):
    with console.status("[bold cyan]開始驗證解析結果...[/bold cyan]"):
        report = validate_all()
    
    # 加上生成時間
    report["generatedAt"] = datetime.now().isoformat()
    
    save_report("validation_summary", report)
    
    report_json = json.dumps(report, ensure_ascii=False, indent=2)
    console.print(Panel(report_json, title="[bold]驗證報告[/bold]", border_style="cyan"))
    
    if report.get("passed"):
        console.print("[bold green][OK] 驗證成功！所有資料格式皆符合要求。[/bold green]")
        return True
    else:
        console.print("[bold red][FAIL] 驗證失敗，請查看上方報告細節。[/bold red]")
        return False

if __name__ == "__main__":
    if not run_validate():
        sys.exit(1)
