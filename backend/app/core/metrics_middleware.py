"""HTTP 层 Prometheus 指标采集 middleware。"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.app.core.config import settings
from backend.app.core.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_IN_PROGRESS,
    HTTP_REQUESTS_TOTAL,
)


def _status_class(status_code: int) -> str:
    """把具体 HTTP 状态码折叠成 2xx/4xx/5xx，控制指标标签基数。"""

    return f"{status_code // 100}xx"


def _path_template(request: Request) -> str:
    """优先取路由模板，避免真实 URL 中的 ID 造成标签基数爆炸。"""

    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        return route.path
    return "__unmatched__"


class PrometheusMiddleware(BaseHTTPMiddleware):
    """采集 HTTP 请求数、耗时和并发请求数。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.PROMETHEUS_ENABLED:
            return await call_next(request)

        metrics_path = settings.METRICS_PATH.rstrip("/")
        if request.url.path.rstrip("/") == metrics_path:
            return await call_next(request)

        method = request.method
        path_template = "__pending__"
        start = time.perf_counter()
        HTTP_REQUESTS_IN_PROGRESS.labels(
            method=method, path_template=path_template
        ).inc()

        try:
            response = await call_next(request)
            path_template = _path_template(request)
            status = response.status_code
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                path_template=path_template,
                status_class=_status_class(status),
            ).inc()
            return response
        except Exception:
            path_template = _path_template(request)
            HTTP_REQUESTS_TOTAL.labels(
                method=method, path_template=path_template, status_class="5xx"
            ).inc()
            raise
        finally:
            elapsed = time.perf_counter() - start
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method, path_template=path_template
            ).observe(elapsed)
            HTTP_REQUESTS_IN_PROGRESS.labels(
                method=method, path_template="__pending__"
            ).dec()
