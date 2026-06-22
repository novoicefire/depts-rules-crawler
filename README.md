# 暨大修業規則爬蟲測試小專案

## 專案目的
建立一個獨立的 Python 環境，用來測試是否可以從暨大修業規則查詢網站批次抓取所有系所、所有部別、所有指定入學年度的修業規則，並轉換成結構化 JSON。

此專案僅做資料抓取與解析驗證，不整合至既有專案，也不建立 CI/CD。

## 系統特色
- 模擬一般瀏覽器請求標頭，提高公開頁面抓取穩定性。
- 支援失敗項目重新入列、重試回合、錯誤報告與續跑。
- 支援全量抓取與單筆 probe 測試。
- 表格解析採 heuristic 方法，會保留無法解析的原始列資料，方便後續人工檢查。
- 不保證所有年度、系所、部別皆可成功抓取或完整語意解析。

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
python cli.py fetch --years 112 --all-depts --class-codes B G P --workers 5 --max-rounds 20 --delay 0.5
```

本機測試可使用 workers=5。
若學校站點回應不穩，請降低 workers 或增加 delay。
未來若放入 GitHub Action，建議 workers=2 或 3，delay=1.0。
不要短時間重複 force 全量抓取。

- `--workers`: 多執行緒的數量，預設為 5。
- `--max-rounds`: 失敗項目的自動重試回合數，預設為 20 圈。
- `--delay`: 每次請求前的延遲秒數，預設為 0.5 秒。

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
python cli.py all --years 112 --deptids 12 --class-codes B --delay 0.5
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

## 固定驗收指令
您可以使用內建腳本 `python scripts/acceptance_test.py [probe|year_112|all_years|all]` 進行驗收，或是手動執行以下三組指令：

### 1. Probe 測試 (針對 112-12-B 進行單一測試與斷言)
```bash
python cli.py clean --yes
python scripts/run_probe.py
```

### 2. 單年度全系所測試 (112 年度)
```bash
python cli.py clean --yes
python cli.py all --years 112 --all-depts --class-codes B G P --workers 5 --max-rounds 20 --delay 0.5
python cli.py validate --strict
```

### 3. 多年度全系所測試 (111 ~ 114 年度)
```bash
python cli.py clean --yes
python cli.py all --years 111 112 113 114 --all-depts --class-codes B G P --workers 5 --max-rounds 20 --delay 0.5
python cli.py validate --strict
```
