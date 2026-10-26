import os
import zlib
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from dotenv import load_dotenv

from logger.utils import get_logger

load_dotenv()
logger = get_logger(__name__)


class DayOffScraperAdapter:
    def __init__(self):
        self._base_url = os.getenv(
            "DAYOFF_SCRAPER_BASE_URL", "https://tracker.day-off.app"
        )
        self._login_url = os.getenv(
            "DAYOFF_SCRAPER_LOGIN_URL", "https://tracker.day-off.app/auth/login"
        )
        self._calendar_url = os.getenv(
            "DAYOFF_SCRAPER_CALENDAR_URL", f"{self._base_url.rstrip('/')}/dashboard"
        )
        self._email = os.getenv("DAYOFF_SCRAPER_EMAIL")
        self._password = os.getenv("DAYOFF_SCRAPER_PASSWORD")
        self._headless = os.getenv("DAYOFF_SCRAPER_HEADLESS", "true").lower() == "true"
        self._timeout_ms = int(os.getenv("DAYOFF_SCRAPER_TIMEOUT_SECONDS", "30")) * 1000
        self._calendar_events_endpoint = "/Dayoff/api/Companies/GetCalendarEvents"

        if not self._email:
            raise ValueError("DAYOFF_SCRAPER_EMAIL is not configured.")
        if not self._password:
            raise ValueError("DAYOFF_SCRAPER_PASSWORD is not configured.")

    def get_absences_for_users_window(
        self,
        full_names: List[str],
        team_name: Optional[str] = None,
        start_date: Optional[date] = None,
        days_ahead: int = 5,
    ) -> Dict[str, Any]:
        start = start_date or date.today()
        if days_ahead <= 0:
            return {
                "team_name": team_name,
                "team_id": None,
                "window_start": start.isoformat(),
                "window_end": start.isoformat(),
                "employees_count": 0,
                "employees_absences": [],
            }
        end = start + timedelta(days=days_ahead - 1)
        months_to_fetch = {(start.year, start.month), (end.year, end.month)}

        accepted_requests: List[Dict[str, Any]] = self._scrape_calendar_requests(
            sorted(months_to_fetch)
        )
        filtered_requests = self._filter_requests_by_full_names(
            accepted_requests, full_names
        )
        return self._build_window_response(
            accepted_requests=filtered_requests,
            full_names=full_names,
            start=start,
            end=end,
            team_name=team_name,
        )

    def _scrape_calendar_requests(
        self, months_to_fetch: List[tuple[int, int]]
    ) -> List[Dict[str, Any]]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise RuntimeError(
                "Playwright is not installed. Install dependencies and run 'playwright install chromium'."
            ) from error

        captured_requests: List[Dict[str, Any]] = []
        observed_relevant_urls: Set[str] = set()

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=self._headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = browser.new_page()
            page.set_default_timeout(self._timeout_ms)

            def on_response(response):
                try:
                    response_url = response.url
                    if self._calendar_events_endpoint not in response_url and (
                        "calendar" not in response_url and "events" not in response_url
                    ):
                        return
                    observed_relevant_urls.add(response_url)
                    payload = response.json()
                except Exception:
                    return

                parsed_requests = self._extract_requests_from_payload(payload)
                if parsed_requests:
                    captured_requests.extend(parsed_requests)

            page.on("response", on_response)
            self._login(page)

            # Dashboard load usually triggers GetCalendarEvents requests.
            dashboard_url = f"{self._calendar_url}?v={datetime.utcnow().timestamp()}"
            page.goto(
                dashboard_url, wait_until="domcontentloaded", timeout=self._timeout_ms
            )
            page.wait_for_timeout(2000)

            for year, month in months_to_fetch:
                # Keep a deterministic refresh cycle so SPA emits data requests.
                cycle_url = (
                    f"{self._calendar_url}?year={year}&month={month}"
                    f"&v={datetime.utcnow().timestamp()}"
                )
                page.goto(
                    cycle_url, wait_until="domcontentloaded", timeout=self._timeout_ms
                )
                try:
                    page.wait_for_response(
                        lambda response: self._calendar_events_endpoint in response.url
                        and response.status == 200,
                        timeout=self._timeout_ms,
                    )
                except Exception:
                    # Fallback path below will try DOM extraction if API payloads are missing.
                    pass
                page.wait_for_timeout(1500)

            if not captured_requests:
                # Fallback: actively call calendar endpoint from authenticated page context.
                for year, month in months_to_fetch:
                    for request_payload in self._calendar_payload_candidates(
                        year, month
                    ):
                        payload = self._fetch_calendar_events_payload(
                            page, request_payload
                        )
                        parsed_requests = self._extract_requests_from_payload(payload)
                        if parsed_requests:
                            captured_requests.extend(parsed_requests)
                            break

            if not captured_requests:
                captured_requests = self._extract_from_calendar_dom(page)

            browser.close()

        if not captured_requests:
            observed_suffix = ""
            if observed_relevant_urls:
                preview = sorted(observed_relevant_urls)[:8]
                observed_suffix = f" Observed relevant response URLs: {preview}."
            raise ValueError(
                "No calendar requests were scraped from Day Off." + observed_suffix
            )

        return captured_requests

    def _login(self, page) -> None:
        page.goto(
            self._login_url, wait_until="domcontentloaded", timeout=self._timeout_ms
        )
        page.wait_for_timeout(1500)
        email_selector = (
            "input[data-cy='UserExistsRequestDTO.Username'],"
            "input[name='username'],"
            "input[type='email'],"
            "input[name='email'],"
            "input[placeholder*='Email'],"
            "input[placeholder*='Phone']"
        )
        try:
            page.wait_for_selector(
                email_selector, state="visible", timeout=self._timeout_ms
            )
        except Exception:
            # Retry once for slow Angular boot in constrained container environments.
            page.reload(wait_until="domcontentloaded", timeout=self._timeout_ms)
            page.wait_for_timeout(1500)

        email_input = self._first_locator(
            page,
            [
                "input[data-cy='UserExistsRequestDTO.Username']",
                "input[name='username']",
                "input[type='email']",
                "input[name='email']",
                "input[placeholder*='Email']",
                "input[placeholder*='Phone']",
            ],
        )
        if email_input is None:
            raise ValueError(
                "Could not locate email field on Day Off login page. "
                f"Current URL: {page.url}. Page title: {page.title()}."
            )
        email_input.fill(self._email)
        self._click_first(
            page,
            [
                "#m_login_signin_submit",
                "button[data-cy='login_signin']",
                "button:has-text('Continue')",
                "button:has-text('Sign in')",
                "button:has-text('Sign In')",
                "button:has-text('Next')",
            ],
        )

        page.wait_for_timeout(700)
        password_selector = (
            "input[type='password'],"
            "input[name='password'],"
            "input[placeholder*='Password'],"
            "m-password-field input"
        )
        page.wait_for_selector(
            password_selector, state="visible", timeout=self._timeout_ms
        )
        password_input = self._first_locator(
            page,
            [
                "input[type='password']",
                "input[name='password']",
                "m-password-field input",
                "input[placeholder*='Password']",
            ],
        )
        if password_input is None:
            raise ValueError("Could not locate password field on Day Off login page.")
        password_input.fill(self._password)
        self._click_first(
            page,
            [
                "#m_login_signin_submit",
                "button[data-cy='login_signin']",
                "button:has-text('Sign in')",
                "button:has-text('Sign In')",
                "button:has-text('Login')",
                "button:has-text('Log in')",
            ],
        )

        page.wait_for_timeout(1200)
        try:
            page.wait_for_url("**/dashboard**", timeout=10_000)
        except Exception:
            # Some sessions do not auto-redirect after sign-in; force dashboard route.
            page.goto(
                self._calendar_url,
                wait_until="domcontentloaded",
                timeout=self._timeout_ms,
            )
            page.wait_for_timeout(1200)

        if "/auth/login" in page.url:
            visible_text = ""
            try:
                visible_text = page.locator("body").inner_text(timeout=2000)[:500]
            except Exception:
                visible_text = ""
            raise ValueError(
                "Day Off login failed; still on login page after sign in. "
                f"Current URL: {page.url}. "
                f"Visible text snippet: {visible_text!r}"
            )

    @staticmethod
    def _first_locator(page, selectors: List[str]):
        for selector in selectors:
            locator = page.locator(selector).first
            if locator.count() > 0:
                return locator
        return None

    @staticmethod
    def _click_first(page, selectors: List[str]) -> None:
        for selector in selectors:
            locator = page.locator(selector).first
            if locator.count() > 0:
                locator.click()
                return
        raise ValueError(f"Could not locate any clickable selector from: {selectors}")

    @staticmethod
    def _extract_requests_from_payload(payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, dict):
            results = payload.get("Results")
            if isinstance(results, dict):
                accepted = results.get("AcceptedRequests")
                if isinstance(accepted, list):
                    return [item for item in accepted if isinstance(item, dict)]
            accepted = payload.get("AcceptedRequests")
            if isinstance(accepted, list):
                return [item for item in accepted if isinstance(item, dict)]
        return []

    def _fetch_calendar_events_payload(
        self, page, request_payload: Dict[str, Any]
    ) -> Any:
        endpoint = f"{self._base_url.rstrip('/')}{self._calendar_events_endpoint}"
        try:
            return page.evaluate(
                """
async ({ endpoint, payload }) => {
  const response = await fetch(endpoint, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json, text/plain, */*",
    },
    body: JSON.stringify(payload),
  });

  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch (_error) {
    return { "__status": response.status, "__text": text };
  }
}
""",
                {"endpoint": endpoint, "payload": request_payload},
            )
        except Exception:
            return {}

    @staticmethod
    def _calendar_payload_candidates(year: int, month: int) -> List[Dict[str, Any]]:
        month_start = f"{year:04d}-{month:02d}-01"
        return [
            {"Year": year, "Month": month},
            {"year": year, "month": month},
            {"CurrentYear": year, "CurrentMonth": month},
            {"Date": month_start},
            {"date": month_start},
            {},
        ]

    def _extract_from_calendar_dom(self, page) -> List[Dict[str, Any]]:
        records = page.evaluate("""
() => {
  const nodes = Array.from(document.querySelectorAll('[data-employee-name][data-from-date][data-to-date]'));
  return nodes.map((node) => ({
    Name: node.getAttribute('data-employee-name') || '',
    FromDateFormated: node.getAttribute('data-from-date') || '',
    ToDateFormated: node.getAttribute('data-to-date') || '',
  }));
}
""")
        if isinstance(records, list):
            return [record for record in records if isinstance(record, dict)]
        return []

    @staticmethod
    def _filter_requests_by_full_names(
        accepted_requests: List[Dict[str, Any]], full_names: List[str]
    ) -> List[Dict[str, Any]]:
        exact_names = {name for name in full_names}
        filtered: List[Dict[str, Any]] = []
        for request in accepted_requests:
            employee_name = str(
                request.get("Name") or request.get("EmployeeName") or ""
            )
            if employee_name in exact_names:
                filtered.append(request)
        return filtered

    def _build_window_response(
        self,
        accepted_requests: List[Dict[str, Any]],
        full_names: List[str],
        start: date,
        end: date,
        team_name: Optional[str],
    ) -> Dict[str, Any]:
        employee_absence_map: Dict[str, Dict[str, Any]] = {}
        for request in accepted_requests:
            date_range = self._extract_request_date_range(request)
            if date_range is None:
                continue
            from_dt, to_dt_inclusive = date_range

            if from_dt > end or to_dt_inclusive < start:
                continue

            employee_name = str(
                request.get("Name") or request.get("EmployeeName") or ""
            )
            if employee_name not in full_names:
                continue

            employee_entry = employee_absence_map.setdefault(
                employee_name,
                {
                    "employee_id": request.get("EmployeeID")
                    or zlib.crc32(employee_name.encode("utf-8")),
                    "name": employee_name,
                    "absence_dates": set(),
                },
            )

            overlap_start = max(from_dt, start)
            overlap_end = min(to_dt_inclusive, end)
            for absence_day in self._date_range(overlap_start, overlap_end):
                casted_dates: Set[str] = employee_entry["absence_dates"]
                casted_dates.add(absence_day.isoformat())

        employees_absences = []
        for employee in employee_absence_map.values():
            employees_absences.append(
                {
                    "employee_id": employee["employee_id"],
                    "name": employee["name"],
                    "absence_dates": sorted(employee["absence_dates"]),
                }
            )

        employees_absences.sort(key=lambda item: item["name"])
        return {
            "team_name": team_name,
            "team_id": None,
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "employees_count": len(employees_absences),
            "employees_absences": employees_absences,
        }

    @staticmethod
    def _date_range(start: date, end: date) -> List[date]:
        if end < start:
            return []
        total_days = (end - start).days + 1
        return [start + timedelta(days=offset) for offset in range(total_days)]

    @staticmethod
    def _extract_request_date_range(
        request: Dict[str, Any],
    ) -> Optional[tuple[date, date]]:
        from_date_formatted = request.get("FromDateFormated")
        to_date_formatted = request.get("ToDateFormated")

        if from_date_formatted and to_date_formatted:
            try:
                from_dt = date.fromisoformat(str(from_date_formatted))
                to_dt = date.fromisoformat(str(to_date_formatted))
            except ValueError:
                return None

            to_dt_inclusive = to_dt - timedelta(days=1)
            if to_dt_inclusive < from_dt:
                to_dt_inclusive = from_dt
            return from_dt, to_dt_inclusive

        from_date_raw = request.get("FromDate")
        to_date_raw = request.get("ToDate")
        if not from_date_raw or not to_date_raw:
            return None

        try:
            from_dt = datetime.fromisoformat(
                str(from_date_raw).replace("Z", "+00:00")
            ).date()
            to_dt = datetime.fromisoformat(
                str(to_date_raw).replace("Z", "+00:00")
            ).date()
        except ValueError:
            return None

        if to_dt < from_dt:
            to_dt = from_dt
        return from_dt, to_dt
