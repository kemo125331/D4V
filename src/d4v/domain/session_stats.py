from collections import deque

from d4v.domain.models import DamageEvent


class SessionStats:
    def __init__(self) -> None:
        self.visible_damage_total = 0
        self.peak_hit = 0
        self.hit_count = 0
        self._recent_hits: deque[DamageEvent] = deque()

    def add_hit(
        self,
        frame: int,
        timestamp_ms: int,
        value: int,
        confidence: float = 0.0,
    ) -> None:
        event = DamageEvent(
            frame=frame,
            value=value,
            timestamp_ms=timestamp_ms,
            confidence=confidence,
        )
        self.visible_damage_total += value
        self.peak_hit = max(self.peak_hit, value)
        self.hit_count += 1
        self._recent_hits.append(event)
        self._trim_recent_hits(window_ms=5000, current_timestamp_ms=timestamp_ms)

    @property
    def biggest_hit(self) -> int:
        return self.peak_hit

    @property
    def average_hit(self) -> float:
        if self.hit_count == 0:
            return 0.0
        return self.visible_damage_total / self.hit_count

    def reset(self) -> None:
        self.visible_damage_total = 0
        self.peak_hit = 0
        self.hit_count = 0
        self._recent_hits.clear()

    def rolling_damage(self, window_ms: int = 5000) -> int:
        if not self._recent_hits:
            return 0
        current_timestamp_ms = self._recent_hits[-1].timestamp_ms or 0
        self._trim_recent_hits(window_ms=window_ms, current_timestamp_ms=current_timestamp_ms)
        return sum(event.value for event in self._recent_hits)

    def rolling_dps(self, window_ms: int = 5000) -> float:
        return self.rolling_damage(window_ms=window_ms) / (window_ms / 1000)

    def _trim_recent_hits(self, window_ms: int, current_timestamp_ms: int) -> None:
        while self._recent_hits:
            event = self._recent_hits[0]
            event_timestamp_ms = event.timestamp_ms or 0
            if current_timestamp_ms - event_timestamp_ms <= window_ms:
                break
            self._recent_hits.popleft()
