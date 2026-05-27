#!/bin/bash
# Task 21: 跑 After 评估 + Locust 压测
# 用法: ./scripts/run_after.sh "<EVAL_TOKEN>"
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$BACKEND_DIR/.." && pwd)"
SPEC_DIR="$PROJECT_DIR/docs/specs/2026-05-27-measurement-and-fix"
AFTER_DIR="$SPEC_DIR/screenshots/after"
PYTHON="$BACKEND_DIR/.venv/bin/python"

if [ $# -lt 1 ]; then
    echo "用法: $0 <EVAL_TOKEN>"
    echo "  从浏览器 localStorage 复制 access_token"
    exit 1
fi

export EVAL_TOKEN="$1"
export EVAL_BASE_URL="${EVAL_BASE_URL:-http://localhost:8000}"

# 检查后端是否可达
echo ">>> 检查后端连接..."
if ! curl -sf -o /dev/null "$EVAL_BASE_URL/api/v1/qa/conversations" -H "Authorization: Bearer $EVAL_TOKEN"; then
    echo "!!! 后端不可达或 token 无效，请确认 dev.sh 已启动且 token 正确"
    exit 1
fi
echo ">>> 后端连接正常"

mkdir -p "$AFTER_DIR"

echo ""
echo "=== Step 2: 跑评估集 ==="
cd "$BACKEND_DIR"
$PYTHON -m scripts.eval.run_eval \
    --golden ../eval/golden.jsonl \
    --output "$SPEC_DIR/report-after.md" \
    --label after

echo ""
echo "=== Step 3: 跑 Locust 50 用户 (5 分钟) ==="
export LOCUST_TOKEN="$EVAL_TOKEN"
export LOCUST_KB_IDS="${LOCUST_KB_IDS:-1,2,3}"

$PYTHON -m locust -f scripts/load_test/locustfile.py \
    --host="$EVAL_BASE_URL" \
    --headless -u 50 -r 5 -t 5m \
    --html "$AFTER_DIR/locust-50.html" \
    --csv "$AFTER_DIR/locust-50"

echo ""
echo "=== Step 3: 跑 Locust 100 用户 (5 分钟) ==="
$PYTHON -m locust -f scripts/load_test/locustfile.py \
    --host="$EVAL_BASE_URL" \
    --headless -u 100 -r 10 -t 5m \
    --html "$AFTER_DIR/locust-100.html" \
    --csv "$AFTER_DIR/locust-100"

echo ""
echo "=== 完成 ==="
echo "评估报告: $SPEC_DIR/report-after.md"
echo "Locust 50: $AFTER_DIR/locust-50.html"
echo "Locust 100: $AFTER_DIR/locust-100.html"
echo ""
echo ">>> 接下来请手动截图 Grafana 三张看板并保存到 $AFTER_DIR/:"
echo "    rag.png / http.png / cache.png"
