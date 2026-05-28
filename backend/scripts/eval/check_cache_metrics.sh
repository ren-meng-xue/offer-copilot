#!/bin/bash
# Cache Metrics 健康检查 — 在跑评估前执行，确保 Prometheus 在采集 cache 指标
# 用法：bash scripts/eval/check_cache_metrics.sh

set -e

METRICS_URL="${METRICS_URL:-http://localhost:8080/metrics}"
PROM_URL="${PROM_URL:-http://localhost:9099}"

echo "=== Cache Metrics 健康检查 ==="

# 1. 确认 /metrics 端点可访问
echo -n "[1/4] /metrics 端点... "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$METRICS_URL")
if [ "$HTTP_CODE" != "200" ]; then
    echo "FAIL (HTTP $HTTP_CODE)"
    echo "  后端未运行？请先启动: ./dev.sh"
    exit 1
fi
echo "OK"

# 2. 确认 cache_ 指标已注册
echo -n "[2/4] cache_ 指标注册... "
CACHE_METRICS=$(curl -sL "$METRICS_URL" | grep -c "cache_lookup_total\|cache_operation_duration_seconds" || true)
if [ "$CACHE_METRICS" -lt 2 ]; then
    echo "FAIL (仅找到 $CACHE_METRICS 个 cache_ 指标)"
    echo "  预期至少 2 个（counter + histogram）"
    exit 1
fi
echo "OK ($CACHE_METRICS 个指标已注册)"

# 3. 确认 Prometheus 在 scrape
echo -n "[3/4] Prometheus scrape 状态... "
UP=$(curl -s "${PROM_URL}/api/v1/query?query=up%7Bjob%3D%22backend%22%7D" | python3 -c "
import sys,json
d = json.load(sys.stdin)
results = d.get('data',{}).get('result',[])
print(results[0]['value'][1] if results else '0')
" 2>/dev/null || echo "0")
if [ "$UP" != "1" ]; then
    echo "FAIL (up=$UP)"
    echo "  Prometheus 未运行或未 scrape backend？"
    echo "  启动: docker compose up -d prometheus"
    exit 1
fi
echo "OK (backend target up)"

# 4. 确认 cache_ 指标有非零值（说明有流量经过 cache 路径）
echo -n "[4/4] cache_lookup_total 数据点... "
CACHE_TOTAL=$(curl -s "${PROM_URL}/api/v1/query?query=cache_lookup_total" | python3 -c "
import sys,json
d = json.load(sys.stdin)
results = d.get('data',{}).get('result',[])
total = 0
for r in results:
    total += float(r.get('value',[0,0])[1])
print(int(total))
" 2>/dev/null || echo "0")
if [ "$CACHE_TOTAL" -eq 0 ]; then
    echo "WARN (无数据点 — 这是正常的如果还没发请求)"
    echo "  cache_ 指标已注册但计数器全为 0。"
    echo "  跑完评估后缓存数据会自动上报到 Prometheus。"
else
    echo "OK ($CACHE_TOTAL 次 cache lookup)"
fi

echo ""
echo "=== 检查通过，可以开始评估 ==="
