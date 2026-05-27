from backend.app.core import metrics


def test_metrics_module_exposes_required_objects():
    # HTTP
    assert hasattr(metrics, "HTTP_REQUESTS_TOTAL")
    assert hasattr(metrics, "HTTP_REQUEST_DURATION_SECONDS")
    assert hasattr(metrics, "HTTP_REQUESTS_IN_PROGRESS")

    # RAG
    assert hasattr(metrics, "RAG_STAGE_DURATION_SECONDS")
    assert hasattr(metrics, "RAG_TOTAL_DURATION_SECONDS")
    assert hasattr(metrics, "RAG_TTFT_SECONDS")
    assert hasattr(metrics, "RAG_OUTCOME_TOTAL")
    assert hasattr(metrics, "RAG_CANDIDATES_COUNT")
    assert hasattr(metrics, "RAG_CITATIONS_COUNT")
    assert hasattr(metrics, "RAG_COHERE_TOP_SCORE")
    assert hasattr(metrics, "RAG_QUERY_REWRITTEN_TOTAL")
    assert hasattr(metrics, "RAG_SCOPE_SIZE")

    # Cache
    assert hasattr(metrics, "CACHE_LOOKUP_TOTAL")
    assert hasattr(metrics, "CACHE_OPERATION_DURATION_SECONDS")

    # App info
    assert hasattr(metrics, "APP_INFO")


def test_http_requests_total_has_expected_labels():
    sample = metrics.HTTP_REQUESTS_TOTAL.labels(
        method="GET", path_template="/api/v1/qa/ping", status_class="2xx"
    )
    sample.inc()
    # 通过 collect 不会抛异常即认为标签正确
    list(metrics.HTTP_REQUESTS_TOTAL.collect())
