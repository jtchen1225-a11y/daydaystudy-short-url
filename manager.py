#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
import zipfile
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
LINKS_FILE = ROOT / "links.csv"
CONFIG_FILE = ROOT / "config.json"
UI_DIR = ROOT / "manager"
BACKUP_DIR = ROOT / "backups"
PUBLISH_LOCK = threading.Lock()

CODE_RE = re.compile(r"^[a-z0-9](?:[a-z0-9/_-]*[a-z0-9])?$")
RESERVED_CODES = {"index", "404", "assets", "admin", "manager"}
TRUE_VALUES = {"1", "true", "yes", "y", "on"}
FALSE_VALUES = {"0", "false", "no", "n", "off", ""}

try:
    import qrcode
    QR_AVAILABLE = True
except Exception:
    qrcode = None
    QR_AVAILABLE = False


def parse_enabled(value) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value if value is not None else "").strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"enabled 只接受 1/0、true/false、yes/no；收到：{value!r}")


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
            f"short_code 格式不正確：{code!r}。只可使用小寫英文字母、數字、-、_、/，且不可用符號開頭或結尾。"
        )
    return code


def validate_url(raw: str) -> str:
    url = (raw or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"target_url 必須是完整 http/https 網址：{url!r}")
    return url


def validate_rows(rows: list[dict]) -> list[dict]:
    cleaned = []
    seen_codes = set()
    for idx, row in enumerate(rows, start=2):
        try:
            code = normalize_code(str(row.get("short_code", "")))
            target = validate_url(str(row.get("target_url", "")))
            title = str(row.get("title") or code).strip()
            enabled = parse_enabled(row.get("enabled", True))
            if code in seen_codes:
                raise ValueError(f"short_code 重複：{code}")
            seen_codes.add(code)
            cleaned.append(
                {
                    "short_code": code,
                    "target_url": target,
                    "title": title,
                    "enabled": enabled,
                }
            )
        except Exception as exc:
            raise ValueError(f"第 {idx} 行：{exc}") from exc
    return cleaned


def read_links() -> list[dict]:
    if not LINKS_FILE.exists():
        return []
    with LINKS_FILE.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append(
                {
                    "short_code": (row.get("short_code") or "").strip(),
                    "target_url": (row.get("target_url") or "").strip(),
                    "title": (row.get("title") or "").strip(),
                    "enabled": parse_enabled(row.get("enabled", "1")),
                }
            )
        return rows


def backup_links() -> Path | None:
    if not LINKS_FILE.exists():
        return None
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = BACKUP_DIR / f"links-{stamp}.csv"
    counter = 2
    while dst.exists():
        dst = BACKUP_DIR / f"links-{stamp}-{counter}.csv"
        counter += 1
    shutil.copy2(LINKS_FILE, dst)
    backups = sorted(BACKUP_DIR.glob("links-*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[30:]:
        try:
            old.unlink()
        except OSError:
            pass
    return dst


def write_links(rows: list[dict]) -> Path | None:
    cleaned = validate_rows(rows)
    backup = backup_links()
    tmp = LINKS_FILE.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["short_code", "target_url", "title", "enabled"])
        writer.writeheader()
        for row in cleaned:
            writer.writerow(
                {
                    "short_code": row["short_code"],
                    "target_url": row["target_url"],
                    "title": row["title"],
                    "enabled": "1" if row["enabled"] else "0",
                }
            )
    os.replace(tmp, LINKS_FILE)
    return backup


def read_config() -> dict:
    default = {"base_url": "https://go.daydaystudy.top"}
    if not CONFIG_FILE.exists():
        return default
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        base = str(data.get("base_url", default["base_url"])).strip().rstrip("/")
        validate_url(base)
        return {"base_url": base}
    except Exception:
        return default


def write_config(data: dict) -> dict:
    base = str(data.get("base_url", "")).strip().rstrip("/")
    validate_url(base)
    CONFIG_FILE.write_text(json.dumps({"base_url": base}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"base_url": base}


def qr_png_bytes(text: str) -> bytes:
    if not QR_AVAILABLE:
        raise RuntimeError('未安裝 QR Code 套件。請執行：python3 -m pip install "qrcode[pil]"')
    img = qrcode.make(text)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()



def run_command(args: list[str], timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command inside the project directory without invoking a shell."""
    try:
        proc = subprocess.run(
            args,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"找不到指令：{args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"指令逾時：{' '.join(args)}") from exc

    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "未知錯誤").strip()
        raise RuntimeError(f"指令失敗：{' '.join(args)}\n{detail}")
    return proc


def parse_github_remote(remote: str) -> tuple[str, str] | None:
    """Return (owner, repo) for common GitHub HTTPS/SSH remote formats."""
    remote = (remote or "").strip()
    patterns = [
        r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?$",
        r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
        r"^ssh://git@github\.com/([^/]+)/([^/]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.match(pattern, remote, flags=re.I)
        if match:
            return match.group(1), match.group(2)
    return None


def git_repo_info() -> dict:
    inside = run_command(["git", "rev-parse", "--is-inside-work-tree"], check=False)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return {"available": False, "error": "目前資料夾不是 Git repository"}

    branch_proc = run_command(["git", "branch", "--show-current"], check=False)
    branch = branch_proc.stdout.strip() or "main"
    remote_proc = run_command(["git", "remote", "get-url", "origin"], check=False)
    remote = remote_proc.stdout.strip() if remote_proc.returncode == 0 else ""
    sha_proc = run_command(["git", "rev-parse", "HEAD"], check=False)
    sha = sha_proc.stdout.strip() if sha_proc.returncode == 0 else ""
    short_sha = sha[:7] if sha else ""
    subject_proc = run_command(["git", "log", "-1", "--pretty=%s"], check=False)
    subject = subject_proc.stdout.strip() if subject_proc.returncode == 0 else ""
    dirty_proc = run_command(["git", "status", "--porcelain", "--", "links.csv"], check=False)
    links_dirty = bool(dirty_proc.stdout.strip())

    result = {
        "available": True,
        "branch": branch,
        "remote": remote,
        "sha": sha,
        "short_sha": short_sha,
        "subject": subject,
        "links_dirty": links_dirty,
    }
    github = parse_github_remote(remote)
    if github:
        owner, repo = github
        result["github"] = {
            "owner": owner,
            "repo": repo,
            "repository_url": f"https://github.com/{owner}/{repo}",
            "actions_url": f"https://github.com/{owner}/{repo}/actions",
        }
    return result


def github_deployment_status(target_sha: str | None = None) -> dict:
    info = git_repo_info()
    github = info.get("github") if info.get("available") else None
    if not github:
        return {
            "available": False,
            "error": "origin 不是可識別的 GitHub repository",
            "git": info,
        }

    branch = info.get("branch") or "main"
    owner = github["owner"]
    repo = github["repo"]
    api_url = (
        f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}/actions/runs"
        f"?branch={quote(branch)}&per_page=10"
    )
    request = Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "DayDayStudy-Short-URL-Manager/3.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {
            "available": False,
            "error": f"暫時無法取得 GitHub Actions 狀態：{exc}",
            "git": info,
            "actions_url": github["actions_url"],
        }

    runs = data.get("workflow_runs") or []
    chosen = None
    wanted = (target_sha or "").strip() or info.get("sha", "")
    if wanted:
        chosen = next((run for run in runs if run.get("head_sha") == wanted), None)
    if chosen is None and runs:
        chosen = runs[0]
    if chosen is None:
        return {
            "available": True,
            "run": None,
            "message": "尚未找到 GitHub Actions 執行紀錄",
            "git": info,
            "actions_url": github["actions_url"],
        }

    return {
        "available": True,
        "git": info,
        "actions_url": github["actions_url"],
        "run": {
            "id": chosen.get("id"),
            "name": chosen.get("name"),
            "status": chosen.get("status"),
            "conclusion": chosen.get("conclusion"),
            "head_sha": chosen.get("head_sha"),
            "html_url": chosen.get("html_url"),
            "created_at": chosen.get("created_at"),
            "updated_at": chosen.get("updated_at"),
        },
    }


def publish_links(commit_message: str | None = None) -> dict:
    """
    Build, commit links.csv only, and push the current branch.

    Deliberately stages only links.csv so local code edits are never committed by
    the Publish button by accident. GitHub Actions performs the production build.
    """
    if not PUBLISH_LOCK.acquire(blocking=False):
        raise RuntimeError("另一個 Publish 正在執行，請稍候。")

    try:
        info_before = git_repo_info()
        if not info_before.get("available"):
            raise RuntimeError(info_before.get("error", "Git repository 不可用"))
        branch = info_before.get("branch") or "main"
        remote = info_before.get("remote") or ""
        if not remote:
            raise RuntimeError("找不到 Git remote：origin")

        build_proc = run_command([sys.executable, str(ROOT / "build.py")], timeout=90)
        run_command(["git", "add", "--", "links.csv"])

        diff_proc = run_command(["git", "diff", "--cached", "--quiet", "--", "links.csv"], check=False)
        committed = diff_proc.returncode == 1
        commit_output = "links.csv 沒有新的變更，不需要建立 commit。"

        if committed:
            message = (commit_message or "").strip()
            if not message:
                message = datetime.now().strftime("Update short links %Y-%m-%d %H:%M")
            if len(message) > 160:
                raise ValueError("Commit message 最長 160 個字元")
            commit_proc = run_command(["git", "commit", "-m", message], timeout=60)
            commit_output = (commit_proc.stdout or commit_proc.stderr).strip()

        push_proc = run_command(["git", "push", "origin", branch], timeout=180)
        info_after = git_repo_info()
        github = info_after.get("github") or {}

        return {
            "ok": True,
            "committed": committed,
            "build_output": (build_proc.stdout or build_proc.stderr).strip(),
            "commit_output": commit_output,
            "push_output": (push_proc.stdout or push_proc.stderr).strip() or "Push 完成",
            "git": info_after,
            "actions_url": github.get("actions_url"),
        }
    finally:
        PUBLISH_LOCK.release()


class Handler(BaseHTTPRequestHandler):
    server_version = "DayDayStudyManager/3.0"

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def send_json(self, data, status=200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def send_bytes(self, data: bytes, content_type: str, filename: str | None = None, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 5_000_000:
            raise ValueError("資料過大")
        body = self.rfile.read(length)
        return json.loads(body.decode("utf-8")) if body else {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in {"/", "/index.html"}:
            return self.serve_static("index.html", "text/html; charset=utf-8")
        if path == "/app.js":
            return self.serve_static("app.js", "text/javascript; charset=utf-8")
        if path == "/style.css":
            return self.serve_static("style.css", "text/css; charset=utf-8")

        if path == "/api/links":
            return self.send_json({"links": read_links()})
        if path == "/api/config":
            cfg = read_config()
            cfg["qr_available"] = QR_AVAILABLE
            return self.send_json(cfg)
        if path == "/api/git-status":
            return self.send_json(git_repo_info())
        if path == "/api/deployment-status":
            qs = parse_qs(parsed.query)
            sha = unquote(qs.get("sha", [""])[0]).strip() or None
            return self.send_json(github_deployment_status(sha))
        if path == "/api/qr":
            try:
                qs = parse_qs(parsed.query)
                code = normalize_code(unquote(qs.get("code", [""])[0]))
                base = read_config()["base_url"]
                url = f"{base}/{code}"
                return self.send_bytes(qr_png_bytes(url), "image/png")
            except Exception as exc:
                return self.send_json({"error": str(exc)}, 400)

        return self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/save":
                data = self.read_json()
                rows = data.get("links", [])
                if not isinstance(rows, list):
                    raise ValueError("links 必須是陣列")
                backup = write_links(rows)
                return self.send_json(
                    {
                        "ok": True,
                        "count": len(rows),
                        "backup": str(backup.relative_to(ROOT)) if backup else None,
                    }
                )

            if parsed.path == "/api/config":
                data = self.read_json()
                cfg = write_config(data)
                cfg["qr_available"] = QR_AVAILABLE
                return self.send_json({"ok": True, **cfg})

            if parsed.path == "/api/publish":
                data = self.read_json()
                message = str(data.get("commit_message", "")).strip()
                result = publish_links(message or None)
                return self.send_json(result)

            if parsed.path == "/api/qr-zip":
                data = self.read_json()
                codes = data.get("codes", [])
                if not isinstance(codes, list) or not codes:
                    raise ValueError("請至少提供一個 short code")
                base = read_config()["base_url"]
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    used = set()
                    for raw in codes:
                        code = normalize_code(str(raw))
                        if code in used:
                            continue
                        used.add(code)
                        png = qr_png_bytes(f"{base}/{code}")
                        safe_name = code.replace("/", "__") + ".png"
                        zf.writestr(safe_name, png)
                return self.send_bytes(
                    buf.getvalue(),
                    "application/zip",
                    filename="daydaystudy-qr-codes.zip",
                )

            return self.send_json({"error": "Not found"}, 404)
        except Exception as exc:
            return self.send_json({"error": str(exc)}, 400)

    def serve_static(self, name: str, content_type: str):
        path = UI_DIR / name
        if not path.exists():
            return self.send_json({"error": f"缺少 UI 檔案：{name}"}, 500)
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def main():
    parser = argparse.ArgumentParser(description="DayDayStudy 批量短網址管理工具")
    parser.add_argument("--host", default="127.0.0.1", help="預設只監聽本機")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    print("DayDayStudy Short URL Manager V3")
    print(f"管理頁：{url}")
    print(f"資料檔：{LINKS_FILE}")
    print(f"QR Code：{'可用' if QR_AVAILABLE else '不可用（請安裝 requirements.txt）'}")
    info = git_repo_info()
    if info.get("available"):
        print(f"Git：{info.get('branch', '?')} @ {info.get('short_sha', '?')}")
        print("Publish：只會自動提交 links.csv，不會提交其他本機修改。")
    else:
        print(f"Git：不可用（{info.get('error', '未知錯誤')}）")
    print("按 Ctrl+C 關閉。")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    if not args.no_browser and args.host in {"127.0.0.1", "localhost"}:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已關閉管理工具。")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
