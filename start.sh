#!/bin/bash

# Youth Chatbot - 同時啟動前後端腳本

echo "=========================================="
echo "  Youth Chatbot 啟動腳本"
echo "=========================================="

# 取得腳本所在目錄
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 定義清理函數 - 在腳本結束時終止所有子進程
cleanup() {
    echo ""
    echo "正在關閉服務..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "服務已關閉"
    exit 0
}

# 捕捉 Ctrl+C 信號
trap cleanup SIGINT SIGTERM

# 啟動後端 (Python Flask)
echo ""
echo "[後端] 啟動 Flask 服務..."
python app.py &
BACKEND_PID=$!
echo "[後端] PID: $BACKEND_PID"

# 等待後端啟動
sleep 2

# 啟動前端 (Vite)
echo ""
echo "[前端] 啟動 Vite 開發伺服器..."
npm run dev &
FRONTEND_PID=$!
echo "[前端] PID: $FRONTEND_PID"

echo ""
echo "=========================================="
echo "  服務已啟動！"
echo "  前端: http://35.212.185.83:3000"
echo "  後端: http://localhost:8300"
echo "  按 Ctrl+C 關閉所有服務"
echo "=========================================="

# 等待子進程
wait
