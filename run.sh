#!/usr/bin/env bash
# Quickstart launcher for AI-Assisted DMX Web Controller
# Binds to 0.0.0.0 so iPads and other devices on local Wi-Fi can connect

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -d "venv" ]; then
    source venv/bin/activate
fi

HOST="${DMX_HOST:-0.0.0.0}"
PORT="${DMX_PORT:-8000}"

echo "=========================================================="
echo "💡 Starting DMX Web Controller on ${HOST}:${PORT}"
echo "📱 Open in browser on this computer: http://localhost:${PORT}"
echo "📱 To connect from an iPad/tablet on your Wi-Fi, open Safari to:"
python3 -c "
import socket, subprocess, re
ips = set()
try:
    out = subprocess.check_output(['hostname', '-I'], text=True, stderr=subprocess.DEVNULL)
    for p in out.strip().split():
        if ':' not in p and not p.startswith('127.'): ips.add(p)
except Exception: pass
try:
    out = subprocess.check_output(['ifconfig'], text=True, stderr=subprocess.DEVNULL)
    for ip in re.findall(r'inet (?:addr:)?([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)', out):
        if not ip.startswith('127.'): ips.add(ip)
except Exception: pass
for ip in sorted(list(ips)):
    print(f'   👉 http://{ip}:${PORT}')
"
echo "=========================================================="

exec python3 -m uvicorn app:app --host "$HOST" --port "$PORT"
