from fastapi import APIRouter, HTTPException

from dayoff.exceptions import ScraperError, ScraperLookupError
from dayoff.scraper_adapter import DayOffScraperAdapter
from gantt.utils import generate_absence_gantt
from logger.utils import get_logger
from microsoft.sharepoint.utils import upload_image
from microsoft.teams.utils import publish_to_channel
from models.requests import GetScrapedAbsencesRequest
from models.responses import AbsenceWindowResponse, AbsenceWindowWithChartResponse

router = APIRouter()
logger = get_logger(__name__)
scraper_adapter = DayOffScraperAdapter()


@router.post(
    "/get_absences_scraped",
    response_model=AbsenceWindowResponse | AbsenceWindowWithChartResponse,
)
def get_absences_scraped(
    payload: GetScrapedAbsencesRequest,
) -> AbsenceWindowResponse | AbsenceWindowWithChartResponse:
    try:
        absence_data = scraper_adapter.get_absences_for_users_window(
            full_names=payload.full_names,
            team_name=payload.team_name,
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
    except ScraperLookupError as error:
        logger.warning("Scraper lookup miss: %s", error)
        raise HTTPException(
            status_code=404, detail="Requested data not found."
        ) from error
    except ScraperError as error:
        logger.exception("Day Off scraper failed: %s", error)
        raise HTTPException(
            status_code=502, detail="Failed to retrieve data from Day Off."
        ) from error
    except Exception as error:
        logger.exception("Unexpected scraper route error: %s", error)
        raise HTTPException(status_code=500, detail="Internal server error.") from error
