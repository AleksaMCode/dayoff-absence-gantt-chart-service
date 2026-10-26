import os
import unittest
from datetime import date
from unittest.mock import Mock, patch

from dayoff.scraper_adapter import DayOffScraperAdapter


class TestDayOffScraperAdapter(unittest.TestCase):
    def setUp(self) -> None:
        self.env_patcher = patch.dict(
            os.environ,
            {
                "DAYOFF_SCRAPER_EMAIL": "scraper@example.com",
                "DAYOFF_SCRAPER_PASSWORD": "password",
                "DAYOFF_SCRAPER_BASE_URL": "https://tracker.day-off.app",
            },
            clear=False,
        )
        self.env_patcher.start()
        self.adapter = DayOffScraperAdapter()

    def tearDown(self) -> None:
        self.env_patcher.stop()

    def test_init_raises_when_email_missing(self) -> None:
        with patch.dict(os.environ, {"DAYOFF_SCRAPER_EMAIL": ""}, clear=False):
            with self.assertRaisesRegex(
                ValueError, "DAYOFF_SCRAPER_EMAIL is not configured."
            ):
                DayOffScraperAdapter()

    def test_filter_requests_by_full_names_uses_exact_match(self) -> None:
        requests = [
            {
                "Name": "John Wick",
                "FromDateFormated": "2026-10-13",
                "ToDateFormated": "2026-10-14",
            },
            {
                "Name": "john wick",
                "FromDateFormated": "2026-10-13",
                "ToDateFormated": "2026-10-14",
            },
            {
                "Name": "John Wick ",
                "FromDateFormated": "2026-10-13",
                "ToDateFormated": "2026-10-14",
            },
        ]

        filtered = self.adapter._filter_requests_by_full_names(requests, ["John Wick"])

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["Name"], "John Wick")

    def test_extract_requests_from_payload_supports_results_shape(self) -> None:
        payload = {
            "Results": {
                "AcceptedRequests": [
                    {
                        "Name": "John Wick",
                        "FromDateFormated": "2026-10-13",
                        "ToDateFormated": "2026-10-14",
                    }
                ]
            }
        }

        extracted = self.adapter._extract_requests_from_payload(payload)
        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0]["Name"], "John Wick")

    @patch.object(DayOffScraperAdapter, "_scrape_calendar_requests")
    def test_get_absences_for_users_window_days_ahead_zero_returns_empty_without_scrape(
        self, mock_scrape_calendar_requests: Mock
    ) -> None:
        result = self.adapter.get_absences_for_users_window(
            full_names=["John Wick"],
            team_name="Sprint Team",
            start_date=date(2026, 10, 13),
            days_ahead=0,
        )

        mock_scrape_calendar_requests.assert_not_called()
        self.assertEqual(result["team_name"], "Sprint Team")
        self.assertEqual(result["window_start"], "2026-10-13")
        self.assertEqual(result["window_end"], "2026-10-13")
        self.assertEqual(result["employees_count"], 0)
        self.assertEqual(result["employees_absences"], [])

    @patch.object(DayOffScraperAdapter, "_scrape_calendar_requests")
    def test_get_absences_for_users_window_aggregates_days(
        self, mock_scrape_calendar_requests: Mock
    ) -> None:
        mock_scrape_calendar_requests.return_value = [
            {
                "Name": "John Wick",
                "FromDateFormated": "2026-10-13",
                "ToDateFormated": "2026-10-16",
            },
            {
                "Name": "Someone Else",
                "FromDateFormated": "2026-10-13",
                "ToDateFormated": "2026-10-15",
            },
        ]

        result = self.adapter.get_absences_for_users_window(
            full_names=["John Wick"],
            team_name="Sprint Team",
            start_date=date(2026, 10, 13),
            days_ahead=3,
        )

        self.assertEqual(result["team_name"], "Sprint Team")
        self.assertEqual(result["employees_count"], 1)
        self.assertEqual(
            result["employees_absences"][0]["absence_dates"],
            ["2026-10-13", "2026-10-14", "2026-10-15"],
        )


if __name__ == "__main__":
    unittest.main()
