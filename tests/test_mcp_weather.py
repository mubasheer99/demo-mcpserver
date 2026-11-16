import unittest
from unittest.mock import Mock, call, patch

import mcp_weather


class OpenMeteoToolTests(unittest.TestCase):
    @patch("mcp_weather.requests.get")
    def test_current_weather_geocodes_city_and_uses_forecast_api(self, get: Mock) -> None:
        geocoding_response = Mock()
        geocoding_response.json.return_value = {
            "results": [
                {"name": "Bhatkal", "country_code": "IN", "latitude": 13.97, "longitude": 74.57}
            ]
        }
        current_response = Mock()
        current_response.json.return_value = {
            "timezone": "Asia/Kolkata",
            "utc_offset_seconds": 19800,
            "current": {
                "time": "2025-01-01T12:00",
                "temperature_2m": 25,
                "apparent_temperature": 27,
                "dew_point_2m": 20,
                "relative_humidity_2m": 70,
                "pressure_msl": 1010,
                "cloud_cover": 50,
                "visibility": 10000,
                "wind_speed_10m": 3,
                "wind_direction_10m": 180,
                "wind_gusts_10m": 5,
                "uv_index": 4,
                "weather_code": 3,
            },
            "daily": {
                "time": ["2025-01-01"],
                "temperature_2m_min": [22],
                "temperature_2m_max": [28],
                "sunrise": ["2025-01-01T06:30"],
                "sunset": ["2025-01-01T18:00"],
            },
        }
        get.side_effect = [geocoding_response, current_response]

        result = mcp_weather.get_current_weather("Bhatkal", country="IN")

        self.assertEqual(result["city"], "Bhatkal")
        self.assertEqual(result["country"], "IN")
        self.assertEqual(result["weather"]["description"], "overcast")
        self.assertEqual(result["temperature"]["current"], 25)
        self.assertEqual(result["temperature"]["min"], 22)
        self.assertEqual(
            get.call_args_list,
            [
                call(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={
                        "name": "Bhatkal",
                        "count": 1,
                        "language": "en",
                        "format": "json",
                        "countryCode": "IN",
                    },
                    timeout=mcp_weather.REQUEST_TIMEOUT_SECONDS,
                ),
                call(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": 13.97,
                        "longitude": 74.57,
                        "current": (
                            "temperature_2m,relative_humidity_2m,apparent_temperature,dew_point_2m,"
                            "pressure_msl,cloud_cover,visibility,wind_speed_10m,wind_direction_10m,"
                            "wind_gusts_10m,uv_index,precipitation,weather_code"
                        ),
                        "daily": (
                            "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,"
                            "sunrise,sunset,uv_index_max,precipitation_probability_max,wind_speed_10m_max,"
                            "wind_direction_10m_dominant,wind_gusts_10m_max"
                        ),
                        "forecast_days": 1,
                        "timezone": "auto",
                        "wind_speed_unit": "ms",
                        "precipitation_unit": "mm",
                    },
                    timeout=mcp_weather.REQUEST_TIMEOUT_SECONDS,
                ),
            ],
        )

    @patch("mcp_weather.requests.get")
    def test_forecast_normalizes_daily_data_and_imperial_units(self, get: Mock) -> None:
        geocoding_response = Mock()
        geocoding_response.json.return_value = {
            "results": [
                {"name": "Bhatkal", "country_code": "IN", "latitude": 13.97, "longitude": 74.57}
            ]
        }
        forecast_response = Mock()
        forecast_response.json.return_value = {
            "utc_offset_seconds": 19800,
            "daily": {
                "time": ["2025-01-01"],
                "weather_code": [61],
                "temperature_2m_max": [80],
                "temperature_2m_min": [70],
                "apparent_temperature_max": [82],
                "sunrise": ["2025-01-01T06:30"],
                "sunset": ["2025-01-01T18:00"],
                "uv_index_max": [5],
                "precipitation_probability_max": [30],
                "wind_speed_10m_max": [12],
                "wind_direction_10m_dominant": [90],
                "wind_gusts_10m_max": [18],
            },
        }
        get.side_effect = [geocoding_response, forecast_response]

        result = mcp_weather.get_weather_forecast(
            "Bhatkal", days=1, units="imperial", country="IN"
        )

        self.assertEqual(result["forecast"][0]["temperature"]["max"], 80)
        self.assertEqual(result["forecast"][0]["temperature"]["min"], 70)
        self.assertEqual(result["forecast"][0]["weather"]["summary"], "Rain")
        self.assertEqual(result["forecast"][0]["date"], "2025-01-01")
        self.assertEqual(
            get.call_args_list[1].kwargs["params"]["temperature_unit"],
            "fahrenheit",
        )
        self.assertEqual(get.call_args_list[1].kwargs["params"]["wind_speed_unit"], "mph")
        self.assertEqual(get.call_args_list[1].kwargs["params"]["precipitation_unit"], "inch")

    def test_standard_units_convert_open_meteo_celsius_to_kelvin(self) -> None:
        self.assertEqual(mcp_weather._convert_temperature(0, "standard"), 273.15)
        self.assertEqual(mcp_weather._convert_temperature(0, "metric"), 0)

    @patch("mcp_weather.requests.get")
    def test_city_not_found_is_reported(self, get: Mock) -> None:
        response = Mock()
        response.json.return_value = {"results": []}
        get.return_value = response

        with self.assertRaisesRegex(ValueError, "No Open-Meteo location found"):
            mcp_weather.get_current_weather("Unknown place")

    def test_forecast_rejects_days_above_documented_tool_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "days must be between 1 and 5"):
            mcp_weather.get_weather_forecast("Bhatkal", days=6)


if __name__ == "__main__":
    unittest.main()
