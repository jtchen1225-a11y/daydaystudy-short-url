# DayDayStudy Short URL Manager V3 升級說明

V3 的核心功能是「一鍵 Publish」。日常不再需要手動輸入：

```bash
python build.py
git add links.csv
git commit -m "..."
git push
```

管理頁會依次完成：

1. 儲存 `links.csv`
2. 執行 `build.py` 驗證
3. 只 `git add links.csv`
4. 如有變更，自動建立 commit
5. `git push origin <目前分支>`
6. 查詢 GitHub Actions 狀態，直到完成或逾時

## 安全設計

Publish **只會提交 `links.csv`**。即使本機同時修改了 `manager.py`、`README.md` 或其他檔案，也不會被一鍵 Publish 意外 commit。

## 安裝

把本升級包解壓並覆蓋到現有專案根目錄：

```text
daydaystudy-short-url/
├── manager.py
└── manager/
    ├── index.html
    ├── app.js
    └── style.css
```

本升級包不包含 `links.csv`，不會覆蓋既有短網址。

第一次完成 V3 升級後，要手動把 V3 程式碼 commit 一次：

```bash
git add manager.py manager UPGRADE_V3.md
git commit -m "Upgrade short URL manager to V3 publish"
git push
```

之後日常新增/修改短網址，直接使用管理頁的「儲存並 Publish」即可。

## 啟動

```bash
cd ~/projects/daydaystudy-short-url
source .venv/bin/activate
python manager.py
```

瀏覽器：

```text
http://127.0.0.1:8787
```

## GitHub Actions 狀態

V3 透過 GitHub 公開 API 讀取 public repository 的 Actions 狀態，不需要新增 GitHub Token。若網路暫時無法連到 GitHub API，Publish/Push 仍可成功，只是管理頁可能暫時顯示「無法取得部署狀態」。

## Git 認證

一鍵 Publish 使用你電腦現有的 `git push` 認證方式。因此只要你在同一個 WSL 專案裡原本可以手動 `git push`，V3 通常就可以直接使用。
