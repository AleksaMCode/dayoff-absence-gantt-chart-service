from fastapi import APIRouter, HTTPException

from dayoff.scraper_adapter import DayOffScraperAdapter
from gantt.utils import generate_absence_gantt
from logger.utils import get_logger
from microsoft.sharepoint.utils import upload_image
from microsoft.teams.utils import publish_to_channel
from models.requests import GetScrapedAbsencesRequest

router = APIRouter()
logger = get_logger(__name__)
scraper_adapter = DayOffScraperAdapter()


@router.post("/get_absences_scraped")
def get_absences_scraped(payload: GetScrapedAbsencesRequest):
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
            return absence_data

        sharepoint_file_url = upload_image(
            image_content=chart_data["chart_bytes"],
            file_name=chart_data["chart_file_name"],
        )
        publish_to_channel(image_url=sharepoint_file_url)
        return {
            **absence_data,
            "chart_file_name": chart_data["chart_file_name"],
            "sharepoint_file_url": sharepoint_file_url,
        }
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch absences: {error}"
        ) from error
