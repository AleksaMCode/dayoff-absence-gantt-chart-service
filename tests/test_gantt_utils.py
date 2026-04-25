import unittest
from datetime import date

from gantt.utils import (
    _build_filename,
    _group_dates_into_intervals,
    generate_absence_gantt,
)


class TestGanttUtils(unittest.TestCase):
    def test_generate_absence_gantt_returns_none_when_no_employees(self) -> None:
        payload = {
            "team_name": "Team 1",
            "window_start": "2026-04-21",
            "window_end": "2026-04-25",
            "employees_absences": [],
        }

        result = generate_absence_gantt(payload)

        self.assertIsNone(result)

    def test_generate_absence_gantt_returns_filename_and_png_bytes(self) -> None:
        payload = {
            "team_name": "Team 1",
            "window_start": "2026-04-21",
            "window_end": "2026-04-25",
            "employees_absences": [
                {
                    "employee_id": 1,
                    "name": "John Wick",
                    "absence_dates": ["2026-04-21", "2026-04-22"],
                },
                {
                    "employee_id": 2,
                    "name": "John Constantine",
                    "absence_dates": ["2026-04-24"],
                },
            ],
        }

        result = generate_absence_gantt(payload)

        self.assertIsInstance(result, dict)
        self.assertIn("chart_file_name", result)
        self.assertIn("chart_bytes", result)
        self.assertTrue(result["chart_file_name"].startswith("absence-gantt-team-1-"))
        self.assertTrue(result["chart_file_name"].endswith(".png"))
        self.assertGreater(len(result["chart_bytes"]), 1000)

    def test_generate_absence_gantt_smoke_png_signature(self) -> None:
        # Smoke test
        payload = {
            "team_name": None,
            "window_start": "2026-04-21",
            "window_end": "2026-04-25",
            "employees_absences": [
                {
                    "employee_id": 100,
                    "name": "Smoke User",
                    "absence_dates": ["2026-04-21", "2026-04-23", "2026-04-24"],
                }
            ],
        }

        result = generate_absence_gantt(payload)

        self.assertIsNotNone(result)
        png_bytes = result["chart_bytes"]
        self.assertTrue(
            png_bytes.startswith(b"\x89PNG\r\n\x1a\n"),
            "Generated chart should be a valid PNG stream.",
        )

    def test_group_dates_into_intervals_merges_and_splits_correctly(self) -> None:
        intervals = _group_dates_into_intervals(
            [
                date(2026, 4, 21),
                date(2026, 4, 22),
                date(2026, 4, 22),
                date(2026, 4, 24),
                date(2026, 4, 25),
            ]
        )

        self.assertEqual(
            intervals,
            [
                (date(2026, 4, 21), date(2026, 4, 22)),
                (date(2026, 4, 24), date(2026, 4, 25)),
            ],
        )

    def test_build_filename_format(self) -> None:
        file_name = _build_filename("Team 1", date(2026, 4, 21), date(2026, 4, 25))

        self.assertRegex(
            file_name,
            r"^absence-gantt-team-1-2026-04-21-2026-04-25-\d{14}\.png$",
        )

    def test_build_filename_defaults_to_all_teams(self) -> None:
        file_name = _build_filename(None, date(2026, 4, 21), date(2026, 4, 25))
        self.assertTrue(file_name.startswith("absence-gantt-all-teams-"))


if __name__ == "__main__":
    unittest.main()
