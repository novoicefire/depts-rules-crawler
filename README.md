# 暨大修業規則爬蟲測試小專案

## 專案目的
建立一個獨立的 Python 環境，用來測試是否可以從暨大修業規則查詢網站批次抓取所有系所、所有部別、所有指定入學年度的修業規則，並轉換成結構化 JSON。

此專案僅做資料抓取與解析驗證，不整合至既有專案，也不建立 CI/CD。

## 系統特色
- **突破 WAF 防火牆**：模擬真實瀏覽器 `User-Agent`，完美避開學校伺服器的防爬蟲阻擋。
- **高併發多執行緒**：採用 `ThreadPoolExecutor` 平行抓取，極大化下載速度。
- **無敵重試迴圈**：針對學校伺服器頻繁的 `500` 錯誤或 `Timeout`，設計了高達 20 次的列表獲取重試與 10 回合的自動失敗重入列機制，確保檔案 100% 完整抓取。
- **高級語意解析器 (Semantic Parser)**：自動逆向爬疏 DOM 樹找尋標題，精準區分 `必修`、`擋修`、`通識核心`、`輔系` 等特殊規定，支援多維度（4 欄 / 5 欄）的複雜表格提取。
- **統一 CLI 介面與進度視覺化**：整合所有腳本至 `cli.py`，搭配 `rich` 提供專業的進度條與色彩終端機輸出。

## 資料來源
1. **開課單位代碼 API** (用來取得所有 `deptid`)
   `https://api.ncnu.edu.tw/API/get.aspx?json=course_deptId`
2. **修業規則 detail 頁**
   `https://ccweb6.ncnu.edu.tw/student/aspmaker_dept_student_graduation_requirements_M_viewview.php?showdetail=&deptid=<deptid>&class_code=<class_code>&entry_year=<entry_year>`

### URL 參數定義
| 參數         | 意義         |
| ------------ | ------------ |
| `deptid`     | 開課單位代碼 |
| `class_code` | 部別代碼     |
| `entry_year` | 入學年度     |

### class_code 對照
| 代碼 | 部別   |
| ---- | ------ |
| `B`  | 學士班 |
| `G`  | 碩士班 |
| `P`  | 博士班 |

## 安裝方式
```bash
python -m venv venv
# 啟用 venv
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

## 使用方式

所有功能都已統一整合至 `cli.py`。請在專案根目錄執行：

```bash
python cli.py --help
```

### 1. 抓取資料 (Fetch)
單筆測試：
```bash
python cli.py fetch --years 112 --deptids 12 --class-codes B
```

抓取所有系所（背景執行建議）：
```bash
python cli.py fetch --years 112 --all-depts --class-codes B G P --workers 5 --max-rounds 20
```
- `--workers`: 多執行緒的數量，預設為 5。
- `--max-rounds`: 失敗項目的自動重試回合數，預設為 10 圈。

### 2. 解析 JSON (Parse)
將已下載在 `data/raw/` 的 HTML 解析成具備語意標記的結構化 JSON 並建立索引檔：
```bash
python cli.py parse
```

### 3. 驗證資料 (Validate)
驗證解析後的 JSON 格式正確性是否符合 Schema 要求：
```bash
python cli.py validate
```

### 4. 一鍵執行 (All)
依序自動執行 Fetch -> Parse -> Validate 完整流程：
```bash
python cli.py all --years 112 --deptids 12 --class-codes B
```

## 輸出資料夾說明
- `data/raw/`: 存放從網站抓下來的原始 HTML 檔案。
- `data/parsed/`: 存放解析後的 JSON 檔案。
- `data/indexes/`: 存放所有解析結果的總索引檔 (`curriculum_rules_index.json`)。
- `data/reports/`: 存放抓取報告與驗證報告 (`fetch_summary.json`, `fetch_errors.json`, `validation_summary.json`)。

## 已知限制
- 這是測試版本，旨在證明爬蟲與基礎解析邏輯可行，未進行複雜的前端 UI 或資料庫對接。
- 表格解析採用 heuristic 方法，若遇到格式不標準的表格（如跨領域合併的通識表格）會將欄位放進 `originalRows` 陣列中保留以確保資料零遺漏。
- 完整的抵免邏輯、通識規則推論等功能不在本專案實作範圍內。
