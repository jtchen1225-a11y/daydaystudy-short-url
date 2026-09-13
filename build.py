#!/usr/bin/env python3
"""
Build static redirect pages from links.csv.

Usage:
    python3 build.py

Input:
    links.csv

Output:
    public/
"""

from __future__ import annotations

import csv
import html
import json
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CSV_FILE = ROOT / "links.csv"
OUTPUT_DIR = ROOT / "public"

CODE_RE = re.compile(r"^[a-z0-9](?:[a-z0-9/_-]*[a-z0-9])?$")
RESERVED_CODES = {"index", "404", "assets"}
TRUE_VALUES = {"1", "true", "yes", "y", "on"}
FALSE_VALUES = {"0", "false", "no", "n", "off", ""}


def parse_enabled(value: str) -> bool:
    normalized = (value or "").strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(
        f"enabled 只接受 1/0、true/false、yes/no；收到：{value!r}"
    )


def normalize_code(raw: str) -> str:
    code = (raw or "").strip().strip("/").lower()

    if not code:
        raise ValueError("short_code 不可留空")
    if ".." in code:
        raise ValueError(f"short_code 不可包含 '..'：{code}")
    if code in RESERVED_CODES:
        raise ValueError(f"short_code 使用了保留名稱：{code}")
    if not CODE_RE.fullmatch(code):
        raise ValueError(
            f"short_code 格式不正確：{code!r}。"
            "只可使用小寫英文字母、數字、-、_、/，且不可用符號開頭或結尾。"
        )
    return code


def validate_url(raw: str) -> str:
    url = (raw or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"target_url 必須是完整 http/https 網址：{url!r}")
    return url


def redirect_html(target: str, title: str) -> str:
    safe_target = html.escape(target, quote=True)
    safe_title = html.escape(title or "Redirecting…", quote=True)
    target_js = json.dumps(target, ensure_ascii=False)

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <meta http-equiv="refresh" content="0; url={safe_target}">
  <link rel="canonical" href="{safe_target}">
  <title>{safe_title}</title>
</head>
<body>
  <p>正在前往 <a href="{safe_target}">{safe_title}</a>…</p>
  <script>
    (() => {{
      const target = {target_js};
      try {{
        const source = new URL(window.location.href);
        const destination = new URL(target);

        // 將短網址後的 query parameters 一併帶到目的網址。
        source.searchParams.forEach((value, key) => {{
          destination.searchParams.append(key, value);
        }});

        // 如果目的網址本身沒有 hash，保留短網址的 hash。
        if (source.hash && !destination.hash) {{
          destination.hash = source.hash;
        }}

        window.location.replace(destination.toString());
      }} catch (error) {{
        window.location.replace(target);
      }}
    }})();
  </script>
</body>
</html>
"""


def home_html(count: int) -> str:
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>DayDayStudy Short URL</title>
</head>
<body>
  <main>
    <h1>DayDayStudy Short URL</h1>
    <p>短網址服務運作正常。</p>
    <p>目前已生成 {count} 個啟用中的短網址。</p>
  </main>
</body>
</html>
"""


def not_found_html() -> str:
    return """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>404 | DayDayStudy Short URL</title>
</head>
<body>
  <h1>404</h1>
  <p>這個短網址不存在，請檢查網址是否正確。</p>
</body>
</html>
"""


def load_rows():
    if not CSV_FILE.exists():
        raise FileNotFoundError(f"找不到 {CSV_FILE}")

    with CSV_FILE.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"short_code", "target_url", "title", "enabled"}
        actual = set(reader.fieldnames or [])
        missing = required - actual
        if missing:
            raise ValueError(
                "links.csv 缺少欄位：" + ", ".join(sorted(missing))
            )

        rows = []
        seen = set()

        for line_no, row in enumerate(reader, start=2):
            try:
                enabled = parse_enabled(row.get("enabled", ""))
                if not enabled:
                    continue

                code = normalize_code(row.get("short_code", ""))
                target = validate_url(row.get("target_url", ""))
                title = (row.get("title") or code).strip()

                if code in seen:
                    raise ValueError(f"short_code 重複：{code}")
                seen.add(code)

                rows.append(
                    {
                        "short_code": code,
                        "target_url": target,
                        "title": title,
                    }
                )
            except Exception as exc:
                raise ValueError(f"links.csv 第 {line_no} 行：{exc}") from exc

        return rows


def build():
    rows = load_rows()

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    for row in rows:
        page_dir = OUTPUT_DIR / row["short_code"]
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "index.html").write_text(
            redirect_html(row["target_url"], row["title"]),
            encoding="utf-8",
        )

    (OUTPUT_DIR / "index.html").write_text(home_html(len(rows)), encoding="utf-8")
    (OUTPUT_DIR / "404.html").write_text(not_found_html(), encoding="utf-8")
    (OUTPUT_DIR / ".nojekyll").write_text("", encoding="utf-8")

    print(f"完成：已生成 {len(rows)} 個短網址")
    for row in rows:
        print(f"  /{row['short_code']} -> {row['target_url']}")
    print(f"輸出目錄：{OUTPUT_DIR}")


if __name__ == "__main__":
    build()
