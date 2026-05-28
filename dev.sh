#!/bin/bash

# 设置代理 (根据用户 v2rayN 配置)
export http_proxy=http://127.0.0.1:7897
export https_proxy=http://127.0.0.1:7897
export ALL_PROXY=http://127.0.0.1:7897
export NO_PROXY=localhost,127.0.0.1,0.0.0.0,::1,.local

BACKEND_PORT=8080
FRONTEND_PORT=3005
# OfferPilot 一键启动开发环境脚本

echo "🧹 清理残留进程..."
pkill -f "celery.*worker" 2>/dev/null || true
pkill -f "app/main.py" 2>/dev/null || true
# 强制释放可能被占用的端口
lsof -i :8080 -t | xargs kill -9 2>/dev/null || true
lsof -i :3005 -t | xargs kill -9 2>/dev/null || true
sleep 1

echo "🚀 正在启动 Docker 依赖 (Postgres & Redis & Prometheus & Grafana)..."
docker-compose up -d postgres redis prometheus grafana

if [ $? -ne 0 ]; then
    echo "❌ Docker 启动失败，请检查 Docker Desktop 是否已运行。"
    exit 1
fi

echo "⏳ 等待数据库 (5439) 和 Redis (6389) 就绪..."
MAX_RETRIES=30
RETRY_COUNT=0
while ! nc -z 127.0.0.1 6389 >/dev/null 2>&1 || ! nc -z 127.0.0.1 5439 >/dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT+1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "❌ 等待超时，数据库或 Redis 未能启动。"
        exit 1
    fi
    printf "."
    sleep 1
done
echo " ✅ 已就绪"

echo "🧹 清理 Celery 残留任务..."
# 确保在执行 purge 前 Redis 已经可以接受连接
CELERY_BROKER_URL=redis://127.0.0.1:6389/1 backend/.venv/bin/python -m celery -A backend.app.tasks:celery_app purge -f

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
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
backend/.venv/bin/python -m celery -A backend.app.tasks:celery_app worker --loglevel=info --pool=solo > celery.log 2>&1 &
CELERY_PID=$!

echo "🎨 [Frontend] 启动中..."
cd frontend && pnpm dev --port $FRONTEND_PORT > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

echo "-------------------------------------------------------"
echo "✅ 所有服务已在后台运行！"
echo "🌐 前端地址: http://localhost:$FRONTEND_PORT"
echo "接口文档: http://localhost:$BACKEND_PORT/docs"
echo "📊 Grafana: http://localhost:3009 (admin/admin)"
echo "📈 Prometheus: http://localhost:9099"
echo "-------------------------------------------------------"
echo "📝 日志文件说明:"
echo "   - 后端日志: tail -f backend.log"
echo "   - 任务日志: tail -f celery.log"
echo "   - 前端日志: tail -f frontend.log"
echo "-------------------------------------------------------"
echo "💡 按 [Ctrl+C] 可同时停止所有服务。"

wait
