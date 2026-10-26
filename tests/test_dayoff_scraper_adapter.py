import os
import sys
import types
import unittest
from datetime import date
from unittest.mock import Mock, patch

from dayoff.exceptions import ScraperError
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

    def test_date_range_returns_inclusive_days(self) -> None:
        result = self.adapter._date_range(date(2026, 10, 13), date(2026, 10, 15))
        self.assertEqual(
            [day.isoformat() for day in result],
            ["2026-10-13", "2026-10-14", "2026-10-15"],
        )

    def test_date_range_returns_empty_when_end_before_start(self) -> None:
        result = self.adapter._date_range(date(2026, 10, 15), date(2026, 10, 13))
        self.assertEqual(result, [])

    def test_stable_employee_fallback_id_is_deterministic(self) -> None:
        first = self.adapter._stable_employee_fallback_id("John Wick")
        second = self.adapter._stable_employee_fallback_id("John Wick")
        third = self.adapter._stable_employee_fallback_id("John Constantine")

        self.assertEqual(first, second)
        self.assertNotEqual(first, third)
        self.assertIsInstance(first, int)
        self.assertGreaterEqual(first, 0)

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

    @patch.object(DayOffScraperAdapter, "_scrape_calendar_requests")
    def test_get_absences_for_users_window_keeps_duplicate_names_separate_by_employee_id(
        self, mock_scrape_calendar_requests: Mock
    ) -> None:
        mock_scrape_calendar_requests.return_value = [
            {
                "EmployeeID": 101,
                "Name": "John Smith",
                "FromDateFormated": "2026-10-13",
                "ToDateFormated": "2026-10-14",
            },
            {
                "EmployeeID": 202,
                "Name": "John Smith",
                "FromDateFormated": "2026-10-14",
                "ToDateFormated": "2026-10-15",
            },
        ]

        result = self.adapter.get_absences_for_users_window(
            full_names=["John Smith"],
            start_date=date(2026, 10, 13),
            days_ahead=3,
        )

        self.assertEqual(result["employees_count"], 2)
        self.assertEqual(len(result["employees_absences"]), 2)
        employee_ids = sorted(
            [entry["employee_id"] for entry in result["employees_absences"]]
        )
        self.assertEqual(employee_ids, [101, 202])
        id_to_dates = {
            entry["employee_id"]: entry["absence_dates"]
            for entry in result["employees_absences"]
        }
        self.assertEqual(id_to_dates[101], ["2026-10-13"])
        self.assertEqual(id_to_dates[202], ["2026-10-14"])

    def test_scrape_calendar_requests_fallback_fetches_each_month(self) -> None:
        class FakePage:
            def set_default_timeout(self, _timeout):
                return None

            def on(self, _event, _handler):
                return None

            def goto(self, _url, wait_until=None, timeout=None):
                return None

            def wait_for_timeout(self, _ms):
                return None

            def wait_for_response(self, _predicate, timeout=None):
                raise RuntimeError("No network response captured in test")

            def evaluate(self, _script):
                return []

        class FakeBrowser:
            def __init__(self, page):
                self._page = page

            def new_page(self):
                return self._page

            def close(self):
                return None

        class FakePlaywright:
            def __init__(self, page):
                self.chromium = self
                self._page = page

            def launch(self, headless=True, args=None):
                return FakeBrowser(self._page)

        class FakeSyncPlaywright:
            def __init__(self, page):
                self._page = page

            def __enter__(self):
                return FakePlaywright(self._page)

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

        fake_page = FakePage()

        def fake_sync_playwright():
            return FakeSyncPlaywright(fake_page)

        fake_sync_api_module = types.ModuleType("playwright.sync_api")
        fake_sync_api_module.sync_playwright = fake_sync_playwright
        fake_sync_api_module.Error = RuntimeError

        fake_playwright_pkg = types.ModuleType("playwright")
        fake_playwright_pkg.sync_api = fake_sync_api_module

        def fallback_payload_for_month(_page, request_payload):
            month = request_payload["Month"]
            day = "2026-10-30" if month == 10 else "2026-11-02"
            return {
                "AcceptedRequests": [
                    {
                        "Name": f"User-{month}",
                        "FromDateFormated": day,
                        "ToDateFormated": day,
                    }
                ]
            }

        with (
            patch.dict(
                sys.modules,
                {
                    "playwright": fake_playwright_pkg,
                    "playwright.sync_api": fake_sync_api_module,
                },
            ),
            patch.object(self.adapter, "_login"),
            patch.object(
                self.adapter,
                "_calendar_payload_candidates",
                side_effect=lambda year, month: [{"Year": year, "Month": month}],
            ),
            patch.object(
                self.adapter,
                "_fetch_calendar_events_payload",
                side_effect=fallback_payload_for_month,
            ) as mock_fallback_fetch,
        ):
            requests = self.adapter._scrape_calendar_requests([(2026, 10), (2026, 11)])

        self.assertEqual(len(requests), 2)
        self.assertEqual(mock_fallback_fetch.call_count, 2)
        months_fetched = [
            call.args[1]["Month"] for call in mock_fallback_fetch.call_args_list
        ]
        self.assertEqual(months_fetched, [10, 11])

    def test_scrape_calendar_requests_fallback_only_for_months_without_usable_capture(
        self,
    ) -> None:
        class FakeResponse:
            def __init__(self, url: str, payload: dict):
                self.url = url
                self._payload = payload

            def json(self):
                return self._payload

        class FakePage:
            def __init__(self):
                self._on_response = None
                self._goto_calls = 0

            def set_default_timeout(self, _timeout):
                return None

            def on(self, event, handler):
                if event == "response":
                    self._on_response = handler

            def goto(self, _url, wait_until=None, timeout=None):
                self._goto_calls += 1
                # 1st goto = dashboard load, 2nd = first month, 3rd = second month
                if self._goto_calls == 2 and self._on_response is not None:
                    self._on_response(
                        FakeResponse(
                            "https://tracker.day-off.app/Dayoff/api/Companies/GetCalendarEvents",
                            {
                                "AcceptedRequests": [
                                    {
                                        "Name": "User-10",
                                        "FromDateFormated": "2026-10-30",
                                        "ToDateFormated": "2026-10-31",
                                    }
                                ]
                            },
                        )
                    )
                return None

            def wait_for_timeout(self, _ms):
                return None

            def wait_for_response(self, _predicate, timeout=None):
                return None

            def evaluate(self, _script):
                return []

        class FakeBrowser:
            def __init__(self, page):
                self._page = page

            def new_page(self):
                return self._page

            def close(self):
                return None

        class FakePlaywright:
            def __init__(self, page):
                self.chromium = self
                self._page = page

            def launch(self, headless=True, args=None):
                return FakeBrowser(self._page)

        class FakeSyncPlaywright:
            def __init__(self, page):
                self._page = page

            def __enter__(self):
                return FakePlaywright(self._page)

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

        fake_page = FakePage()
        fake_sync_api_module = types.ModuleType("playwright.sync_api")
        fake_sync_api_module.sync_playwright = lambda: FakeSyncPlaywright(fake_page)
        fake_sync_api_module.Error = RuntimeError
        fake_playwright_pkg = types.ModuleType("playwright")
        fake_playwright_pkg.sync_api = fake_sync_api_module

        def fallback_payload_for_month(_page, request_payload):
            month = request_payload["Month"]
            return {
                "AcceptedRequests": [
                    {
                        "Name": f"User-{month}",
                        "FromDateFormated": "2026-11-02",
                        "ToDateFormated": "2026-11-03",
                    }
                ]
            }

        with (
            patch.dict(
                sys.modules,
                {
                    "playwright": fake_playwright_pkg,
                    "playwright.sync_api": fake_sync_api_module,
                },
            ),
            patch.object(self.adapter, "_login"),
            patch.object(
                self.adapter,
                "_calendar_payload_candidates",
                side_effect=lambda year, month: [{"Year": year, "Month": month}],
            ),
            patch.object(
                self.adapter,
                "_fetch_calendar_events_payload",
                side_effect=fallback_payload_for_month,
            ) as mock_fallback_fetch,
        ):
            requests = self.adapter._scrape_calendar_requests([(2026, 10), (2026, 11)])

        self.assertEqual(len(requests), 2)
        self.assertEqual(mock_fallback_fetch.call_count, 1)
        self.assertEqual(mock_fallback_fetch.call_args.args[1]["Month"], 11)

    def test_scrape_calendar_requests_wraps_playwright_error_as_scraper_error(
        self,
    ) -> None:
        class FakePlaywrightError(Exception):
            pass

        class FakeChromium:
            @staticmethod
            def launch(headless=True, args=None):
                raise FakePlaywrightError("Timeout exceeded")

        class FakePlaywright:
            chromium = FakeChromium()

        class FakeSyncPlaywright:
            def __enter__(self):
                return FakePlaywright()

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

        fake_sync_api_module = types.ModuleType("playwright.sync_api")
        fake_sync_api_module.sync_playwright = lambda: FakeSyncPlaywright()
        fake_sync_api_module.Error = FakePlaywrightError

        fake_playwright_pkg = types.ModuleType("playwright")
        fake_playwright_pkg.sync_api = fake_sync_api_module

        with patch.dict(
            sys.modules,
            {
                "playwright": fake_playwright_pkg,
                "playwright.sync_api": fake_sync_api_module,
            },
        ):
            with self.assertRaises(ScraperError) as context:
                self.adapter._scrape_calendar_requests([(2026, 10)])

        self.assertIsNotNone(context.exception.__cause__)
        self.assertIsInstance(context.exception.__cause__, FakePlaywrightError)


if __name__ == "__main__":
    unittest.main()
