import importlib
import os
import sys
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

os.environ["LANG"] = "en"


def _load_main_module():
    for module_name in ["main", "routers.api_absences", "routers.scraper_absences"]:
        sys.modules.pop(module_name, None)
    return importlib.import_module("main")


class TestMainApiModeEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch.dict(
            os.environ,
            {
                "DAYOFF_FETCH_MODE": "api",
                "DAYOFF_API_KEY": "test-api-key",
            },
            clear=False,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app_main = _load_main_module()
        self.client = TestClient(self.app_main.app)

    @patch("routers.api_absences.publish_to_channel")
    @patch("routers.api_absences.upload_image")
    @patch("routers.api_absences.generate_absence_gantt")
    @patch("routers.api_absences.api_adapter.get_absences_for_window")
    def test_get_absences_success_with_chart(
        self,
        mock_get_absences_for_window: Mock,
        mock_generate_absence_gantt: Mock,
        mock_upload_image: Mock,
        mock_publish_to_channel: Mock,
    ) -> None:
        mock_get_absences_for_window.return_value = {
            "team_name": "Team 1",
            "team_id": 12954,
            "window_start": "2026-04-21",
            "window_end": "2026-04-25",
            "employees_count": 1,
            "employees_absences": [
                {
                    "employee_id": 1,
                    "name": "John Wick",
                    "absence_dates": ["2026-04-22"],
                }
            ],
        }
        mock_generate_absence_gantt.return_value = {
            "chart_file_name": "chart.png",
            "chart_bytes": b"png-bytes",
        }
        mock_upload_image.return_value = "https://sharepoint.local/chart.png"

        response = self.client.post(
            "/get_absences", json={"team_name": "Team 1", "days_ahead": 5}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["chart_file_name"], "chart.png")
        self.assertEqual(
            body["sharepoint_file_url"], "https://sharepoint.local/chart.png"
        )
        mock_publish_to_channel.assert_called_once_with(
            image_url="https://sharepoint.local/chart.png"
        )

    @patch("routers.api_absences.api_adapter.get_absences_for_window")
    def test_get_absences_returns_404_on_value_error(
        self, mock_get_absences_for_window: Mock
    ) -> None:
        mock_get_absences_for_window.side_effect = ValueError("Team not found")
        response = self.client.post(
            "/get_absences", json={"team_name": "Unknown", "days_ahead": 5}
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Team not found")

    def test_scraper_route_not_available_in_api_mode(self) -> None:
        response = self.client.post(
            "/get_absences_scraped", json={"full_names": ["John Wick"], "days_ahead": 5}
        )
        self.assertEqual(response.status_code, 404)

    def test_get_absences_returns_422_for_invalid_payload(self) -> None:
        response = self.client.post(
            "/get_absences",
            json={"team_name": "Team 1", "team_id": 123, "days_ahead": 5},
        )
        self.assertEqual(response.status_code, 422)


class TestMainScraperModeEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch.dict(
            os.environ,
            {
                "DAYOFF_FETCH_MODE": "scraper",
                "DAYOFF_SCRAPER_EMAIL": "scraper@example.com",
                "DAYOFF_SCRAPER_PASSWORD": "password",
            },
            clear=False,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app_main = _load_main_module()
        self.client = TestClient(self.app_main.app)

    @patch("routers.scraper_absences.publish_to_channel")
    @patch("routers.scraper_absences.upload_image")
    @patch("routers.scraper_absences.generate_absence_gantt")
    @patch("routers.scraper_absences.scraper_adapter.get_absences_for_users_window")
    def test_get_absences_scraped_success_with_chart(
        self,
        mock_scraped_absences: Mock,
        mock_generate_absence_gantt: Mock,
        mock_upload_image: Mock,
        mock_publish_to_channel: Mock,
    ) -> None:
        mock_scraped_absences.return_value = {
            "team_name": "Sprint Team",
            "team_id": None,
            "window_start": "2026-04-21",
            "window_end": "2026-04-25",
            "employees_count": 1,
            "employees_absences": [
                {
                    "employee_id": 10,
                    "name": "John Wick",
                    "absence_dates": ["2026-04-22"],
                }
            ],
        }
        mock_generate_absence_gantt.return_value = {
            "chart_file_name": "chart.png",
            "chart_bytes": b"png-bytes",
        }
        mock_upload_image.return_value = "https://sharepoint.local/chart.png"

        response = self.client.post(
            "/get_absences_scraped",
            json={
                "full_names": ["John Wick"],
                "team_name": "Sprint Team",
                "days_ahead": 5,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["chart_file_name"], "chart.png")
        mock_publish_to_channel.assert_called_once_with(
            image_url="https://sharepoint.local/chart.png"
        )

    def test_api_route_not_available_in_scraper_mode(self) -> None:
        response = self.client.post(
            "/get_absences", json={"team_name": "Team 1", "days_ahead": 5}
        )
        self.assertEqual(response.status_code, 404)

    def test_get_absences_scraped_returns_422_for_invalid_payload(self) -> None:
        response = self.client.post(
            "/get_absences_scraped",
            json={"full_names": [""], "days_ahead": 5},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
