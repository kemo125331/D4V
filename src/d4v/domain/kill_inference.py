"""Kill tracking pipeline for inferring enemy deaths.

Tracks damage per enemy and infers kills from:
- XP orb pickups
- Gold drops
- Death animations
- Damage cessation patterns
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class KillSignal(StrEnum):
    """Types of kill confirmation signals."""

    XP_ORB = "xp_orb"
    GOLD_DROP = "gold_drop"
    ITEM_DROP = "item_drop"
    DEATH_ANIMATION = "death_animation"
    DAMAGE_CESSATION = "damage_cessation"
    ENEMY_HEALTH_BAR = "enemy_health_bar"


@dataclass(frozen=True)
class KillEvent:
    """Represents an inferred enemy kill.

    Attributes:
        timestamp_ms: Timestamp of kill in milliseconds.
        frame_index: Frame where kill was inferred.
        enemy_id: Unique enemy identifier (if tracked).
        total_damage_dealt: Total damage dealt to enemy.
        final_hit_value: Value of killing blow.
        kill_signal: Type of signal that confirmed kill.
        confidence: Confidence in kill inference (0-1).
        position_x: X position where enemy died.
        position_y: Y position where enemy died.
        damage_history: List of damage values leading to kill.
    """

    timestamp_ms: int
    frame_index: int
    enemy_id: str
    total_damage_dealt: int
    final_hit_value: int
    kill_signal: KillSignal
    confidence: float
    position_x: float = 0.0
    position_y: float = 0.0
    damage_history: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp_ms": self.timestamp_ms,
            "frame_index": self.frame_index,
            "enemy_id": self.enemy_id,
            "total_damage_dealt": self.total_damage_dealt,
            "final_hit_value": self.final_hit_value,
            "kill_signal": str(self.kill_signal),
            "confidence": round(self.confidence, 4),
            "position_x": round(self.position_x, 2),
            "position_y": round(self.position_y, 2),
            "damage_count": len(self.damage_history),
        }


@dataclass
class EnemyState:
    """Tracks state of a single enemy.

    Attributes:
        enemy_id: Unique identifier.
        damage_total: Total damage dealt.
        damage_hits: List of damage values.
        first_seen_frame: Frame where enemy first appeared.
        last_damage_frame: Frame of last damage.
        position_x: Last known X position.
        position_y: Last known Y position.
        is_alive: Whether enemy is still alive.
        kill_frame: Frame where enemy was killed (if dead).
    """

    enemy_id: str
    damage_total: int = 0
    damage_hits: list[int] = field(default_factory=list)
    first_seen_frame: int = 0
    last_damage_frame: int = 0
    position_x: float = 0.0
    position_y: float = 0.0
    is_alive: bool = True
    kill_frame: int | None = None

    def add_damage(self, value: int, frame: int, x: float, y: float) -> None:
        """Add damage to this enemy.

        Args:
            value: Damage value.
            frame: Frame index.
            x: X position.
            y: Y position.
        """
        self.damage_total += value
        self.damage_hits.append(value)
        self.last_damage_frame = frame
        self.position_x = x
        self.position_y = y

        if self.first_seen_frame == 0:
            self.first_seen_frame = frame

    def mark_dead(self, frame: int, kill_signal: KillSignal) -> None:
        """Mark enemy as dead.

        Args:
            frame: Frame of death.
            kill_signal: Signal that confirmed death.
        """
        self.is_alive = False
        self.kill_frame = frame


@dataclass
class KillStatistics:
    """Statistics for kill tracking session.

    Attributes:
        total_kills: Total kills inferred.
        total_damage: Total damage dealt.
        biggest_kill: Largest single kill damage.
        average_damage_per_kill: Average damage per kill.
        kills_per_minute: Kill rate.
        kill_signals: Breakdown by signal type.
    """

    total_kills: int = 0
    total_damage: int = 0
    biggest_kill: int = 0
    average_damage_per_kill: float = 0.0
    kills_per_minute: float = 0.0
    kill_signals: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_kills": self.total_kills,
            "total_damage": self.total_damage,
            "biggest_kill": self.biggest_kill,
            "average_damage_per_kill": round(self.average_damage_per_kill, 2),
            "kills_per_minute": round(self.kills_per_minute, 2),
            "kill_signals": self.kill_signals,
        }


class KillTracker:
    """Tracks damage and infers enemy kills.

    Example:
        tracker = KillTracker(
            damage_window_ms=3000,
            spatial_cluster_threshold=100.0,
        )

        # Process damage events
        tracker.add_damage(
            value=1234,
            frame=100,
            timestamp_ms=3333,
            center_x=500.0,
            center_y=300.0,
        )

        # Process visual cues (XP orbs, gold)
        tracker.add_visual_cue(
            cue_type="xp_orb",
            frame=105,
            timestamp_ms=3500,
            center_x=510.0,
            center_y=310.0,
        )

        # Get inferred kills
        kills = tracker.get_kills()
    """

    def __init__(
        self,
        damage_window_ms: int = 3000,
        spatial_cluster_threshold: float = 100.0,
        kill_confirmation_delay_ms: int = 500,
        min_damage_for_kill: int = 100,
    ) -> None:
        """Initialize kill tracker.

        Args:
            damage_window_ms: Time window to associate damage with enemy.
            spatial_cluster_threshold: Pixel distance for clustering damage.
            kill_confirmation_delay_ms: Delay before confirming kill.
            min_damage_for_kill: Minimum damage to count as kill.
        """
        self.damage_window_ms = damage_window_ms
        self.spatial_cluster_threshold = spatial_cluster_threshold
        self.kill_confirmation_delay_ms = kill_confirmation_delay_ms
        self.min_damage_for_kill = min_damage_for_kill

        # Enemy tracking
        self.enemies: dict[str, EnemyState] = {}
        self.next_enemy_id = 1

        # Kill tracking
        self.kills: list[KillEvent] = []
        self.pending_kills: list[dict[str, Any]] = []

        # Visual cue tracking
        self.recent_cues: list[dict[str, Any]] = []

        # Timing
        self.session_start_ms: int = 0
        self.session_end_ms: int = 0

    def add_damage(
        self,
        value: int,
        frame: int,
        timestamp_ms: int,
        center_x: float,
        center_y: float,
        damage_type: str = "direct",
    ) -> None:
        """Add damage event.

        Args:
            value: Damage value.
            frame: Frame index.
            timestamp_ms: Timestamp in milliseconds.
            center_x: X coordinate of damage.
            center_y: Y coordinate of damage.
            damage_type: Type of damage.
        """
        # Update session timing
        if self.session_start_ms == 0:
            self.session_start_ms = timestamp_ms
        self.session_end_ms = max(self.session_end_ms, timestamp_ms)

        # Find or create enemy
        enemy_id = self._find_or_create_enemy(center_x, center_y, frame)

        # Add damage
        if enemy_id in self.enemies:
            self.enemies[enemy_id].add_damage(value, frame, center_x, center_y)

        # Check for visual cues that might confirm kill
        self._check_kill_confirmation(enemy_id, frame, timestamp_ms, center_x, center_y)

    def add_visual_cue(
        self,
        cue_type: str,
        frame: int,
        timestamp_ms: int,
        center_x: float,
        center_y: float,
        confidence: float = 0.8,
    ) -> None:
        """Add visual cue (XP orb, gold drop, etc.).

        Args:
            cue_type: Type of visual cue.
            frame: Frame index.
            timestamp_ms: Timestamp.
            center_x: X coordinate.
            center_y: Y coordinate.
            confidence: Detection confidence.
        """
        cue = {
            "cue_type": cue_type,
            "frame": frame,
            "timestamp_ms": timestamp_ms,
            "center_x": center_x,
            "center_y": center_y,
            "confidence": confidence,
        }
        self.recent_cues.append(cue)

        # Keep only recent cues (within 2 seconds)
        cutoff_ms = timestamp_ms - 2000
        self.recent_cues = [c for c in self.recent_cues if c["timestamp_ms"] > cutoff_ms]

        # Try to associate with pending kills
        self._associate_cue_with_pending_kills(cue)

    def _find_or_create_enemy(
        self,
        x: float,
        y: float,
        frame: int,
    ) -> str:
        """Find existing enemy or create new one.

        Args:
            x: X position.
            y: Y position.
            frame: Frame index.

        Returns:
            Enemy ID.
        """
        # Look for nearby enemy
        for enemy_id, enemy in self.enemies.items():
            if not enemy.is_alive:
                continue

            # Check spatial proximity
            dx = abs(enemy.position_x - x)
            dy = abs(enemy.position_y - y)
            distance = (dx ** 2 + dy ** 2) ** 0.5

            if distance < self.spatial_cluster_threshold:
                # Check temporal proximity
                if frame - enemy.last_damage_frame < 60:  # Within 2 seconds at 30fps
                    return enemy_id

        # Create new enemy
        enemy_id = f"enemy_{self.next_enemy_id}"
        self.next_enemy_id += 1

        self.enemies[enemy_id] = EnemyState(enemy_id=enemy_id)

        return enemy_id

    def _check_kill_confirmation(
        self,
        enemy_id: str,
        frame: int,
        timestamp_ms: int,
        x: float,
        y: float,
    ) -> None:
        """Check if there's evidence of a kill.

        Args:
            enemy_id: Enemy to check.
            frame: Current frame.
            timestamp_ms: Current timestamp.
            x: X position.
            y: Y position.
        """
        enemy = self.enemies.get(enemy_id)
        if not enemy or not enemy.is_alive:
            return

        # Check for visual cues at same position
        for cue in self.recent_cues:
            if cue["frame"] <= frame:
                continue

            dx = abs(cue["center_x"] - x)
            dy = abs(cue["center_y"] - y)
            distance = (dx ** 2 + dy ** 2) ** 0.5

            if distance < 50:  # Close to damage position
                # Confirm kill
                self._confirm_kill(enemy_id, cue["cue_type"], frame, timestamp_ms)
                return

    def _associate_cue_with_pending_kills(self, cue: dict[str, Any]) -> None:
        """Associate visual cue with pending kills.

        Args:
            cue: Visual cue dictionary.
        """
        cue_type = cue["cue_type"]
        cue_frame = cue["frame"]
        cue_x = cue["center_x"]
        cue_y = cue["center_y"]

        # Check pending kills
        for pending in self.pending_kills[:]:
            dx = abs(pending["position_x"] - cue_x)
            dy = abs(pending["position_y"] - cue_y)
            distance = (dx ** 2 + dy ** 2) ** 0.5

            if distance < 80:  # Within range
                # Confirm kill with this signal
                self._confirm_kill(
                    pending["enemy_id"],
                    cue_type,
                    cue_frame,
                    cue["timestamp_ms"],
                )
                self.pending_kills.remove(pending)

    def _confirm_kill(
        self,
        enemy_id: str,
        signal_type: str,
        frame: int,
        timestamp_ms: int,
    ) -> None:
        """Confirm enemy kill.

        Args:
            enemy_id: Enemy that was killed.
            signal_type: Type of confirmation signal.
            frame: Frame of confirmation.
            timestamp_ms: Timestamp.
        """
        enemy = self.enemies.get(enemy_id)
        if not enemy:
            return

        # Mark enemy as dead
        enemy.mark_dead(frame, KillSignal(signal_type))

        # Determine kill signal type
        kill_signal = self._map_signal_type(signal_type)

        # Calculate confidence
        confidence = self._calculate_kill_confidence(enemy, kill_signal)

        # Create kill event
        kill_event = KillEvent(
            timestamp_ms=timestamp_ms,
            frame_index=frame,
            enemy_id=enemy_id,
            total_damage_dealt=enemy.damage_total,
            final_hit_value=enemy.damage_hits[-1] if enemy.damage_hits else 0,
            kill_signal=kill_signal,
            confidence=confidence,
            position_x=enemy.position_x,
            position_y=enemy.position_y,
            damage_history=enemy.damage_hits.copy(),
        )

        self.kills.append(kill_event)

    def _map_signal_type(self, signal_type: str) -> KillSignal:
        """Map signal type string to KillSignal enum.

        Args:
            signal_type: Signal type string.

        Returns:
            KillSignal enum value.
        """
        mapping = {
            "xp_orb": KillSignal.XP_ORB,
            "gold_drop": KillSignal.GOLD_DROP,
            "item_drop": KillSignal.ITEM_DROP,
            "death_animation": KillSignal.DEATH_ANIMATION,
            "health_bar": KillSignal.ENEMY_HEALTH_BAR,
        }
        return mapping.get(signal_type, KillSignal.DAMAGE_CESSATION)

    def _calculate_kill_confidence(
        self,
        enemy: EnemyState,
        kill_signal: KillSignal,
    ) -> float:
        """Calculate confidence in kill inference.

        Args:
            enemy: Enemy state.
            kill_signal: Confirmation signal.

        Returns:
            Confidence score (0-1).
        """
        # Base confidence by signal type
        signal_confidence = {
            KillSignal.XP_ORB: 0.95,
            KillSignal.GOLD_DROP: 0.90,
            KillSignal.ITEM_DROP: 0.85,
            KillSignal.DEATH_ANIMATION: 0.90,
            KillSignal.ENEMY_HEALTH_BAR: 0.95,
            KillSignal.DAMAGE_CESSATION: 0.60,
        }

        base_confidence = signal_confidence.get(kill_signal, 0.5)

        # Adjust based on damage dealt
        if enemy.damage_total < self.min_damage_for_kill:
            base_confidence *= 0.5

        # Adjust based on number of hits
        if len(enemy.damage_hits) >= 3:
            base_confidence = min(base_confidence + 0.05, 1.0)

        return base_confidence

    def get_kills(self) -> list[KillEvent]:
        """Get all inferred kills.

        Returns:
            List of KillEvent objects.
        """
        return self.kills.copy()

    def get_statistics(self) -> KillStatistics:
        """Get kill tracking statistics.

        Returns:
            KillStatistics object.
        """
        if not self.kills:
            return KillStatistics()

        total_kills = len(self.kills)
        total_damage = sum(k.total_damage_dealt for k in self.kills)
        biggest_kill = max(k.total_damage_dealt for k in self.kills)

        # Calculate kills per minute
        duration_ms = self.session_end_ms - self.session_start_ms
        duration_minutes = duration_ms / 60000 if duration_ms > 0 else 1
        kills_per_minute = total_kills / duration_minutes

        # Count signal types
        signal_counts: dict[str, int] = defaultdict(int)
        for kill in self.kills:
            signal_counts[str(kill.kill_signal)] += 1

        return KillStatistics(
            total_kills=total_kills,
            total_damage=total_damage,
            biggest_kill=biggest_kill,
            average_damage_per_kill=total_damage / total_kills if total_kills > 0 else 0,
            kills_per_minute=kills_per_minute,
            kill_signals=dict(signal_counts),
        )

    def reset(self) -> None:
        """Reset tracker state."""
        self.enemies.clear()
        self.kills.clear()
        self.pending_kills.clear()
        self.recent_cues.clear()
        self.next_enemy_id = 1
        self.session_start_ms = 0
        self.session_end_ms = 0


def infer_kills_from_damage(
    damage_events: list[dict[str, Any]],
    visual_cues: list[dict[str, Any]] | None = None,
) -> list[KillEvent]:
    """Convenience function to infer kills from damage events.

    Args:
        damage_events: List of damage event dictionaries.
        visual_cues: Optional list of visual cue dictionaries.

    Returns:
        List of inferred KillEvent objects.
    """
    tracker = KillTracker()

    # Add damage events
    for event in damage_events:
        tracker.add_damage(**event)

    # Add visual cues
    if visual_cues:
        for cue in visual_cues:
            tracker.add_visual_cue(**cue)

    return tracker.get_kills()
