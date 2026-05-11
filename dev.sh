#!/bin/bash

# OfferPilot 一键启动开发环境脚本

echo "🚀 正在启动 Docker 依赖 (Postgres & Redis)..."
docker-compose up -d postgres redis

# 检查 Docker 是否启动成功
if [ $? -ne 0 ]; then
    echo "❌ Docker 启动失败，请检查 Docker Desktop 是否已运行。"
    exit 1
fi

echo "等待数据库就绪..."
sleep 2

# 定义清理函数：当按下 Ctrl+C 时，同时关闭所有后台进程
cleanup() {
    echo ""
    echo "🛑 正在停止所有服务..."
    kill $BACKEND_PID $CELERY_PID $FRONTEND_PID 2>/dev/null
    echo "✅ 服务已关闭。"
    exit
}

trap cleanup SIGINT

echo "后台服务启动中..."

# 1. 启动后端 API (后台运行)
echo "📡 [Backend] 启动中..."
export PYTHONPATH=.
uv run python backend/app/main.py > backend.log 2>&1 &
BACKEND_PID=$!

# 2. 启动 Celery Worker (后台运行)
echo "👷 [Celery] 启动中..."
uv run celery -A backend.app.tasks:celery_app worker --loglevel=info > celery.log 2>&1 &
CELERY_PID=$!

# 3. 启动前端 (后台运行)
echo "🎨 [Frontend] 启动中..."
cd frontend && pnpm dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

echo "-------------------------------------------------------"
echo "✅ 所有服务已在后台运行！"
echo "🌐 前端地址: http://localhost:3000"
echo "接口文档: http://localhost:8000/docs"
echo "-------------------------------------------------------"
echo "📝 日志文件说明:"
echo "   - 后端日志: tail -f backend.log"
echo "   - 任务日志: tail -f celery.log"
echo "   - 前端日志: tail -f frontend.log"
echo "-------------------------------------------------------"
echo "💡 按 [Ctrl+C] 可同时停止所有服务。"

# 保持脚本运行，以便等待 Ctrl+C
wait
