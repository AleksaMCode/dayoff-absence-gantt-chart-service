from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from typing import Any, Dict, List, Optional

import matplotlib

from gantt import GANTT_THEME

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


def generate_absence_gantt(
    absence_data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    window_start = date.fromisoformat(absence_data["window_start"])
    window_end = date.fromisoformat(absence_data["window_end"])
    employees = absence_data.get("employees_absences", [])

    if not employees:
        return None

    filename = _build_filename(absence_data.get("team_name"), window_start, window_end)
    image_bytes = _render_absence_chart_to_bytes(
        employees, window_start, window_end, absence_data.get("team_name")
    )
    return {"chart_file_name": filename, "chart_bytes": image_bytes}


def _render_absence_chart_to_bytes(
    employees: List[Dict[str, Any]],
    window_start: date,
    window_end: date,
    team_name: str | None,
) -> bytes:
    plt.rcParams.update(GANTT_THEME)
    fig, ax = plt.subplots(figsize=(14, 4))

    y_positions = list(range(len(employees)))
    y_labels = [employee["name"] for employee in employees]

    # _add_weekend_background isn't needed if you perform check for one work week!
    _add_weekend_background(ax, window_start, window_end)
    _add_row_striping(ax, len(employees))

    for idx, employee in enumerate(employees):
        absence_dates = [
            date.fromisoformat(absence_date)
            for absence_date in employee.get("absence_dates", [])
        ]
        intervals = _group_dates_into_intervals(absence_dates)
        for interval_start, interval_end in intervals:
            bar_start = mdates.date2num(interval_start)
            bar_width = (interval_end - interval_start).days + 1
            ax.broken_barh(
                [(bar_start, bar_width)],
                (idx - 0.35, 0.7),
                facecolors="#6366F1",
                edgecolors="#4F46E5",
                linewidth=0.8,
            )

    ax.set_ylim(-1, len(employees))
    ax.set_yticks(y_positions)
    ax.set_yticklabels(y_labels)
    ax.set_xlim(
        mdates.date2num(window_start), mdates.date2num(window_end + timedelta(days=1))
    )
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    title_team = team_name or "All Teams"
    ax.set_title(
        f"Absence Timeline - {title_team}", fontsize=15, weight="bold", color="#0F172A"
    )
    ax.set_xlabel("Date")
    ax.set_ylabel("Employees")
    ax.grid(axis="x", linestyle="-", linewidth=0.8, color="#E2E8F0", alpha=0.9)
    ax.tick_params(axis="both", labelsize=10)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#E2E8F0")
    ax.spines["bottom"].set_color("#E2E8F0")
    fig.tight_layout()

    with BytesIO() as buffer:
        fig.savefig(buffer, format="png", dpi=180)
        buffer.seek(0)
        data = buffer.getvalue()
    plt.close(fig)
    return data


def _group_dates_into_intervals(dates: List[date]) -> List[tuple[date, date]]:
    if not dates:
        return []

    sorted_dates = sorted(set(dates))
    grouped: List[tuple[date, date]] = []
    interval_start = sorted_dates[0]
    interval_end = sorted_dates[0]

    for current in sorted_dates[1:]:
        if current == interval_end + timedelta(days=1):
            interval_end = current
            continue
        grouped.append((interval_start, interval_end))
        interval_start = current
        interval_end = current

    grouped.append((interval_start, interval_end))
    return grouped


def _build_filename(team_name: str | None, window_start: date, window_end: date) -> str:
    safe_team_name = (team_name or "all-teams").strip().lower().replace(" ", "-")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"absence-gantt-{safe_team_name}-{window_start.isoformat()}-{window_end.isoformat()}-{timestamp}.png"


def _add_weekend_background(ax: Any, window_start: date, window_end: date) -> None:
    current_day = window_start
    while current_day <= window_end:
        if current_day.weekday() >= 5:
            start = mdates.date2num(current_day)
            end = mdates.date2num(current_day + timedelta(days=1))
            ax.axvspan(start, end, facecolor="#F1F5F9", edgecolor="none", zorder=0)
        current_day += timedelta(days=1)


def _add_row_striping(ax: Any, total_rows: int) -> None:
    for row_index in range(total_rows):
        if row_index % 2 == 1:
            ax.axhspan(
                row_index - 0.5,
                row_index + 0.5,
                facecolor="#F8FAFC",
                edgecolor="none",
                zorder=0,
            )
