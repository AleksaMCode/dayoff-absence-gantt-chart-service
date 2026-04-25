import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from dayoff.adapter import DayOffAdapter
from gantt.utils import generate_absence_gantt
from logger.utils import get_logger
from microsoft.sharepoint.utils import upload_image
from microsoft.teams.utils import publish_to_channel
from models.requests import GetAbsencesRequest

app = FastAPI(title="DayOff Absence Gantt Service", version="1.0.0")
dayoff_adapter = DayOffAdapter()

logger = get_logger(__name__)
load_dotenv()


@app.post("/get_absences")
def get_absences(payload: GetAbsencesRequest):
    try:
        if payload.email_usernames:
            absence_data = dayoff_adapter.get_absences_for_users_window(
                email_usernames=payload.email_usernames,
                team_name=payload.team_name,
                days_ahead=payload.days_ahead,
            )
        else:
            absence_data = dayoff_adapter.get_absences_for_window(
                team=payload.team_name,
                team_id=payload.team_id,
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


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
