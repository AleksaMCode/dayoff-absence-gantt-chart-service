from typing import List, Optional

from pydantic import BaseModel, Field


class EmployeeAbsence(BaseModel):
    employee_id: int = Field(..., description="Unique employee identifier.")
    name: str = Field(..., min_length=1, description="Employee display name.")
    absence_dates: List[str] = Field(
        ..., description="List of ISO dates where employee is absent."
    )


class AbsenceWindowResponse(BaseModel):
    team_name: Optional[str] = Field(
        default=None,
        description="Team label used for response/chart context.",
    )
    team_id: Optional[int] = Field(
        default=None,
        description="Team id when available from source.",
    )
    window_start: str = Field(..., description="Window start date (ISO).")
    window_end: str = Field(..., description="Window end date (ISO).")
    employees_count: int = Field(..., ge=0, description="Employees with absences.")
    employees_absences: List[EmployeeAbsence] = Field(
        ..., description="Absence records for matching employees."
    )


class AbsenceWindowWithChartResponse(AbsenceWindowResponse):
    chart_file_name: str = Field(..., description="Generated chart filename.")
    sharepoint_file_url: str = Field(..., description="Uploaded chart URL.")
