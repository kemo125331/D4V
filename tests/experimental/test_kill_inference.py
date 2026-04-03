"""Tests for kill tracking pipeline."""

import sys
from pathlib import Path

import pytest

# Import from experimental module
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

import importlib.util
spec = importlib.util.spec_from_file_location(
    "d4v.experimental.kill_inference",
    src_path / "d4v" / "experimental" / "kill_inference.py"
)
kill_inference = importlib.util.module_from_spec(spec)
sys.modules["d4v.experimental.kill_inference"] = kill_inference
spec.loader.exec_module(kill_inference)

KillTracker = kill_inference.KillTracker
KillEvent = kill_inference.KillEvent
KillSignal = kill_inference.KillSignal
EnemyState = kill_inference.EnemyState
KillStatistics = kill_inference.KillStatistics
infer_kills_from_damage = kill_inference.infer_kills_from_damage


class TestKillSignal:
    """Tests for KillSignal enum."""

    def test_signal_values(self):
        """Given signal enum, expect correct values."""
        assert KillSignal.XP_ORB == "xp_orb"
        assert KillSignal.GOLD_DROP == "gold_drop"
        assert KillSignal.DEATH_ANIMATION == "death_animation"


class TestKillEvent:
    """Tests for KillEvent dataclass."""

    def test_create_kill_event(self):
        """Given valid parameters, expect event created."""
        event = KillEvent(
            timestamp_ms=3333,
            frame_index=100,
            enemy_id="enemy_1",
            total_damage_dealt=5000,
            final_hit_value=1234,
            kill_signal=KillSignal.XP_ORB,
            confidence=0.95,
        )
        assert event.enemy_id == "enemy_1"
        assert event.kill_signal == KillSignal.XP_ORB

    def test_to_dict(self):
        """Given event, expect dict conversion."""
        event = KillEvent(
            timestamp_ms=3333,
            frame_index=100,
            enemy_id="enemy_1",
            total_damage_dealt=5000,
            final_hit_value=1234,
            kill_signal=KillSignal.XP_ORB,
            confidence=0.95,
        )
        data = event.to_dict()
        assert data["enemy_id"] == "enemy_1"
        assert data["kill_signal"] == "xp_orb"
        assert "damage_count" in data


class TestEnemyState:
    """Tests for EnemyState dataclass."""

    def test_create_enemy(self):
        """Given enemy created, expect initialized."""
        enemy = EnemyState(enemy_id="enemy_1")
        assert enemy.enemy_id == "enemy_1"
        assert enemy.damage_total == 0
        assert enemy.is_alive

    def test_add_damage(self):
        """Given damage added, expect state updated."""
        enemy = EnemyState(enemy_id="enemy_1")

        enemy.add_damage(value=1000, frame=10, x=500.0, y=300.0)

        assert enemy.damage_total == 1000
        assert len(enemy.damage_hits) == 1
        assert enemy.position_x == 500.0

    def test_add_multiple_damage(self):
        """Given multiple damage, expect accumulation."""
        enemy = EnemyState(enemy_id="enemy_1")

        enemy.add_damage(1000, 10, 500.0, 300.0)
        enemy.add_damage(2000, 15, 502.0, 298.0)
        enemy.add_damage(1500, 20, 504.0, 296.0)

        assert enemy.damage_total == 4500
        assert len(enemy.damage_hits) == 3
        assert enemy.last_damage_frame == 20

    def test_mark_dead(self):
        """Given marked dead, expect state updated."""
        enemy = EnemyState(enemy_id="enemy_1")

        enemy.mark_dead(frame=25, kill_signal=KillSignal.XP_ORB)

        assert not enemy.is_alive
        assert enemy.kill_frame == 25


class TestKillStatistics:
    """Tests for KillStatistics dataclass."""

    def test_create_statistics(self):
        """Given statistics created, expect initialized."""
        stats = KillStatistics()
        assert stats.total_kills == 0
        assert stats.kills_per_minute == 0.0

    def test_to_dict(self):
        """Given statistics, expect dict conversion."""
        stats = KillStatistics(
            total_kills=10,
            total_damage=50000,
            biggest_kill=8000,
            kills_per_minute=5.5,
        )
        data = stats.to_dict()
        assert data["total_kills"] == 10
        assert data["biggest_kill"] == 8000


class TestKillTracker:
    """Tests for KillTracker."""

    def test_tracker_creation(self):
        """Given tracker created, expect initialized."""
        tracker = KillTracker()
        assert tracker.damage_window_ms == 3000
        assert len(tracker.enemies) == 0
        assert len(tracker.kills) == 0

    def test_add_damage_creates_enemy(self):
        """Given damage added, expect enemy created."""
        tracker = KillTracker()

        tracker.add_damage(
            value=1234,
            frame=10,
            timestamp_ms=333,
            center_x=500.0,
            center_y=300.0,
        )

        assert len(tracker.enemies) == 1
        assert tracker.next_enemy_id == 2

    def test_add_damage_clusters_nearby(self):
        """Given nearby damage, expect same enemy."""
        tracker = KillTracker(spatial_cluster_threshold=100.0)

        tracker.add_damage(1000, 10, 333, 500.0, 300.0)
        tracker.add_damage(2000, 15, 500, 502.0, 298.0)  # Nearby

        assert len(tracker.enemies) == 1
        enemy = list(tracker.enemies.values())[0]
        assert enemy.damage_total == 3000

    def test_add_damage_creates_multiple_enemies(self):
        """Given distant damage, expect different enemies."""
        tracker = KillTracker(spatial_cluster_threshold=100.0)

        tracker.add_damage(1000, 10, 333, 100.0, 100.0)
        tracker.add_damage(2000, 15, 500, 800.0, 600.0)  # Far away

        assert len(tracker.enemies) == 2

    def test_add_visual_cue(self):
        """Given visual cue added, expect stored."""
        tracker = KillTracker()

        tracker.add_visual_cue(
            cue_type="xp_orb",
            frame=20,
            timestamp_ms=666,
            center_x=500.0,
            center_y=300.0,
        )

        assert len(tracker.recent_cues) == 1

    def test_get_statistics(self):
        """Given tracker, expect statistics available."""
        tracker = KillTracker()

        # Add some damage
        tracker.add_damage(5000, 10, 333, 500.0, 300.0)

        stats = tracker.get_statistics()

        assert isinstance(stats, KillStatistics)
        # Stats object should be valid even with no confirmed kills
        assert stats.total_kills >= 0

    def test_reset(self):
        """Given reset, expect state cleared."""
        tracker = KillTracker()

        tracker.add_damage(1000, 10, 333, 500.0, 300.0)
        tracker.add_visual_cue("xp_orb", 15, 500, 505.0, 305.0)
        tracker.reset()

        assert len(tracker.enemies) == 0
        assert len(tracker.kills) == 0
        assert tracker.next_enemy_id == 1

    def test_session_timing(self):
        """Given damage events, expect timing tracked."""
        tracker = KillTracker()

        tracker.add_damage(1000, 10, 333, 500.0, 300.0)
        tracker.add_damage(2000, 60, 2000, 502.0, 298.0)

        assert tracker.session_start_ms == 333
        assert tracker.session_end_ms == 2000


class TestInferKillsFromDamage:
    """Tests for convenience function."""

    def test_infer_kills_simple(self):
        """Given damage events, expect function works."""
        damage_events = [
            {
                "value": 5000,
                "frame": 10,
                "timestamp_ms": 333,
                "center_x": 500.0,
                "center_y": 300.0,
            },
        ]

        kills = infer_kills_from_damage(damage_events)

        # Returns list of kills (may be empty without visual cues)
        assert isinstance(kills, list)

    def test_infer_kills_with_cues(self):
        """Given damage and cues, expect function works."""
        damage_events = [
            {
                "value": 5000,
                "frame": 10,
                "timestamp_ms": 333,
                "center_x": 500.0,
                "center_y": 300.0,
            },
        ]

        visual_cues = [
            {
                "cue_type": "xp_orb",
                "frame": 15,
                "timestamp_ms": 500,
                "center_x": 505.0,
                "center_y": 305.0,
            },
        ]

        kills = infer_kills_from_damage(damage_events, visual_cues)

        # Returns list of kills
        assert isinstance(kills, list)


class TestIntegration:
    """Integration tests for kill tracking."""

    def test_full_kill_tracking_workflow(self):
        """Given full workflow, expect end-to-end tracking."""
        tracker = KillTracker()

        # Simulate combat with multiple enemies
        # Enemy 1
        tracker.add_damage(2000, 10, 333, 500.0, 300.0)
        tracker.add_damage(3000, 15, 500, 502.0, 298.0)

        # Enemy 2 (different position)
        tracker.add_damage(1500, 25, 833, 700.0, 400.0)
        tracker.add_damage(2500, 30, 1000, 702.0, 398.0)

        # Get results
        kills = tracker.get_kills()
        stats = tracker.get_statistics()

        # Should have tracked enemies
        assert len(tracker.enemies) == 2
        assert isinstance(stats, KillStatistics)

    def test_multiple_damage_types(self):
        """Given different damage types, expect tracking works."""
        tracker = KillTracker()

        # Direct damage
        tracker.add_damage(1000, 10, 333, 500.0, 300.0, damage_type="direct")
        # Crit
        tracker.add_damage(5000, 15, 500, 502.0, 298.0, damage_type="crit")
        # DoT
        tracker.add_damage(200, 20, 666, 504.0, 296.0, damage_type="dot_tick")

        # Should track all as same enemy (nearby positions)
        assert len(tracker.enemies) == 1
        enemy = list(tracker.enemies.values())[0]
        assert enemy.damage_total == 6200

    def test_rapid_kills(self):
        """Given rapid successive kills, expect all tracked."""
        tracker = KillTracker()

        positions = [
            (100.0, 100.0),
            (300.0, 300.0),
            (500.0, 500.0),
            (700.0, 700.0),
        ]

        for i, (x, y) in enumerate(positions):
            tracker.add_damage(3000, i * 10, i * 333, x, y)

        # Should have 4 separate enemies
        assert len(tracker.enemies) == 4
