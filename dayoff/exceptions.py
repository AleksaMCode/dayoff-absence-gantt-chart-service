class ScraperError(RuntimeError):
    """Raised when Day Off scraping fails due to upstream/auth/page issues."""


class ScraperLookupError(ScraperError):
    """Raised when requested data is genuinely not found."""
