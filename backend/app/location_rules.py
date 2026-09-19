# 離床過久／如廁過久的判斷：純粹看「目前 location 已經維持多久」，不比對真實時鐘的
# 時段（例如卡「晚上 10 點到早上 6 點才算夜間」）。demo 沒辦法保證在夜間展示，卡真實
# 時段會讓這個功能在白天展示時完全看不到效果，所以「夜遊」在這裡的定義單純是
# 「離床超過門檻時間」，跟現實時刻無關。

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from app.schemas import EventLocation, EventState, Priority

AWAY_FROM_BED_THRESHOLD = timedelta(minutes=15)
BATHROOM_THRESHOLD = timedelta(minutes=15)


@dataclass
class LocationAlert:
    state: EventState
    priority: Priority
    reason: str
    location: EventLocation


def evaluate_location(location: EventLocation, duration: timedelta) -> Optional[LocationAlert]:
    """location/duration 來自 store.get_location()/get_location_duration()。
    回傳 None 代表目前不需要開事件（在床上，或離床/在廁所都還沒超過門檻）。
    """
    minutes = int(duration.total_seconds() // 60)
    if location == "bathroom" and duration >= BATHROOM_THRESHOLD:
        return LocationAlert(
            state="prolonged_bathroom",
            priority="yellow",
            reason=f"如廁超過 {minutes} 分鐘",
            location="bathroom",
        )
    if location == "out_of_bed" and duration >= AWAY_FROM_BED_THRESHOLD:
        return LocationAlert(
            state="night_wandering",
            priority="yellow",
            reason=f"離床超過 {minutes} 分鐘",
            location="out_of_bed",
        )
    return None
