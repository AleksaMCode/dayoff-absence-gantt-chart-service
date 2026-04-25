import os
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

os.environ["LANG"] = "en"
os.environ.setdefault("DAYOFF_API_KEY", "test-api-key")

import main as app_main


class TestMainEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app_main.app)

    @patch("main.publish_to_channel")
    @patch("main.upload_image")
    @patch("main.generate_absence_gantt")
    @patch.object(app_main.dayoff_adapter, "get_absences_for_window")
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

    @patch("main.publish_to_channel")
    @patch("main.generate_absence_gantt")
    @patch.object(app_main.dayoff_adapter, "get_absences_for_window")
    def test_get_absences_success_without_chart(
        self,
        mock_get_absences_for_window: Mock,
        mock_generate_absence_gantt: Mock,
        mock_publish_to_channel: Mock,
    ) -> None:
        mock_get_absences_for_window.return_value = {
            "team_name": "Team 1",
            "team_id": 12954,
            "window_start": "2026-04-21",
            "window_end": "2026-04-25",
            "employees_count": 0,
            "employees_absences": [],
        }
        mock_generate_absence_gantt.return_value = None

        response = self.client.post(
            "/get_absences", json={"team_name": "Team 1", "days_ahead": 5}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["employees_count"], 0)
        mock_publish_to_channel.assert_called_once_with(no_absences=True)

    @patch("main.publish_to_channel")
    @patch("main.upload_image")
    @patch("main.generate_absence_gantt")
    @patch.object(app_main.dayoff_adapter, "get_absences_for_window")
    @patch.object(app_main.dayoff_adapter, "get_absences_for_users_window")
    def test_get_absences_uses_username_mode_when_email_usernames_present(
        self,
        mock_get_absences_for_users_window: Mock,
        mock_get_absences_for_window: Mock,
        mock_generate_absence_gantt: Mock,
        mock_upload_image: Mock,
        mock_publish_to_channel: Mock,
    ) -> None:
        mock_get_absences_for_users_window.return_value = {
            "team_name": "Sprint Team",
            "team_id": None,
            "window_start": "2026-04-21",
            "window_end": "2026-04-25",
            "employees_count": 1,
            "employees_absences": [
                {
                    "employee_id": 10,
                    "name": "Wick",
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
            "/get_absences",
            json={
                "team_name": "Sprint Team",
                "email_usernames": ["wick"],
                "days_ahead": 5,
            },
        )

        self.assertEqual(response.status_code, 200)
        mock_get_absences_for_users_window.assert_called_once()
        mock_get_absences_for_window.assert_not_called()
        mock_publish_to_channel.assert_called_once_with(
            image_url="https://sharepoint.local/chart.png"
        )

    @patch.object(app_main.dayoff_adapter, "get_absences_for_window")
    def test_get_absences_returns_404_on_value_error(
        self, mock_get_absences_for_window: Mock
    ) -> None:
        mock_get_absences_for_window.side_effect = ValueError("Team not found")

        response = self.client.post(
            "/get_absences", json={"team_name": "Unknown", "days_ahead": 5}
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Team not found")

    @patch("main.generate_absence_gantt")
    @patch.object(app_main.dayoff_adapter, "get_absences_for_window")
    def test_get_absences_returns_500_on_unexpected_exception(
        self,
        mock_get_absences_for_window: Mock,
        mock_generate_absence_gantt: Mock,
    ) -> None:
        mock_get_absences_for_window.return_value = {
            "team_name": "Team 1",
            "team_id": 12954,
            "window_start": "2026-04-21",
            "window_end": "2026-04-25",
            "employees_count": 1,
            "employees_absences": [
                {"employee_id": 1, "name": "A", "absence_dates": []}
            ],
        }
        mock_generate_absence_gantt.side_effect = RuntimeError("chart failed")

        response = self.client.post(
            "/get_absences", json={"team_name": "Team 1", "days_ahead": 5}
        )

        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to fetch absences", response.json()["detail"])

    def test_get_absences_returns_422_for_invalid_payload(self) -> None:
        response = self.client.post(
            "/get_absences",
            json={"team_name": "Team 1", "team_id": 123, "days_ahead": 5},
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
