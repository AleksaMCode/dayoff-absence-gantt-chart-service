from fastapi import APIRouter, HTTPException

from dayoff.adapter import DayOffAdapter
from gantt.utils import generate_absence_gantt
from logger.utils import get_logger
from microsoft.sharepoint.utils import upload_image
from microsoft.teams.exceptions import TeamsPublishError
from microsoft.teams.utils import publish_to_channel
from models.requests import GetAbsencesRequest
from models.responses import AbsenceWindowResponse, AbsenceWindowWithChartResponse

router = APIRouter()
logger = get_logger(__name__)
api_adapter = DayOffAdapter()


@router.post(
    "/get_absences",
    response_model=AbsenceWindowResponse | AbsenceWindowWithChartResponse,
)
def get_absences(
    payload: GetAbsencesRequest,
) -> AbsenceWindowResponse | AbsenceWindowWithChartResponse:
    try:
        if payload.email_usernames:
            absence_data = api_adapter.get_absences_for_users_window(
                email_usernames=payload.email_usernames,
                team_name=payload.team_name,
                days_ahead=payload.days_ahead,
            )
        else:
            absence_data = api_adapter.get_absences_for_window(
                team=payload.team_name,
                team_id=payload.team_id,
                days_ahead=payload.days_ahead,
            )
        chart_data = generate_absence_gantt(absence_data)
        if chart_data is None:
            logger.info(f"There are no absences for team '{absence_data['team_name']}'")
            publish_to_channel(no_absences=True)
            return AbsenceWindowResponse.model_validate(absence_data)

        sharepoint_file_url = upload_image(
            image_content=chart_data["chart_bytes"],
            file_name=chart_data["chart_file_name"],
        )
        publish_to_channel(image_url=sharepoint_file_url)
        return AbsenceWindowWithChartResponse.model_validate(
            {
                **absence_data,
                "chart_file_name": chart_data["chart_file_name"],
                "sharepoint_file_url": sharepoint_file_url,
            }
        )
    except TeamsPublishError as error:
        logger.exception("Teams publish failed: %s", error)
        raise HTTPException(
            status_code=502, detail="Failed to publish Teams notification."
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch absences: {error}"
        ) from error
