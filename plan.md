# 暨大修業規則爬蟲測試小專案實作計畫

## 任務目標

建立一個獨立 Python 小專案，用來測試是否可以從暨大修業規則查詢網站批次抓取所有系所、所有部別、所有指定入學年度的修業規則，並轉換成結構化 JSON。

這個小專案只做資料抓取與解析驗證，不要整合到既有 NCNU Super Assistant 專案，也不要建立 GitHub Action workflow。

---

## 已知資料來源

### 1. 開課單位代碼 API

用來取得所有 `deptid`。

```text
https://api.ncnu.edu.tw/API/get.aspx?json=course_deptId
```

API 回傳資料中，每個單位有：

```json
{
  "開課單位代碼": "12",
  "單位中文名稱": "國際企業學系",
  "單位英文名稱": "International Business Studies",
  "單位中文簡稱": "國企系"
}
```

### 2. 修業規則 detail 頁

URL 格式：

```text
https://ccweb6.ncnu.edu.tw/student/aspmaker_dept_student_graduation_requirements_M_viewview.php?showdetail=&deptid=<deptid>&class_code=<class_code>&entry_year=<entry_year>
```

參數定義：

| 參數         | 意義         |
| ------------ | ------------ |
| `deptid`     | 開課單位代碼 |
| `class_code` | 部別代碼     |
| `entry_year` | 入學年度     |

`class_code` 對照：

| 代碼 | 部別   |
| ---- | ------ |
| `B`  | 學士班 |
| `G`  | 碩士班 |
| `P`  | 博士班 |

測試樣本：

```text
https://ccweb6.ncnu.edu.tw/student/aspmaker_dept_student_graduation_requirements_M_viewview.php?showdetail=&deptid=12&class_code=B&entry_year=112
```

這筆代表：

```text
國際企業學系 / 學士班 / 112 入學年度
```

---

## 小專案目標

請建立一個新的獨立專案，例如：

```text
ncnu-graduation-requirements-probe/
```

這個專案要能做到：

1. 取得所有開課單位代碼。
2. 依照指定入學年度、部別、系所代碼組合產生 detail URL。
3. 批次抓取修業規則 HTML。
4. 保存 raw HTML。
5. 將 HTML 解析成 JSON。
6. 產生索引檔。
7. 產生抓取報告與解析報告。
8. 提供 CLI 可測試單筆、指定多筆、或全量抓取。

---

## 建議專案結構

```text
ncnu-graduation-requirements-probe/
  README.md
  requirements.txt
  .gitignore

  scripts/
    fetch_requirements.py
    parse_requirements.py
    validate_requirements.py
    run_probe.py

  src/
    ncnu_graduation/
      __init__.py
      config.py
      dept_api.py
      fetcher.py
      parser.py
      normalizer.py
      storage.py
      validator.py

  data/
    raw/
    parsed/
    indexes/
    reports/
```

---

## Python 套件需求

`requirements.txt`：

```text
requests
beautifulsoup4
lxml
tqdm
```

可選：

```text
pytest
```

---

## CLI 設計

### 1. 抓單筆資料

```bash
python scripts/fetch_requirements.py --years 112 --deptids 12 --class-codes B
```

### 2. 抓指定多筆

```bash
python scripts/fetch_requirements.py --years 112 113 114 --deptids 12 13 14 --class-codes B
```

### 3. 抓所有系所

```bash
python scripts/fetch_requirements.py --years 112 113 114 --all-depts --class-codes B G P
```

### 4. 強制重新抓取

```bash
python scripts/fetch_requirements.py --years 112 --deptids 12 --class-codes B --force
```

### 5. 解析已抓 HTML

```bash
python scripts/parse_requirements.py
```

### 6. 驗證資料

```bash
python scripts/validate_requirements.py
```

### 7. 一鍵測試樣本

```bash
python scripts/run_probe.py
```

`run_probe.py` 預設只測：

```text
entry_year=112
deptid=12
class_code=B
```

---

## 抓取腳本需求

實作 `scripts/fetch_requirements.py`。

### 功能

1. 呼叫開課單位代碼 API。
2. 取得所有 `deptid`。
3. 根據 CLI 參數決定要抓哪些組合。
4. 對每個組合產生 detail URL。
5. 使用 `requests.get()` 抓取 HTML。
6. 成功時保存 HTML。
7. 失敗時記錄錯誤。
8. 每次 request 之間加入 delay。

### CLI 參數

```text
--years
--deptids
--all-depts
--class-codes
--delay
--force
--timeout
```

預設值：

| 參數            | 預設  |
| --------------- | ----- |
| `--years`       | `112` |
| `--class-codes` | `B`   |
| `--delay`       | `0.5` |
| `--timeout`     | `20`  |
| `--force`       | false |

### 成功判斷

HTTP 狀態必須是 `200`。

HTML 內容至少要符合其中幾個條件：

```text
包含「查詢修業規則」
包含「必修課程」
包含 entry_year
包含 deptid 或系所名稱
```

若 HTML 內容明顯是錯誤頁、空白頁、登入頁，視為失敗。

### raw HTML 保存路徑

```text
data/raw/<entry_year>/<deptid>/<class_code>.html
```

範例：

```text
data/raw/112/12/B.html
```

### fetch summary

輸出：

```text
data/reports/fetch_summary.json
```

格式：

```json
{
  "generatedAt": "2026-06-22T00:00:00+08:00",
  "total": 1,
  "success": 1,
  "failed": 0,
  "skipped": 0
}
```

### fetch errors

輸出：

```text
data/reports/fetch_errors.json
```

格式：

```json
[
  {
    "entryYear": "112",
    "departmentId": "12",
    "classCode": "B",
    "url": "...",
    "statusCode": 500,
    "reason": "HTTP error"
  }
]
```

---

## HTML 解析腳本需求

實作 `scripts/parse_requirements.py`。

### 功能

1. 掃描 `data/raw/**/*.html`。
2. 從路徑取得：
   - `entryYear`
   - `departmentId`
   - `classCode`

3. 用 BeautifulSoup 解析 HTML。
4. 解析頁面中的基本資訊。
5. 解析頁面中的所有表格。
6. 盡量將課程資料轉成結構化 JSON。
7. 無法解析的文字要保留。
8. 輸出 parsed JSON。
9. 產生 index。

---

## JSON 輸出格式

每一筆 requirement set 輸出到：

```text
data/parsed/<entry_year>/<entry_year>-<deptid>-<class_code>.json
```

範例：

```text
data/parsed/112/112-12-B.json
```

格式：

```json
{
  "requirementSetId": "112-12-B",
  "source": "ccweb6_graduation_requirements",
  "entryYear": "112",
  "departmentId": "12",
  "departmentName": "國際企業學系",
  "departmentShortName": "國企系",
  "classCode": "B",
  "className": "學士班",
  "rawHtmlPath": "data/raw/112/12/B.html",
  "groups": [
    {
      "groupId": "group_001",
      "name": "必修課程清單",
      "type": "course_list",
      "requiredCredits": null,
      "courses": [
        {
          "courseId": "120001",
          "courseName": "經濟學及實習(上)",
          "credits": 3
        }
      ],
      "description": "",
      "originalRows": []
    }
  ],
  "notes": []
}
```

---

## 表格解析原則

detail 頁中可能有多個表格。請不要假設只有一個表格。

每個表格都要轉成一個 group。

### group name

優先取表格前方最近的文字標題，例如：

```text
必修課程清單
輔系必修課程清單
雙主修必修課程清單
通識課程
學分小計
```

如果找不到標題，用：

```text
group_001
group_002
```

### 課程欄位

盡量辨識：

| 欄位     | JSON         |
| -------- | ------------ |
| 課號     | `courseId`   |
| 科目代碼 | `courseId`   |
| 課程名稱 | `courseName` |
| 科目名稱 | `courseName` |
| 學分     | `credits`    |

若欄位名稱不同，請用模糊比對。

### 無法解析的列

如果某一列不像課程資料，不要丟掉，放進：

```json
"originalRows": []
```

### 備註文字

頁面上的規則說明、備註、限制條件，先保留在：

```json
"notes": []
```

或 group 的：

```json
"description": ""
```

第一版不要嘗試完整理解所有條件邏輯。

---

## index 輸出格式

解析完成後產生：

```text
data/indexes/curriculum_rules_index.json
```

格式：

```json
{
  "generatedAt": "2026-06-22T00:00:00+08:00",
  "source": "ccweb6_graduation_requirements",
  "items": [
    {
      "requirementSetId": "112-12-B",
      "entryYear": "112",
      "departmentId": "12",
      "departmentName": "國際企業學系",
      "departmentShortName": "國企系",
      "classCode": "B",
      "className": "學士班",
      "path": "data/parsed/112/112-12-B.json",
      "rawHtmlPath": "data/raw/112/12/B.html"
    }
  ]
}
```

---

## 驗證腳本需求

實作 `scripts/validate_requirements.py`。

### 檢查項目

1. `data/indexes/curriculum_rules_index.json` 存在。
2. index JSON 可以讀取。
3. 每個 item 的 parsed JSON 都存在。
4. `requirementSetId` 不重複。
5. 每個 parsed JSON 至少有：
   - `requirementSetId`
   - `entryYear`
   - `departmentId`
   - `classCode`
   - `groups`

6. 若存在 `112-12-B`，確認它至少有一個 group。
7. 輸出驗證報告。

### 驗證報告

```text
data/reports/validation_summary.json
```

---

## run_probe.py

實作一個一鍵測試腳本：

```bash
python scripts/run_probe.py
```

它應該自動執行：

```bash
python scripts/fetch_requirements.py --years 112 --deptids 12 --class-codes B --force
python scripts/parse_requirements.py
python scripts/validate_requirements.py
```

最後印出：

```text
raw HTML path
parsed JSON path
index path
fetch summary
validation summary
```

---

## README 內容

`README.md` 要包含：

1. 專案目的。
2. 資料來源。
3. URL 參數定義。
4. class_code 對照。
5. 安裝方式。
6. 單筆測試。
7. 批次抓取。
8. 解析 JSON。
9. 驗證資料。
10. 輸出資料夾說明。
11. 已知限制。

---

## 已知限制

第一版只要證明可行，不需要做到完整畢業審查。

不要在第一版做：

1. 前端 UI。
2. GitHub Action。
3. 資料庫。
4. 登入。
5. Supabase。
6. 與 NCNU Super Assistant 整合。
7. 完整抵免邏輯。
8. 完整通識規則推論。
9. 完整輔系 / 雙主修進度計算。

---

## 驗收標準

第一階段驗收：

```bash
python scripts/run_probe.py
```

必須成功產生：

```text
data/raw/112/12/B.html
data/parsed/112/112-12-B.json
data/indexes/curriculum_rules_index.json
data/reports/fetch_summary.json
data/reports/validation_summary.json
```

第二階段驗收：

```bash
python scripts/fetch_requirements.py --years 112 --deptids 12 --class-codes B G P --force
python scripts/parse_requirements.py
python scripts/validate_requirements.py
```

第三階段驗收：

```bash
python scripts/fetch_requirements.py --years 112 113 114 --all-depts --class-codes B G P
python scripts/parse_requirements.py
python scripts/validate_requirements.py
```

如果第三階段能成功產生多數系所、多數部別、多數年度的 JSON，就代表此資料來源可行，後續再把 crawler、parser、data schema 併入 NCNU Super Assistant。
