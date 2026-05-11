from backend.app.core.config import Settings
from backend.app.core.cors import build_cors_middleware_options


def test_settings_parse_cors_allow_origins() -> None:
    settings = Settings(
        BACKEND_CORS_ORIGINS=" http://localhost:3000, ,https://offer-copilot-frontend.vercel.app ",
    )

    assert settings.cors_allow_origins == [
        "http://localhost:3000",
        "https://offer-copilot-frontend.vercel.app",
    ]


def test_settings_default_cors_origins_include_production_frontend() -> None:
    settings = Settings(_env_file=None)

    assert "http://localhost:3000" in settings.cors_allow_origins
    assert "http://127.0.0.1:3000" in settings.cors_allow_origins
    assert "https://offer-copilot-frontend.vercel.app" in settings.cors_allow_origins


def test_settings_parse_cors_origin_regex() -> None:
    settings = Settings(BACKEND_CORS_ORIGIN_REGEX="  https://.*\\.vercel\\.app  ")

    assert settings.cors_allow_origin_regex == "https://.*\\.vercel\\.app"


def test_settings_parse_empty_cors_origin_regex() -> None:
    settings = Settings(BACKEND_CORS_ORIGIN_REGEX="   ")

    assert settings.cors_allow_origin_regex is None


def test_build_cors_middleware_options_omit_regex_when_empty() -> None:
    settings = Settings(BACKEND_CORS_ORIGINS="http://localhost:3000", BACKEND_CORS_ORIGIN_REGEX=None)

    options = build_cors_middleware_options(settings)

    assert options == {
        "allow_origins": ["http://localhost:3000"],
        "allow_methods": ["*"],
        "allow_headers": ["*"],
        "allow_credentials": True,
    }


def test_build_cors_middleware_options_include_regex() -> None:
    settings = Settings(
        BACKEND_CORS_ORIGINS="https://offer-copilot-frontend.vercel.app",
        BACKEND_CORS_ORIGIN_REGEX=r"https://offer-copilot-frontend-git-.*\.vercel\.app",
    )

    options = build_cors_middleware_options(settings)

    assert options == {
        "allow_origins": ["https://offer-copilot-frontend.vercel.app"],
        "allow_methods": ["*"],
        "allow_headers": ["*"],
        "allow_credentials": True,
        "allow_origin_regex": r"https://offer-copilot-frontend-git-.*\.vercel\.app",
    }
