import pytest
from pydantic import ValidationError
from backend.app.schemas.auth import RegisterRequest


def test_register_request_username_validation():
    # Valid username
    req = RegisterRequest(
        email="test@example.com", username="testuser", password="password123"
    )
    assert req.username == "testuser"

    # Username with spaces should be trimmed
    req = RegisterRequest(
        email="test@example.com", username="  trimmeduser  ", password="password123"
    )
    assert req.username == "trimmeduser"

    # Empty username should fail
    with pytest.raises(ValidationError) as excinfo:
        RegisterRequest(email="test@example.com", username="", password="password123")
    # Pydantic's min_length=1 might catch this first
    assert "String should have at least 1 character" in str(
        excinfo.value
    ) or "用户名不能为空" in str(excinfo.value)

    # Whitespace-only username should fail with our custom message
    with pytest.raises(ValidationError) as excinfo:
        RegisterRequest(
            email="test@example.com", username="   ", password="password123"
        )
    assert "用户名不能为空" in str(excinfo.value)

    # Username too long should fail
    with pytest.raises(ValidationError) as excinfo:
        RegisterRequest(
            email="test@example.com", username="a" * 51, password="password123"
        )
    assert "String should have at most 50 characters" in str(excinfo.value)
