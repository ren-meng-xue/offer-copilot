from backend.app.core.sentry import before_send, sanitize_sentry_value


def test_sanitize_sentry_value_redacts_sensitive_fields() -> None:
    event = {
        "request": {
            "headers": {
                "authorization": "Bearer abc",
                "cookie": "session=abc",
                "x-request-id": "req_123",
            },
            "data": {
                "password": "secret",
                "apiKey": "key",
                "name": "alice",
            },
        }
    }

    sanitized = sanitize_sentry_value(event)

    assert sanitized["request"]["headers"]["authorization"] == "[REDACTED]"
    assert sanitized["request"]["headers"]["cookie"] == "[REDACTED]"
    assert sanitized["request"]["headers"]["x-request-id"] == "req_123"
    assert sanitized["request"]["data"]["password"] == "[REDACTED]"
    assert sanitized["request"]["data"]["apiKey"] == "[REDACTED]"
    assert sanitized["request"]["data"]["name"] == "alice"


def test_before_send_returns_sanitized_event() -> None:
    event = {"extra": {"refresh_token": "abc", "status": "failed"}}

    sanitized = before_send(event, {})

    assert sanitized == {"extra": {"refresh_token": "[REDACTED]", "status": "failed"}}
