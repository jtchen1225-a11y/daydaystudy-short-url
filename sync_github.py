#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DayDayStudy 自動同步 GitHub 倉庫為短網址腳本
支援自動抓取 GitHub 倉庫與 GitHub Pages，智慧生成 short_code，更新 links.csv 並構建推送。
"""

import csv
import json
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV_FILE = ROOT / "links.csv"
CONFIG_FILE = ROOT / "config.json"

# 預定義優先精簡別名字典
CUSTOM_ALIASES = {
    "macau-uni-bonus-points-guide": "macau",
    "cdsj5-section-features": "features",
    "math-review-deck": "f6",
    "cdsj5-math-opencode-workshop": "opencode",
    "pisa-2025-macau-curriculum-report": "pisa",
    "math-j7a-review": "7a",
    "math-j7b-review": "7b",
    "math-j8a-review": "8a",
    "math-j8b-review": "8b",
    "math-j9a-review": "9a",
    "math-j9b-review": "9b",
    "math-b1-review": "b1",
    "math-b2-review": "b2",
    "math-b3-review": "b3",
    "math-b4-review": "b4",
    "math-xb1-review": "xb1",
    "math-xb2-review": "xb2",
    "math-lesson-deck": "lesson",
    "timss-p4-lab-ipad": "p4lab",
    "timss-p4-math-lab": "p4math",
    "macau-distinguished-teachers": "teacher",
    "fruit-verb-game": "fruit",
    "pythagorean-demo": "pythagoras",
    "wordcloud-demo": "wordcloud",
    "sci-research-workflow": "sci",
    "um-dissertation-formatter-api": "um-api",
    "opencode-github-test": "opencode-test",
    "daydaystudy-short-url": "admin"
}

def load_existing_links():
    rows = []
    seen_codes = set()
    seen_targets = {}
    if CSV_FILE.exists():
        with CSV_FILE.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                code = r.get("short_code", "").strip()
                target = r.get("target_url", "").strip()
                title = r.get("title", "").strip()
                enabled = r.get("enabled", "1").strip()
                if code:
                    rows.append({"short_code": code, "target_url": target, "title": title, "enabled": enabled})
                    seen_codes.add(code)
                    if target:
                        seen_targets[target.rstrip("/")] = code
    return rows, seen_codes, seen_targets

import shutil

def get_gh_cmd():
    if shutil.which("gh"):
        return "gh"
    if shutil.which("gh.exe"):
        return "gh.exe"
    p = Path("/mnt/c/Program Files/GitHub CLI/gh.exe")
    if p.exists():
        return str(p)
    return "gh"

def fetch_repos(owner):
    gh_cmd = get_gh_cmd()
    cmd = [gh_cmd, 'repo', 'list', owner, '--limit', '100', '--json', 'name,description,url,homepageUrl,isPrivate,isArchived']
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(res.stdout)

def detect_pages_url(owner, repo_name, homepage_url):
    pages_candidate = f"https://{owner}.github.io/{repo_name}/"
    if homepage_url and "github.io" in homepage_url:
        return homepage_url
    try:
        req = urllib.request.Request(pages_candidate, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                return pages_candidate
    except Exception:
        pass
    return None

def sync(owners=None, auto_push=True):
    if not owners:
        owners = ["jtchen1225-a11y"]

    print("=" * 60)
    print(f"🚀 開始自動同步 GitHub 倉庫 (目標帳號: {', '.join(owners)})")
    print("=" * 60)

    rows, seen_codes, seen_targets = load_existing_links()
    print(f"現有 links.csv 已有 {len(rows)} 筆短網址。")

    all_repos = []
    for owner in owners:
        try:
            print(f"正在透過 GitHub CLI 抓取 {owner} 的倉庫清單...")
            repos = fetch_repos(owner)
            for r in repos:
                r["_owner"] = owner
            all_repos.extend(repos)
        except Exception as e:
            print(f"⚠️ 抓取 {owner} 失敗: {e}")

    print(f"共抓取到 {len(all_repos)} 個 GitHub 倉庫。正在檢測 GitHub Pages 在線狀態...")

    def check_repo(r):
        owner = r["_owner"]
        name = r["name"]
        hp = r.get("homepageUrl") or ""
        pages = detect_pages_url(owner, name, hp)
        target = pages if pages else r["url"]
        desc = r.get("description") or name
        return {
            "owner": owner,
            "name": name,
            "target": target,
            "desc": desc,
            "is_pages": bool(pages)
        }

    with ThreadPoolExecutor(max_workers=10) as ex:
        checked_repos = list(ex.map(check_repo, all_repos))

    added_count = 0
    for item in checked_repos:
        name = item["name"]
        target = item["target"]
        desc = item["desc"]
        norm_target = target.rstrip("/")

        # 優先短代碼建議
        pref_code = CUSTOM_ALIASES.get(name, name).lower()

        # 檢查是否已在 links.csv
        if pref_code not in seen_codes:
            rows.append({
                "short_code": pref_code,
                "target_url": target,
                "title": desc,
                "enabled": "1"
            })
            seen_codes.add(pref_code)
            seen_targets[norm_target] = pref_code
            added_count += 1
            print(f"  [+新增] /{pref_code:15s} -> {target} ({desc[:25]})")

        # 同時若別名不同於倉庫全名，且倉庫全名未被佔用，也加一條完整名稱別名
        if name.lower() != pref_code and name.lower() not in seen_codes:
            rows.append({
                "short_code": name.lower(),
                "target_url": target,
                "title": desc,
                "enabled": "1"
            })
            seen_codes.add(name.lower())
            added_count += 1

    # 寫回 links.csv
    with CSV_FILE.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["short_code", "target_url", "title", "enabled"])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print("-" * 60)
    print(f"✅ links.csv 更新完成！本次新增 {added_count} 條，現共有 {len(rows)} 條短網址。")

    # 執行 build.py
    print("🔨 正在執行 build.py 生成靜態跳轉頁...")
    from build import build
    build()

    # 自動 Git 提交與推送
    if auto_push:
        print("📦 正在自動提交並推送到 GitHub...")
        try:
            subprocess.run(["git", "add", "links.csv", "build.py", "config.json", "sync_github.py"], cwd=ROOT, check=True)
            commit_res = subprocess.run(["git", "commit", "-m", f"sync: 自動同步 GitHub 倉庫短網址 (共 {len(rows)} 筆)"], cwd=ROOT, capture_output=True, text=True)
            if "nothing to commit" not in commit_res.stdout:
                print("  已建立 Commit。正在 Push...")
                subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
                print("🎉 Push 成功！GitHub Actions 正在自動部署到 www.daydaystudy.top！")
            else:
                print("  無新變更需要 Commit。")
        except Exception as e:
            print(f"⚠️ Git 操作提示: {e}")

    print("=" * 60)
    print("🌟 同步完成！所有短網址均可透過 https://www.daydaystudy.top/XXX 訪問！")
    print("=" * 60)

if __name__ == "__main__":
    owners = ["jtchen1225-a11y"]
    if "--all" in sys.argv:
        owners = ["jtchen1225-a11y", "mathruffian-dot"]
    sync(owners=owners, auto_push=True)
