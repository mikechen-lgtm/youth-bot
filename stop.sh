#!/bin/bash

# Youth Chatbot - Ubuntu 停止服務腳本

echo "=========================================="
echo "  Youth Chatbot 停止服務"
echo "=========================================="

echo ""
echo "[後端] 停止 Python 服務..."
pkill -f "python.*app.py" 2>/dev/null && echo "  已停止" || echo "  未運行"

echo "[前端] 停止 Node 服務..."
pkill -f "vite" 2>/dev/null && echo "  已停止" || echo "  未運行"

echo ""
echo "=========================================="
echo "  所有服務已停止"
echo "=========================================="
