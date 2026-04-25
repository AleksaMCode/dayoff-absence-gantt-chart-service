import json
import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set

import requests
from dotenv import load_dotenv
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_exponential

from dayoff.endpoints import Endpoints
from logger.utils import get_logger

load_dotenv()
logger = get_logger(__name__)


class DayOffAdapter:
    def __init__(self):
        self._api_key = os.getenv("DAYOFF_API_KEY")
        self._base_url = os.getenv(
            "DAYOFF_BASE_URL", "https://tracker.day-off.app/Dayoff"
        ).rstrip("/")
        self._timeout = int(os.getenv("DAYOFF_TIMEOUT_SECONDS", "30"))
        if not self._api_key:
            raise ValueError("DAYOFF_API_KEY is not configured.")

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "accept": "application/json",
        }

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.ERROR),
        reraise=True,
    )
    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self._base_url}{endpoint}"
        response = requests.get(
            url, headers=self._headers, params=params, timeout=self._timeout
        )
        response.raise_for_status()
        return response.json()

    def get_teams(self) -> List[Dict[str, Any]]:
        response = self._get(Endpoints.TEAMS)
        if isinstance(response, list):
            return response
        return []

    def resolve_team_id(self, team_name: str) -> int:
        normalized_name = team_name.strip().lower()
        for team in self.get_teams():
            candidate_name = str(team.get("TeamName", "")).strip().lower()
            if candidate_name == normalized_name:
                team_id = team.get("TeamID")
                if team_id is None:
                    continue
                return int(team_id)
        raise ValueError(f"Team '{team_name}' was not found in DayOff teams list.")

    def resolve_team_name(self, team_id: int) -> str:
        for team in self.get_teams():
            candidate_team_id = team.get("TeamID")
            if candidate_team_id is None:
                continue
            if int(candidate_team_id) == int(team_id):
                candidate_name = str(team.get("TeamName", "")).strip()
                if candidate_name:
                    return candidate_name
        raise ValueError(f"Team id '{team_id}' was not found in DayOff teams list.")

    def get_all_employees(self, page_size: int = 100) -> List[Dict[str, Any]]:
        employees: List[Dict[str, Any]] = []
        page_number = 1

        while True:
            payload = self._get(
                Endpoints.EMPLOYEES,
                params={"pageNumber": page_number, "limit": page_size},
            )
            if not isinstance(payload, dict):
                break

            page_results = payload.get("Results", [])
            if not isinstance(page_results, list) or not page_results:
                break

            employees.extend(page_results)

            total = payload.get("Total")
            if isinstance(total, int) and len(employees) >= total:
                break

            page_number += 1

        return employees

    def resolve_employee_ids_by_email_usernames(
        self, email_usernames: List[str]
    ) -> Dict[int, str]:
        normalized_targets = {
            username.strip().lower()
            for username in email_usernames
            if username and username.strip()
        }
        if not normalized_targets:
            return {}

        matched: Dict[int, str] = {}
        for employee in self.get_all_employees():
            employee_id = employee.get("EmployeeID")
            if employee_id is None:
                continue

            email = str(employee.get("Email") or "").strip().lower()
            if not email:
                continue
            email_username = self._email_username(email)
            if email_username not in normalized_targets:
                continue

            matched[int(employee_id)] = str(
                employee.get("Name") or f"Employee-{employee_id}"
            )

        return matched

    def get_employee_leave_requests(self, employee_id: int) -> List[Dict[str, Any]]:
        payload = self._get(Endpoints.LEAVE_REQUESTS.format(employee_id=employee_id))
        if not isinstance(payload, dict):
            return []

        history = payload.get("History", [])
        if not isinstance(history, list):
            return []

        accepted = []
        for request in history:
            if not isinstance(request, dict):
                continue
            status_id = request.get("StatusID")
            status_name = str(request.get("StatusName") or "").strip().lower()
            if status_id == 2 or status_name == "accepted":
                accepted.append(request)
        return accepted

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.ERROR),
        reraise=True,
    )
    def get_absences_by_month(
        self,
        year: int,
        month: int,
        team: Optional[str] = None,
        team_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        if team_id is not None:
            resolved_team_id = team_id
        elif team is not None:
            resolved_team_id = self.resolve_team_id(team)
        else:
            resolved_team_id = None
        filter_payload: Dict[str, Any] = {
            "Year": year,
            "Month": month,
        }
        if resolved_team_id is not None:
            filter_payload["TeamIds"] = [resolved_team_id]
        logger.info(
            f"Fetching absences for team '{team}' ({resolved_team_id}) in {year}-{month}."
        )
        response = self._get(
            Endpoints.EVENTS_BY_MONTH,
            params={"filter": json.dumps(filter_payload, separators=(",", ":"))},
        )
        return response if isinstance(response, dict) else {}

    def get_absences_for_window(
        self,
        team: Optional[str] = None,
        team_id: Optional[int] = None,
        start_date: Optional[date] = None,
        days_ahead: int = 5,
    ) -> Dict[str, Any]:
        start = start_date or date.today()
        end = start + timedelta(days=days_ahead - 1)

        months_to_fetch = {(start.year, start.month), (end.year, end.month)}
        accepted_requests: List[Dict[str, Any]] = []
        resolved_team_id = team_id
        if resolved_team_id is None and team is not None:
            resolved_team_id = self.resolve_team_id(team)
        resolved_team_name = team
        if resolved_team_name is None and resolved_team_id is not None:
            resolved_team_name = self.resolve_team_name(resolved_team_id)

        for year, month in sorted(months_to_fetch):
            monthly_payload = self.get_absences_by_month(
                year=year, month=month, team=team, team_id=resolved_team_id
            )
            results = (
                monthly_payload.get("Results", {})
                if isinstance(monthly_payload, dict)
                else {}
            )
            accepted_requests.extend(results.get("AcceptedRequests", []))

        return self._build_window_response(
            accepted_requests=accepted_requests,
            start=start,
            end=end,
            team_name=resolved_team_name,
            team_id=resolved_team_id,
        )

    def get_absences_for_users_window(
        self,
        email_usernames: List[str],
        team_name: Optional[str] = None,
        start_date: Optional[date] = None,
        days_ahead: int = 5,
    ) -> Dict[str, Any]:
        start = start_date or date.today()
        end = start + timedelta(days=days_ahead - 1)

        selected_employees = self.resolve_employee_ids_by_email_usernames(
            email_usernames
        )
        accepted_requests: List[Dict[str, Any]] = []

        for employee_id in selected_employees.keys():
            accepted_requests.extend(self.get_employee_leave_requests(employee_id))

        return self._build_window_response(
            accepted_requests=accepted_requests,
            start=start,
            end=end,
            team_name=team_name,
            team_id=None,
        )

    def _build_window_response(
        self,
        accepted_requests: List[Dict[str, Any]],
        start: date,
        end: date,
        team_name: Optional[str],
        team_id: Optional[int],
    ) -> Dict[str, Any]:
        employee_absence_map: Dict[int, Dict[str, Any]] = {}
        for request in accepted_requests:
            date_range = self._extract_request_date_range(request)
            if date_range is None:
                continue
            from_dt, to_dt_inclusive = date_range

            if from_dt > end or to_dt_inclusive < start:
                continue

            employee_id = request.get("EmployeeID")
            if employee_id is None:
                continue

            employee_name = (
                request.get("Name")
                or request.get("EmployeeName")
                or f"Employee-{employee_id}"
            )
            employee_entry = employee_absence_map.setdefault(
                int(employee_id),
                {
                    "employee_id": int(employee_id),
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
            "team_id": team_id,
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
    def _email_username(email: str) -> str:
        return email.split("@", 1)[0].strip().lower()

    @staticmethod
    def _extract_request_date_range(
        request: Dict[str, Any],
    ) -> Optional[tuple[date, date]]:
        from_date_formatted = request.get("FromDateFormated")
        to_date_formatted = request.get("ToDateFormated")

        # Calendar/month endpoint: *Formated fields are present and ToDateFormated is end-exclusive.
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

        # Employee leaveRequests endpoint: use FromDate/ToDate and compare by date only.
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
