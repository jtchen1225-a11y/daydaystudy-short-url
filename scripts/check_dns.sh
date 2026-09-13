#!/usr/bin/env bash
set -e

DOMAIN="${1:-go.daydaystudy.top}"

echo "Checking CNAME for: $DOMAIN"
echo

if command -v dig >/dev/null 2>&1; then
  dig "$DOMAIN" CNAME +short
elif command -v nslookup >/dev/null 2>&1; then
  nslookup -type=CNAME "$DOMAIN"
else
  echo "找不到 dig 或 nslookup。"
  exit 1
fi
