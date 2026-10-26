import unittest

from models.fetch_mode import FetchMode


class TestFetchMode(unittest.TestCase):
    def test_from_env_requires_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "DAYOFF_FETCH_MODE is required"):
            FetchMode.from_env(None)
        with self.assertRaisesRegex(ValueError, "DAYOFF_FETCH_MODE is required"):
            FetchMode.from_env("")

    def test_from_env_parses_explicit_value(self) -> None:
        self.assertEqual(FetchMode.from_env("scraper"), FetchMode.SCRAPER)
        self.assertEqual(FetchMode.from_env("API"), FetchMode.API)

    def test_from_env_rejects_invalid_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid fetch mode"):
            FetchMode.from_env("invalid")


if __name__ == "__main__":
    unittest.main()
