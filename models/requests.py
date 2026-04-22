from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class GetAbsencesRequest(BaseModel):
    team_name: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Exact DayOff team name. If omitted, fetches all teams.",
    )
    team_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="Exact DayOff team id. If omitted, fetches all teams.",
    )
    email_usernames: Optional[List[str]] = Field(
        default=None,
        description="Optional list of email usernames (part before @) used to select employees.",
    )
    days_ahead: int = Field(
        default=5, ge=0, le=30, description="Window size from today."
    )

    @model_validator(mode="after")
    def validate_team_selector(self):
        if self.team_name is not None and self.team_id is not None:
            raise ValueError("Provide either team_name or team_id, not both.")
        if self.email_usernames and self.team_id is not None:
            raise ValueError("team_id cannot be used with email_usernames.")
        return self
