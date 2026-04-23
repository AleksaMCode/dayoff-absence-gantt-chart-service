import unittest

from pydantic import ValidationError

from models.requests import GetAbsencesRequest


class TestGetAbsencesRequestModel(unittest.TestCase):
    def test_allows_team_name_only(self) -> None:
        payload = GetAbsencesRequest(team_name="Engineering")
        self.assertEqual(payload.team_name, "Engineering")
        self.assertIsNone(payload.team_id)
        self.assertEqual(payload.days_ahead, 5)

    def test_allows_team_id_only(self) -> None:
        payload = GetAbsencesRequest(team_id=12954, days_ahead=7)
        self.assertEqual(payload.team_id, 12954)
        self.assertIsNone(payload.team_name)
        self.assertEqual(payload.days_ahead, 7)

    def test_allows_both_team_selectors_omitted(self) -> None:
        payload = GetAbsencesRequest(days_ahead=3)
        self.assertIsNone(payload.team_name)
        self.assertIsNone(payload.team_id)
        self.assertEqual(payload.days_ahead, 3)

    def test_rejects_team_name_and_team_id_together(self) -> None:
        with self.assertRaisesRegex(
            ValidationError, "Provide either team_name or team_id, not both."
        ):
            GetAbsencesRequest(team_name="Engineering", team_id=12954)

    def test_allows_email_usernames_without_team_id(self) -> None:
        payload = GetAbsencesRequest(
            team_name="Custom Label",
            email_usernames=["john", "wick"],
            days_ahead=5,
        )
        self.assertEqual(payload.email_usernames, ["john", "wick"])
        self.assertEqual(payload.team_name, "Custom Label")
        self.assertIsNone(payload.team_id)

    def test_rejects_email_usernames_with_team_id(self) -> None:
        with self.assertRaisesRegex(
            ValidationError, "team_id cannot be used with email_usernames."
        ):
            GetAbsencesRequest(email_usernames=["john"], team_id=12954)

    def test_rejects_invalid_days_ahead(self) -> None:
        with self.assertRaises(ValidationError):
            GetAbsencesRequest(days_ahead=31)


if __name__ == "__main__":
    unittest.main()
