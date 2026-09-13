#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

if ! python3 -c 'import qrcode' >/dev/null 2>&1; then
  echo '缺少 QR Code 套件。正在安裝 requirements.txt ...'
  python3 -m pip install -r requirements.txt
fi

exec python3 manager.py
