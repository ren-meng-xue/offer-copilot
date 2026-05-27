#!/bin/bash

# 设置代理 (根据用户 v2rayN 配置)
export http_proxy=http://127.0.0.1:10808
export https_proxy=http://127.0.0.1:10808
export ALL_PROXY=http://127.0.0.1:10808

# OfferPilot 一键启动开发环境脚本

echo "🧹 清理残留进程..."
pkill -f "celery.*backend.app.tasks" 2>/dev/null || true
pkill -f "backend/app/main.py" 2>/dev/null || true
sleep 1

echo "🚀 正在启动 Docker 依赖 (Postgres & Redis & Prometheus & Grafana)..."
docker-compose up -d postgres redis prometheus grafana

if [ $? -ne 0 ]; then
    echo "❌ Docker 启动失败，请检查 Docker Desktop 是否已运行。"
    exit 1
fi

echo "等待数据库和 Redis 就绪..."
sleep 2

echo "🧹 清理 Celery 残留任务..."
backend/.venv/bin/python -m celery -A backend.app.tasks:celery_app purge -f

if [ $? -ne 0 ]; then
    echo "⚠️ Celery 残留任务清理失败，继续启动服务..."
fi

cleanup() {
    echo ""
    echo "🛑 正在停止所有服务..."
    kill $BACKEND_PID $CELERY_PID $FRONTEND_PID 2>/dev/null
    echo "✅ 服务已关闭。"
    exit
}

trap cleanup SIGINT

echo "后台服务启动中..."

echo "📡 [Backend] 启动中..."
export PYTHONPATH="$PWD"
uv run --directory backend python app/main.py > backend.log 2>&1 &
BACKEND_PID=$!

echo "👷 [Celery] 启动中..."
backend/.venv/bin/python -m celery -A backend.app.tasks:celery_app worker --loglevel=info > celery.log 2>&1 &
CELERY_PID=$!

echo "🎨 [Frontend] 启动中..."
cd frontend && pnpm dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

echo "-------------------------------------------------------"
echo "✅ 所有服务已在后台运行！"
echo "🌐 前端地址: http://localhost:3000"
echo "接口文档: http://localhost:8000/docs"
echo "📊 Grafana: http://localhost:3001 (admin/admin)"
echo "📈 Prometheus: http://localhost:9090"
echo "-------------------------------------------------------"
echo "📝 日志文件说明:"
echo "   - 后端日志: tail -f backend.log"
echo "   - 任务日志: tail -f celery.log"
echo "   - 前端日志: tail -f frontend.log"
echo "-------------------------------------------------------"
echo "💡 按 [Ctrl+C] 可同时停止所有服务。"

wait