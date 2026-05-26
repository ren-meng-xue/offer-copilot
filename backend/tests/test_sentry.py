from dataclasses import dataclass
from pydantic import BaseModel
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


def test_sanitize_sentry_value_does_not_redact_non_sensitive_keys() -> None:
    event = {
        "extra": {
            "tokenizer": "gpt-4",
            "vector_key": "chunk_123",
            "hotkeyMap": "Ctrl+P",
            "keyboard": "QWERTY",
            "api_key": "secret-key-123",
        }
    }

    sanitized = sanitize_sentry_value(event)

    assert sanitized["extra"]["tokenizer"] == "gpt-4"
    assert sanitized["extra"]["vector_key"] == "chunk_123"
    assert sanitized["extra"]["hotkeyMap"] == "Ctrl+P"
    assert sanitized["extra"]["keyboard"] == "QWERTY"
    assert sanitized["extra"]["api_key"] == "[REDACTED]"


def test_sanitize_sentry_value_redacts_pii_in_strings() -> None:
    event = {
        "exception": {
            "values": [
                {
                    "type": "ValueError",
                    "value": "登录失败: test.user+123@example.com / password=mySecret123",
                }
            ]
        },
        "message": "Auth failed for user@domain.cn with token: 'secret-token-val'",
    }

    sanitized = sanitize_sentry_value(event)

    assert "[EMAIL_REDACTED]" in sanitized["exception"]["values"][0]["value"]
    assert "password=[REDACTED]" in sanitized["exception"]["values"][0]["value"]
    assert "test.user" not in sanitized["exception"]["values"][0]["value"]
    assert "mySecret123" not in sanitized["exception"]["values"][0]["value"]

    assert "[EMAIL_REDACTED]" in sanitized["message"]
    assert "token=[REDACTED]" in sanitized["message"]
    assert "secret-token-val" not in sanitized["message"]


def test_api_keys_plural_is_redacted() -> None:
    """api_keys (plural) must be redacted — it was previously whitelisted by the 'keys' NON_SENSITIVE entry."""
    event = {"extra": {"api_keys": "sk-abc123", "hotkeys": "Ctrl+P"}}
    sanitized = sanitize_sentry_value(event)
    assert sanitized["extra"]["api_keys"] == "[REDACTED]"
    assert sanitized["extra"]["hotkeys"] == "Ctrl+P"


def test_sanitize_sentry_value_handles_pydantic_and_dataclasses() -> None:
    class UserSchema(BaseModel):
        email: str
        password: str
        name: str

    @dataclass
    class SimpleDataclass:
        api_key: str
        chunk_key: str

    user = UserSchema(email="user@test.com", password="pwd", name="bob")
    dc = SimpleDataclass(api_key="secret", chunk_key="vector")

    event = {"extra": {"user": user, "dc": dc}}

    sanitized = sanitize_sentry_value(event)

    assert sanitized["extra"]["user"]["email"] == "[EMAIL_REDACTED]"
    assert sanitized["extra"]["user"]["password"] == "[REDACTED]"
    assert sanitized["extra"]["user"]["name"] == "bob"

    assert sanitized["extra"]["dc"]["api_key"] == "[REDACTED]"
    assert sanitized["extra"]["dc"]["chunk_key"] == "vector"
