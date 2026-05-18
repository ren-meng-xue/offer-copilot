from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.services import weather_service


def _mock_response(json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = json_data
    return resp


@pytest.mark.asyncio
async def test_reverse_geocode_returns_adcode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(weather_service.settings, "AMAP_API_KEY", "test-key")
    response_data = {
        "status": "1",
        "regeocode": {"addressComponent": {"adcode": "110105"}},
    }
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_mock_response(response_data))

    with patch(
        "backend.app.services.weather_service.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await weather_service.reverse_geocode(39.9, 116.4)

    assert result == "110105"


@pytest.mark.asyncio
async def test_reverse_geocode_returns_none_on_api_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(weather_service.settings, "AMAP_API_KEY", "test-key")
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_mock_response({"status": "0"}))

    with patch(
        "backend.app.services.weather_service.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await weather_service.reverse_geocode(39.9, 116.4)

    assert result is None


@pytest.mark.asyncio
async def test_reverse_geocode_returns_none_when_no_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(weather_service.settings, "AMAP_API_KEY", None)
    result = await weather_service.reverse_geocode(39.9, 116.4)
    assert result is None


@pytest.mark.asyncio
async def test_geocode_city_returns_adcode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(weather_service.settings, "AMAP_API_KEY", "test-key")
    response_data = {"status": "1", "geocodes": [{"adcode": "310000"}]}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_mock_response(response_data))

    with patch(
        "backend.app.services.weather_service.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await weather_service.geocode_city("上海")

    assert result == "310000"


@pytest.mark.asyncio
async def test_fetch_weather_returns_weather_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(weather_service.settings, "AMAP_API_KEY", "test-key")
    live_data = {
        "status": "1",
        "lives": [
            {
                "city": "北京市",
                "weather": "晴",
                "temperature": "26",
                "winddirection": "南",
                "windpower": "≤3",
                "humidity": "30",
            }
        ],
    }
    forecast_data = {
        "status": "1",
        "forecasts": [
            {
                "casts": [
                    {
                        "date": "2026-05-18",
                        "dayweather": "晴",
                        "nightweather": "晴",
                        "daytemp": "29",
                        "nighttemp": "16",
                        "daywind": "南",
                        "daypower": "≤3",
                    }
                ]
            }
        ],
    }

    async def mock_fetch_both(client, adcode):
        return _mock_response(live_data), _mock_response(forecast_data)

    monkeypatch.setattr(weather_service, "_fetch_both", mock_fetch_both)

    with patch("backend.app.services.weather_service.httpx.AsyncClient"):
        result = await weather_service.fetch_weather("110000")

    assert result is not None
    assert result.city == "北京市"
    assert result.live.weather == "晴"
    assert result.live.temperature == "26"
    assert len(result.forecast) == 1
    assert result.forecast[0].day_temp == "29"


@pytest.mark.asyncio
async def test_fetch_weather_returns_none_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(weather_service.settings, "AMAP_API_KEY", "test-key")

    async def mock_fetch_both(client, adcode):
        return _mock_response({"status": "0"}), _mock_response({"status": "0"})

    monkeypatch.setattr(weather_service, "_fetch_both", mock_fetch_both)

    with patch("backend.app.services.weather_service.httpx.AsyncClient"):
        result = await weather_service.fetch_weather("110000")

    assert result is None
