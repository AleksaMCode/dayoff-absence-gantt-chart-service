import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from models.fetch_mode import FetchMode

app = FastAPI(title="DayOff Absence Gantt Service", version="1.0.0")
load_dotenv()

fetch_mode = FetchMode.from_env(
    raw_mode=os.getenv("DAYOFF_FETCH_MODE"),
)

if fetch_mode == FetchMode.API:
    from routers.api_absences import router as absences_router
elif fetch_mode == FetchMode.SCRAPER:
    from routers.scraper_absences import router as absences_router
else:
    raise ValueError("Invalid fetch mode. Use DAYOFF_FETCH_MODE=api|scraper.")

app.include_router(absences_router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
