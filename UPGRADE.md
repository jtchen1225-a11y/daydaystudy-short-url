# DayDayStudy Short URL Manager 升級說明

這個升級包不包含 `links.csv`，因此不會覆蓋你現有的短網址資料。

把升級包內所有檔案解壓到既有 `daydaystudy-short-url` 專案根目錄即可。

第一次執行：

```bash
python3 -m pip install -r requirements.txt
python3 manager.py
```

瀏覽器：

```text
http://127.0.0.1:8787
```

完成管理後，按管理頁的「儲存 links.csv」，再執行：

```bash
python3 build.py
git add .
git commit -m "Upgrade short URL manager"
git push
```

之後日常更新只需要：

```bash
python3 manager.py
```

在管理頁新增／修改網址並儲存，然後：

```bash
git add links.csv
git commit -m "Update short links"
git push
```
