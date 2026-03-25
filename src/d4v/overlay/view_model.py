from __future__ import annotations

from dataclasses import dataclass, field


def format_damage_value(value: int | float) -> str:
    if isinstance(value, float) and not value.is_integer():
        return f"{value:,.2f}"
    return f"{int(value):,}"


@dataclass(frozen=True)
class PreviewViewModel:
    total_damage_label: str
    rolling_dps_label: str
    biggest_hit_label: str
    last_hit_label: str
    status_label: str
    recent_hits: list[str] = field(default_factory=list)

    @classmethod
    def from_state(
        cls,
        *,
        total_damage: int,
        rolling_dps: float,
        biggest_hit: int,
        last_hit: int | None,
        status: str,
        recent_hits: list[str] | None = None,
    ) -> "PreviewViewModel":
        last_hit_label = "No hit yet" if last_hit is None else format_damage_value(last_hit)
        return cls(
            total_damage_label=format_damage_value(total_damage),
            rolling_dps_label=format_damage_value(rolling_dps),
            biggest_hit_label=format_damage_value(biggest_hit),
            last_hit_label=last_hit_label,
            status_label=status,
            recent_hits=recent_hits or [],
        )
