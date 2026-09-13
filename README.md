# daydaystudy-short-url

使用 `go.daydaystudy.top` 建立自己的批量短網址服務。

核心概念：

```text
links.csv
   ↓
build.py
   ↓
public/
   ↓
GitHub Actions
   ↓
GitHub Pages
   ↓
https://go.daydaystudy.top/短碼
```

## 1. 你日後真正需要修改的檔案

通常只需要修改：

```text
links.csv
```

格式：

```csv
short_code,target_url,title,enabled
timss,https://example.com/timss,TIMSS 2027,1
pisa,https://example.com/pisa,PISA 分析,1
aimath,https://example.com/ai-math,AI 數學,1
```

四個欄位：

| 欄位 | 用途 |
|---|---|
| `short_code` | 短網址名稱，例如 `timss` |
| `target_url` | 真正要前往的完整網址 |
| `title` | 顯示名稱 |
| `enabled` | `1` 啟用；`0` 停用 |

例如：

```text
short_code = timss
```

部署後：

```text
https://go.daydaystudy.top/timss
```

---

# 2. 專案結構

```text
daydaystudy-short-url/
├── .github/
│   └── workflows/
│       └── deploy.yml
├── scripts/
│   └── check_dns.sh
├── build.py
├── links.csv
├── .gitignore
└── README.md
```

`public/` 是自動生成的，不需要手動建立或維護。

---

# 3. 第一次：在 WSL / VS Code 建立 GitHub Repository

建議 Repository 名稱：

```text
daydaystudy-short-url
```

在 GitHub 建立一個新的 repository 後，在 WSL 執行：

```bash
cd ~
git clone https://github.com/YOUR_GITHUB_USERNAME/daydaystudy-short-url.git
cd daydaystudy-short-url
code .
```

如果你是把這份模板直接解壓到本機，可以在專案資料夾執行：

```bash
git init
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/daydaystudy-short-url.git
git add .
git commit -m "Initial short URL system"
git push -u origin main
```

---

# 4. 本機測試

執行：

```bash
python3 build.py
```

成功後會看到：

```text
完成：已生成 4 個短網址
/timss -> ...
/pisa -> ...
```

然後啟動簡單的本機網站：

```bash
python3 -m http.server 8000 -d public
```

瀏覽器開啟：

```text
http://localhost:8000/timss/
```

如果可以正確跳轉，代表 redirect 系統正常。

---

# 5. GitHub Pages 設定

進入：

```text
GitHub Repository
→ Settings
→ Pages
```

在 **Build and deployment**：

```text
Source → GitHub Actions
```

本專案已包含：

```text
.github/workflows/deploy.yml
```

所以每次 push 到 `main`，GitHub 都會：

1. 執行 `python3 build.py`
2. 生成 `public/`
3. 上傳 Pages artifact
4. 部署 GitHub Pages

---

# 6. 設定 Custom Domain

仍然在：

```text
Repository
→ Settings
→ Pages
```

找到：

```text
Custom domain
```

填入：

```text
go.daydaystudy.top
```

然後 Save。

建議先在 GitHub 設定 Custom Domain，再到 DNS provider 建立 DNS 記錄。

注意：

如果使用本專案的 GitHub Actions 部署方式，不需要自行建立 `CNAME` 檔案；GitHub 對 custom workflow 的 Pages 部署會以 Repository Pages 設定中的 Custom Domain 為準。

---

# 7. 阿里雲 DNS 設定

到阿里雲 DNS 控制台：

```text
Alibaba Cloud / 阿里雲
→ DNS / 雲解析 DNS
→ daydaystudy.top
→ 添加記錄
```

新增：

| 設定 | 值 |
|---|---|
| 記錄類型 | `CNAME` |
| 主機記錄 | `go` |
| 記錄值 | `YOUR_GITHUB_USERNAME.github.io` |
| TTL | 預設即可 |

重要：

```text
不要填：
YOUR_GITHUB_USERNAME.github.io/daydaystudy-short-url
```

必須直接指向：

```text
YOUR_GITHUB_USERNAME.github.io
```

如果 `go` 已經存在 A、AAAA 或其他衝突記錄，先確認用途，不要直接覆蓋。CNAME 通常不能和同一 hostname 的其他記錄並存。

---

# 8. 檢查 DNS

WSL：

```bash
bash scripts/check_dns.sh
```

或者：

```bash
dig go.daydaystudy.top CNAME +short
```

預期應看到類似：

```text
YOUR_GITHUB_USERNAME.github.io.
```

Windows PowerShell 也可以：

```powershell
Resolve-DnsName go.daydaystudy.top -Type CNAME
```

DNS 變更不一定立即生效。

---

# 9. 啟用 HTTPS

當 GitHub Pages 確認 DNS 正確後：

```text
Repository
→ Settings
→ Pages
→ Enforce HTTPS
```

如果剛設定 Domain，HTTPS 選項可能需要一段時間才可以勾選。

正式分享時請使用：

```text
https://go.daydaystudy.top/timss
```

---

# 10. 日常新增短網址

假設新增：

```text
https://very-long-site.example.com/teacher-training/opencode/2026/index.html
```

修改：

```csv
short_code,target_url,title,enabled
opencode,https://very-long-site.example.com/teacher-training/opencode/2026/index.html,OpenCode 培訓,1
```

然後：

```bash
git add links.csv
git commit -m "Add opencode short URL"
git push
```

GitHub Actions 自動重新部署。

完成後：

```text
https://go.daydaystudy.top/opencode
```

---

# 11. 一次批量加入幾十 / 幾百個網址

直接在 Excel 或 Google Sheets 建立四欄：

```text
short_code | target_url | title | enabled
```

完成後另存為 UTF-8 CSV，覆蓋：

```text
links.csv
```

再：

```bash
python3 build.py
```

先檢查格式。

沒有錯誤後：

```bash
git add links.csv
git commit -m "Batch update short URLs"
git push
```

---

# 12. 修改舊短網址的目的地

例如原本：

```csv
timss,https://old.example.com,TIMSS,1
```

改為：

```csv
timss,https://new.example.com,TIMSS,1
```

保持：

```text
short_code = timss
```

不變。

使用者仍然使用：

```text
https://go.daydaystudy.top/timss
```

但會自動前往新網址。

這是自建短網址最大的好處之一。

---

# 13. 暫停某個短網址

把：

```text
enabled = 1
```

改為：

```text
enabled = 0
```

例如：

```csv
oldcourse,https://example.com/old,舊課程,0
```

重新 push 後：

```text
/oldcourse
```

不再生成，會得到 404。

---

# 14. 支援分類式短網址

`short_code` 支援 `/`。

例如：

```csv
math/timss,https://example.com/timss,TIMSS,1
math/pisa,https://example.com/pisa,PISA,1
ai/opencode,https://example.com/opencode,OpenCode,1
```

會生成：

```text
https://go.daydaystudy.top/math/timss
https://go.daydaystudy.top/math/pisa
https://go.daydaystudy.top/ai/opencode
```

---

# 15. Query parameters

本系統會把短網址收到的 query parameters 傳到目的網址。

例如：

```text
https://go.daydaystudy.top/timss?class=P4A
```

如果目的網址是：

```text
https://example.com/timss
```

JavaScript redirect 會前往：

```text
https://example.com/timss?class=P4A
```

這對日後做來源追蹤、班級代碼或 campaign tracking 很方便。

---

# 16. short_code 規則

建議：

```text
timss
pisa
aimath
open-code
p4/math
teacher/ai
```

允許：

```text
a-z
0-9
-
_
/
```

不要使用空格、中文、`..`。

系統會自動檢查：

- short code 重複
- URL 是否為 http / https
- CSV 欄位是否完整
- enabled 是否合法
- short code 是否包含危險路徑

如果有錯誤，build 會停止，不會部署錯誤資料。

---

# 17. 建議工作流程

日後每次只需要：

```text
取得新的 GitHub / Vercel / Netlify / 其他網站網址
                  ↓
            加入 links.csv
                  ↓
           python3 build.py
             本機驗證
                  ↓
              git push
                  ↓
        GitHub Actions 自動部署
                  ↓
     go.daydaystudy.top/你的短碼
```

---

# 18. 第一批建議短碼

可以按你的用途逐步建立：

```text
go.daydaystudy.top/timss
go.daydaystudy.top/pisa
go.daydaystudy.top/aimath
go.daydaystudy.top/opencode
go.daydaystudy.top/math
go.daydaystudy.top/p4
go.daydaystudy.top/teacher
```

建議不要把短碼設得太抽象，例如 `a1`、`x22`。短網址的主要價值不是只追求字符最少，而是「容易記、容易口頭告訴別人」。

---

# 19. 安全提醒

此系統適合公開網址跳轉。

不要把下列內容放入 `links.csv`：

- 私人管理後台
- 帶永久 token 的網址
- API key
- 密碼重設網址
- 任何不能公開的敏感連結

GitHub Pages 是公開 Web 服務；短網址也應視為公開資訊。
