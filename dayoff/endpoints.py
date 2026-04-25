from enum import Enum


class Endpoints(str, Enum):
    TEAMS = "/api/doc/teams"
    EMPLOYEES = "/api/doc/employees"
    LEAVE_REQUESTS = "/api/doc/employees/{employee_id}/leaveRequests"
    EVENTS_BY_MONTH = "/api/doc/calendar/events/by-month"

    def __str__(self):
        return self.value
