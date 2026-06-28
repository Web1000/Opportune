#!/bin/bash
# Double-click this file to launch the AI Opportunity Matcher.
# It starts the backend and opens the app in your default browser.

cd "$(dirname "$0")" || exit 1
export PORT="${PORT:-5001}"

echo "──────────────────────────────────────────────"
echo "  🎯 AI Opportunity Matcher"
echo "  启动中… 浏览器会自动打开 http://localhost:$PORT"
echo "  使用期间请保持本窗口打开。"
echo "  停止:关闭此窗口,或按 Ctrl+C。"
echo "──────────────────────────────────────────────"

if [ ! -x "./venv/bin/python" ]; then
  echo "❌ 找不到虚拟环境 (venv)。请先在项目目录运行: python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"
  read -r -p "按回车键退出…" _
  exit 1
fi

# Open the browser a moment after the server starts.
( sleep 2 && open "http://localhost:$PORT" ) &

exec ./venv/bin/python app.py
