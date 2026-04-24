import json
import os
import unittest
from datetime import date
from unittest.mock import Mock, patch

from dayoff_adapter.dayoff_adapter import DayOffAdapter


class TestDayOffAdapter(unittest.TestCase):
    def setUp(self) -> None:
        self.env_patcher = patch.dict(
            os.environ,
            {
                "DAYOFF_API_KEY": "test-api-key",
                "DAYOFF_BASE_URL": "https://tracker.day-off.app/Dayoff",
                "DAYOFF_TIMEOUT_SECONDS": "30",
            },
            clear=False,
        )
        self.env_patcher.start()
        self.adapter = DayOffAdapter()

    def tearDown(self) -> None:
        self.env_patcher.stop()

    def test_init_raises_when_api_key_missing(self) -> None:
        with patch.dict(os.environ, {"DAYOFF_API_KEY": ""}, clear=False):
            with self.assertRaisesRegex(
                ValueError, "DAYOFF_API_KEY is not configured."
            ):
                DayOffAdapter()

    @patch.object(DayOffAdapter, "get_teams")
    def test_resolve_team_id_is_case_insensitive(self, mock_get_teams: Mock) -> None:
        mock_get_teams.return_value = [{"TeamID": 12954, "TeamName": "Team 1"}]

        team_id = self.adapter.resolve_team_id("  team 1 ")

        self.assertEqual(team_id, 12954)

    @patch.object(DayOffAdapter, "_get")
    def test_get_absences_by_month_without_team_filter(self, mock_get: Mock) -> None:
        mock_get.return_value = {}

        self.adapter.get_absences_by_month(year=2026, month=4)

        called_endpoint = mock_get.call_args.args[0]
        called_params = mock_get.call_args.kwargs["params"]
        filter_payload = json.loads(called_params["filter"])

        self.assertEqual(called_endpoint, "/api/doc/calendar/events/by-month")
        self.assertEqual(filter_payload, {"Year": 2026, "Month": 4})

    @patch.object(DayOffAdapter, "_get")
    def test_get_absences_by_month_with_team_id_filter(self, mock_get: Mock) -> None:
        mock_get.return_value = {}

        self.adapter.get_absences_by_month(year=2026, month=4, team_id=777)

        called_params = mock_get.call_args.kwargs["params"]
        filter_payload = json.loads(called_params["filter"])
        self.assertEqual(filter_payload, {"Year": 2026, "Month": 4, "TeamIds": [777]})

    @patch.object(DayOffAdapter, "get_absences_by_month")
    def test_get_absences_for_window_aggregates_per_employee(
        self, mock_by_month: Mock
    ) -> None:
        mock_by_month.return_value = {
            "Results": {
                "AcceptedRequests": [
                    {
                        "EmployeeID": 1,
                        "Name": "John Constantine",
                        "FromDateFormated": "2026-04-21",
                        "ToDateFormated": "2026-04-23",  # end-exclusive -> 21,22
                    },
                    {
                        "EmployeeID": 1,
                        "Name": "John Wick",
                        "FromDateFormated": "2026-04-22",
                        "ToDateFormated": "2026-04-26",  # end-exclusive -> 22..25
                    },
                    {
                        "EmployeeID": 2,
                        "Name": "John Wick",
                        "FromDateFormated": "2026-04-24",
                        "ToDateFormated": "2026-04-25",  # end-exclusive -> 24
                    },
                    {
                        "EmployeeID": 3,
                        "Name": "Johnny Mnemonic",
                        "FromDateFormated": "2026-04-30",
                        "ToDateFormated": "2026-05-01",
                    },
                ]
            }
        }

        result = self.adapter.get_absences_for_window(
            start_date=date(2026, 4, 21),
            days_ahead=5,
        )

        self.assertEqual(result["window_start"], "2026-04-21")
        self.assertEqual(result["window_end"], "2026-04-25")
        self.assertEqual(result["employees_count"], 2)

        self.assertEqual(
            result["employees_absences"],
            [
                {
                    "employee_id": 1,
                    "name": "John Constantine",
                    "absence_dates": [
                        "2026-04-21",
                        "2026-04-22",
                        "2026-04-23",
                        "2026-04-24",
                        "2026-04-25",
                    ],
                },
                {
                    "employee_id": 2,
                    "name": "John Wick",
                    "absence_dates": ["2026-04-24"],
                },
            ],
        )

    @patch.object(DayOffAdapter, "get_employee_leave_requests")
    @patch.object(DayOffAdapter, "resolve_employee_ids_by_email_usernames")
    def test_get_absences_for_users_window_uses_employee_requests(
        self,
        mock_resolve_employee_ids: Mock,
        mock_get_leave_requests: Mock,
    ) -> None:
        mock_resolve_employee_ids.return_value = {10: "A", 20: "B"}
        mock_get_leave_requests.side_effect = [
            [
                {
                    "EmployeeID": 10,
                    "EmployeeName": "A",
                    "FromDate": "2026-04-23T00:00:00",
                    "ToDate": "2026-04-23T00:00:00",
                }
            ],
            [
                {
                    "EmployeeID": 20,
                    "EmployeeName": "B",
                    "FromDate": "2026-04-24T00:00:00",
                    "ToDate": "2026-04-24T00:00:00",
                }
            ],
        ]

        result = self.adapter.get_absences_for_users_window(
            email_usernames=["a", "b"],
            team_name="A Team",
            start_date=date(2026, 4, 23),
            days_ahead=3,
        )

        self.assertEqual(result["team_name"], "A Team")
        self.assertEqual(result["employees_count"], 2)
        self.assertEqual(mock_get_leave_requests.call_count, 2)
        self.assertEqual(mock_get_leave_requests.call_args_list[0].args[0], 10)
        self.assertEqual(mock_get_leave_requests.call_args_list[1].args[0], 20)

    @patch.object(DayOffAdapter, "get_all_employees")
    def test_resolve_employee_ids_by_email_usernames(
        self, mock_get_all_employees: Mock
    ) -> None:
        mock_get_all_employees.return_value = [
            {"EmployeeID": 1, "Name": "John", "Email": "john@example.com"},
            {"EmployeeID": 2, "Name": "Jane", "Email": "jane@example.com"},
            {"EmployeeID": 3, "Name": "NoEmail", "Email": None},
        ]

        result = self.adapter.resolve_employee_ids_by_email_usernames(
            ["JOHN", "  jane  ", "", "unknown"]
        )

        self.assertEqual(result, {1: "John", 2: "Jane"})

    @patch.object(DayOffAdapter, "_get")
    def test_get_employee_leave_requests_filters_only_accepted(
        self, mock_get: Mock
    ) -> None:
        mock_get.return_value = {
            "History": [
                {"LeaveRequestID": 1, "StatusID": 2, "EmployeeID": 11},
                {"LeaveRequestID": 2, "StatusID": 1, "EmployeeID": 11},
                {"LeaveRequestID": 3, "StatusName": "Accepted", "EmployeeID": 11},
                {"LeaveRequestID": 4, "StatusName": "Rejected", "EmployeeID": 11},
            ]
        }

        requests = self.adapter.get_employee_leave_requests(employee_id=11)
        request_ids = [item["LeaveRequestID"] for item in requests]

        self.assertEqual(request_ids, [1, 3])


if __name__ == "__main__":
    unittest.main()
