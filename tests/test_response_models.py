import unittest

from models.responses import AbsenceWindowResponse, AbsenceWindowWithChartResponse


class TestResponseModels(unittest.TestCase):
    def test_absence_window_response_validates(self) -> None:
        model = AbsenceWindowResponse.model_validate(
            {
                "team_name": "Team 1",
                "team_id": 123,
                "window_start": "2026-10-13",
                "window_end": "2026-10-17",
                "employees_count": 1,
                "employees_absences": [
                    {
                        "employee_id": 42,
                        "name": "John Wick",
                        "absence_dates": ["2026-10-14"],
                    }
                ],
            }
        )
        self.assertEqual(model.employees_count, 1)
        self.assertEqual(model.employees_absences[0].name, "John Wick")

    def test_absence_window_with_chart_response_validates(self) -> None:
        model = AbsenceWindowWithChartResponse.model_validate(
            {
                "team_name": "Team 1",
                "team_id": 123,
                "window_start": "2026-10-13",
                "window_end": "2026-10-17",
                "employees_count": 0,
                "employees_absences": [],
                "chart_file_name": "chart.png",
                "sharepoint_file_url": "https://contoso.local/chart.png",
            }
        )
        self.assertEqual(model.chart_file_name, "chart.png")


if __name__ == "__main__":
    unittest.main()
