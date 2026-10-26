from enum import Enum


class FetchMode(str, Enum):
    API = "api"
    SCRAPER = "scraper"

    @classmethod
    def from_env(cls, raw_mode: str | None) -> "FetchMode":
        if raw_mode is None or not raw_mode.strip():
            raise ValueError(
                "DAYOFF_FETCH_MODE is required. Use DAYOFF_FETCH_MODE=api|scraper."
            )

        normalized = raw_mode.strip().lower()
        try:
            return cls(normalized)
        except ValueError as error:
            raise ValueError(
                "Invalid fetch mode. Use DAYOFF_FETCH_MODE=api|scraper."
            ) from error
