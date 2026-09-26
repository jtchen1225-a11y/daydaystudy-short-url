#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DayDayStudy Universal Short URL Engine (通用短網址引擎)
支援任何專案一鍵自動註冊、全量 GitHub 倉庫同步、Pages 在線檢測與自動構建發布。
"""

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV_FILE = ROOT / "links.csv"
CONFIG_FILE = ROOT / "config.json"
BASE_URL = "https://www.daydaystudy.top"

# 預定義常用簡短別名
CUSTOM_ALIASES = {
    # jtchen1225-a11y
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
    "daydaystudy-short-url": "admin",

    # mathruffian-dot
    "math-sequence-games": "sequence",
    "seat-chart-generator": "seat",
    "blackhole-war": "blackhole",
    "quadratic-function-graph": "quadratic",
    "tetris-game": "tetris",
    "classroom-tools-9": "tools9",
    "shouzhu-daitu": "shouzhu",
    "math-graph-tool": "graph",
    "delin-campus-tour-system": "delin",
    "airport-vocab-game": "airport",
    "2026-fraction-cooking-rescue": "fraction",
    "taigi-teaching-agent-plan": "taigi",
    "super-teacher-2026": "superteacher",
    "triangle-geometry-8": "geometry8",
    "ch4-2-inequality-slides": "inequality",
    "opencode-coordinate-game": "coordinate",
    "firebase-wordcloud": "livecloud",
}

def to_wsl_path(p: str) -> Path:
    p = p.strip().strip('"').strip("'")
    if len(p) >= 2 and p[1] == ':':
        drive = p[0].lower()
        rest = p[2:].replace('\\', '/').lstrip('/')
        return Path(f"/mnt/{drive}/{rest}").resolve()
    return Path(p).resolve()

def get_gh_cmd():
    for candidate in ["gh", "gh.exe", "/mnt/c/Program Files/GitHub CLI/gh.exe"]:
        if shutil.which(candidate) or Path(candidate).exists():
            return candidate
    return "gh"

def load_existing_links():
    rows = []
    seen_codes = set()
    code_to_row = {}
    if CSV_FILE.exists():
        with CSV_FILE.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                code = r.get("short_code", "").strip()
                target = r.get("target_url", "").strip()
                title = r.get("title", "").strip()
                enabled = r.get("enabled", "1").strip()
                if code:
                    row_data = {"short_code": code, "target_url": target, "title": title, "enabled": enabled}
                    rows.append(row_data)
                    seen_codes.add(code)
                    code_to_row[code] = row_data
    return rows, seen_codes, code_to_row

def save_links(rows):
    with CSV_FILE.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["short_code", "target_url", "title", "enabled"])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

def run_build_and_push(commit_msg: str, auto_push: bool = True):
    print("🔨 正在編譯生成靜態短網址跳轉頁面...")
    from build import build
    build()

    if auto_push:
        print("📦 正在自動 Git Commit 並推送到 GitHub...")
        try:
            subprocess.run(["git", "add", "links.csv", "build.py", "config.json", "sync_github.py", "shorturl_engine.py"], cwd=ROOT, check=True)
            res = subprocess.run(["git", "commit", "-m", commit_msg], cwd=ROOT, capture_output=True, text=True)
            if "nothing to commit" not in res.stdout:
                subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
                print("🎉 推送成功！GitHub Actions 正在自動部署到 www.daydaystudy.top！")
            else:
                print("ℹ️ 無內容變更，跳過推送。")
        except Exception as e:
            print(f"⚠️ Git 操作提示: {e}")

def detect_pages_url(owner: str, repo_name: str, homepage_url: str = "") -> str:
    if homepage_url and "github.io" in homepage_url:
        return homepage_url
    candidate = f"https://{owner}.github.io/{repo_name}/"
    try:
        req = urllib.request.Request(candidate, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                return candidate
    except Exception:
        pass
    return ""

def parse_git_remote(repo_path: Path):
    git_config = repo_path / ".git" / "config"
    if not git_config.exists():
        if (repo_path / "config").exists() and repo_path.name == ".git":
            git_config = repo_path / "config"
        else:
            return None, None

    content = git_config.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'url\s*=\s*(?:git@github\.com:|https?://github\.com/)([\w-]+)/([\w.-]+?)(?:\.git)?\s*$', content, re.M)
    if m:
        return m.group(1), m.group(2)
    return None, None

def cmd_register(args):
    """將當前專案或指定路徑/URL 註冊為短網址"""
    target_path_or_url = args.target or "."
    rows, seen_codes, code_to_row = load_existing_links()

    owner = None
    repo_name = None
    target_url = None
    title = args.title or ""

    if target_path_or_url.startswith("http://") or target_path_or_url.startswith("https://"):
        target_url = target_path_or_url
        if "github.com/" in target_url:
            parts = target_url.rstrip("/").split("github.com/")[-1].split("/")
            if len(parts) >= 2:
                owner, repo_name = parts[0], parts[1].replace(".git", "")
        elif "github.io/" in target_url:
            parts = target_url.rstrip("/").split("github.io/")
            owner = parts[0].split("//")[-1]
            repo_name = parts[1].split("/")[0] if len(parts) > 1 else ""
    else:
        repo_path = to_wsl_path(target_path_or_url)
        if not repo_path.exists():
            print(f"❌ 找不到目錄: {target_path_or_url}")
            sys.exit(1)

        owner, repo_name = parse_git_remote(repo_path)
        if not owner or not repo_name:
            print(f"❌ 無法在 {repo_path} 解析出 GitHub Remote 倉庫資訊，請確認是否為 Git 專案並配置了 origin。")
            sys.exit(1)

        print(f"🔍 識別專案: {owner}/{repo_name}")
        pages = detect_pages_url(owner, repo_name)
        if pages:
            target_url = pages
            print(f"🌐 偵測到在線 GitHub Pages: {pages}")
        else:
            target_url = f"https://github.com/{owner}/{repo_name}"
            print(f"📁 未開通 Pages，短網址將指向 GitHub 倉庫: {target_url}")

    if not title:
        title = repo_name if repo_name else target_url

    short_code = args.code
    if not short_code:
        if repo_name:
            short_code = CUSTOM_ALIASES.get(repo_name, repo_name).lower()
        else:
            short_code = re.sub(r'[^a-z0-9_-]', '', Path(target_url).name.lower())[:20] or "link"

    if short_code in code_to_row:
        code_to_row[short_code]["target_url"] = target_url
        code_to_row[short_code]["title"] = title
        code_to_row[short_code]["enabled"] = "1"
        print(f"✏️ 更新現有短網址: /{short_code} -> {target_url}")
    else:
        new_row = {"short_code": short_code, "target_url": target_url, "title": title, "enabled": "1"}
        rows.append(new_row)
        seen_codes.add(short_code)
        code_to_row[short_code] = new_row
        print(f"✨ 新增短網址: /{short_code} -> {target_url}")

    if repo_name and repo_name.lower() != short_code:
        full_code = repo_name.lower()
        if full_code in code_to_row:
            code_to_row[full_code]["target_url"] = target_url
        else:
            rows.append({"short_code": full_code, "target_url": target_url, "title": title, "enabled": "1"})
            seen_codes.add(full_code)

    save_links(rows)
    run_build_and_push(f"feat: 註冊專案短網址 /{short_code} -> {repo_name or target_url}", auto_push=not args.no_push)

    print("\n" + "=" * 60)
    print(f"🎉 專案短網址註冊成功！")
    print(f"🔗 專屬短網址：{BASE_URL}/{short_code}")
    if repo_name and repo_name.lower() != short_code:
        print(f"📌 原名短網址：{BASE_URL}/{repo_name.lower()}")
    print(f"🌐 目標網址  ：{target_url}")
    print("=" * 60 + "\n")

def cmd_add(args):
    """手動添加任意短網址"""
    code = args.code.strip().lower()
    target = args.target.strip()
    title = args.title or code

    rows, seen_codes, code_to_row = load_existing_links()
    if code in code_to_row:
        code_to_row[code]["target_url"] = target
        code_to_row[code]["title"] = title
        code_to_row[code]["enabled"] = "1"
        print(f"✏️ 更新短網址: /{code} -> {target}")
    else:
        rows.append({"short_code": code, "target_url": target, "title": title, "enabled": "1"})
        print(f"✨ 新增短網址: /{code} -> {target}")

    save_links(rows)
    run_build_and_push(f"feat: 手動新增短網址 /{code}", auto_push=not args.no_push)
    print(f"✅ 短網址已配置: {BASE_URL}/{code} -> {target}")

def cmd_sync(args):
    """全量同步 GitHub 倉庫"""
    owners = args.owners or ["jtchen1225-a11y", "mathruffian-dot"]
    gh_cmd = get_gh_cmd()

    print("=" * 60)
    print(f"🚀 開始全量同步 GitHub 倉庫 (目標帳號: {', '.join(owners)})")
    print("=" * 60)

    rows, seen_codes, code_to_row = load_existing_links()
    print(f"現有短網址共有 {len(rows)} 筆。")

    all_repos = []
    for owner in owners:
        try:
            print(f"正在透過 GitHub CLI 抓取 {owner} 的倉庫清單 (上限 300 個)...")
            cmd = [gh_cmd, 'repo', 'list', owner, '--limit', '300', '--json', 'name,description,url,homepageUrl,isPrivate,isArchived']
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            repos = json.loads(res.stdout)
            for r in repos:
                r["_owner"] = owner
            print(f"  ✓ {owner}: 獲取到 {len(repos)} 個倉庫")
            all_repos.extend(repos)
        except Exception as e:
            print(f"  ⚠️ 抓取 {owner} 失敗: {e}")

    print(f"\n共獲取 {len(all_repos)} 個倉庫。正在透過多線程檢測 GitHub Pages 在線狀態...")

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

    with ThreadPoolExecutor(max_workers=15) as ex:
        checked_repos = list(ex.map(check_repo, all_repos))

    added_count = 0
    updated_count = 0

    for item in checked_repos:
        name = item["name"]
        target = item["target"]
        desc = item["desc"]
        pref_code = CUSTOM_ALIASES.get(name, name).lower()

        # 優先短碼
        if pref_code not in seen_codes:
            new_r = {"short_code": pref_code, "target_url": target, "title": desc, "enabled": "1"}
            rows.append(new_r)
            seen_codes.add(pref_code)
            code_to_row[pref_code] = new_r
            added_count += 1
            print(f"  [+新增] /{pref_code:18s} -> {target} ({desc[:25]})")
        elif item["is_pages"] and not code_to_row[pref_code]["target_url"].endswith("/"):
            code_to_row[pref_code]["target_url"] = target
            updated_count += 1

        # 原倉庫名稱完整別名
        if name.lower() != pref_code:
            full_code = name.lower()
            if full_code not in seen_codes:
                new_r = {"short_code": full_code, "target_url": target, "title": desc, "enabled": "1"}
                rows.append(new_r)
                seen_codes.add(full_code)
                code_to_row[full_code] = new_r
                added_count += 1
            elif item["is_pages"] and not code_to_row[full_code]["target_url"].endswith("/"):
                code_to_row[full_code]["target_url"] = target
                updated_count += 1

    save_links(rows)
    print("-" * 60)
    print(f"✅ 更新完成！本次新增 {added_count} 筆，升級 {updated_count} 筆，現共有 {len(rows)} 條短網址。")

    run_build_and_push(f"sync: 全量自動同步 GitHub 倉庫短網址 (現共 {len(rows)} 筆)", auto_push=not args.no_push)
    print("\n" + "=" * 60)
    print(f"🌟 全量同步完成！所有短網址均可透過 {BASE_URL}/XXX 訪問！")
    print("=" * 60 + "\n")

def cmd_list(args):
    """查詢短網址"""
    rows, _, _ = load_existing_links()
    q = (args.query or "").lower()
    matches = [r for r in rows if not q or q in r["short_code"].lower() or q in r["target_url"].lower() or q in r["title"].lower()]
    print(f"\n找到 {len(matches)} 筆短網址 (總數 {len(rows)}):")
    print(f"{'短代碼':20s} | {'啟用':4s} | {'標題':30s} | 目標網址")
    print("-" * 90)
    for r in matches[:args.limit]:
        print(f"/{r['short_code']:19s} | {r['enabled']:4s} | {r['title'][:28]:30s} | {r['target_url']}")
    if len(matches) > args.limit:
        print(f"... 尚有 {len(matches) - args.limit} 筆未列出，請使用關鍵字縮小查詢範圍。")
    print()

def main():
    parser = argparse.ArgumentParser(description="DayDayStudy Universal Short URL CLI")
    subparsers = parser.add_subparsers(dest="command")

    reg_parser = subparsers.add_parser("register", help="註冊 Git 專案或網址為短網址")
    reg_parser.add_argument("target", nargs="?", default=".", help="專案目錄路徑或網址（預設當前目錄）")
    reg_parser.add_argument("--code", "-c", help="自訂短代碼 (short code)")
    reg_parser.add_argument("--title", "-t", help="專案標題說明")
    reg_parser.add_argument("--no-push", action="store_true", help="僅生成不推送到遠端")

    add_parser = subparsers.add_parser("add", help="手動添加短網址")
    add_parser.add_argument("code", help="短代碼")
    add_parser.add_argument("target", help="目標網址")
    add_parser.add_argument("title", nargs="?", default="", help="標題說明")
    add_parser.add_argument("--no-push", action="store_true", help="僅生成不推送到遠端")

    sync_parser = subparsers.add_parser("sync", help="全量同步 GitHub 倉庫")
    sync_parser.add_argument("--owners", "-o", nargs="+", default=["jtchen1225-a11y", "mathruffian-dot"], help="目標 GitHub 帳號清單")
    sync_parser.add_argument("--no-push", action="store_true", help="僅生成不推送到遠端")

    list_parser = subparsers.add_parser("list", help="查詢現有短網址")
    list_parser.add_argument("query", nargs="?", default="", help="搜尋關鍵字")
    list_parser.add_argument("--limit", "-n", type=int, default=50, help="最多顯示筆數")

    args = parser.parse_args()

    if args.command == "register":
        cmd_register(args)
    elif args.command == "add":
        cmd_add(args)
    elif args.command == "sync":
        cmd_sync(args)
    elif args.command == "list":
        cmd_list(args)
    else:
        if len(sys.argv) == 1:
            parser.print_help()
        else:
            arg = sys.argv[1]
            args.title = None
            args.no_push = False
            if arg.startswith("http://") or arg.startswith("https://") or to_wsl_path(arg).exists():
                args.target = arg
                args.code = None
            else:
                args.target = "."
                args.code = arg
            cmd_register(args)

if __name__ == "__main__":
    main()
