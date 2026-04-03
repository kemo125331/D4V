from __future__ import annotations

from dataclasses import dataclass

from d4v.capture.game_window import get_diablo_iv_bounds, is_diablo_iv_foreground
from d4v.overlay.game_overlay import GameOverlayViewModel, format_elapsed_time
from d4v.overlay.view_model import MLModelInfo, PreviewViewModel


@dataclass(frozen=True)
class DiagnosticsState:
    session_time_label: str
    game_focus_label: str
    window_binding_label: str
    runtime_mode_label: str


@dataclass(frozen=True)
class MainWindowState:
    title: str
    session_name: str
    start_button_label: str
    metrics: PreviewViewModel
    diagnostics: DiagnosticsState
    is_running: bool = False
    status_detail: str = ""

    @classmethod
    def from_controller(cls, controller: object) -> "MainWindowState":
        view_model = controller.view_model()
        return cls(
            title=str(getattr(controller, "window_title", "D4V Preview")),
            session_name=str(getattr(controller, "session_name", "live-session")),
            start_button_label=str(getattr(controller, "start_button_label", "Start")),
            metrics=view_model,
            diagnostics=diagnostics_state_from_controller(controller),
            is_running=bool(getattr(controller, "is_running", False)),
            status_detail=view_model.ml_model_info.display_text,
        )


def empty_window_state() -> MainWindowState:
    return MainWindowState(
        title="D4V Preview",
        session_name="live-session",
        start_button_label="Start",
        metrics=PreviewViewModel(
            total_damage_label="0",
            rolling_dps_label="0",
            biggest_hit_label="0",
            last_hit_label="No hit yet",
            status_label="Ready",
            recent_hits=[],
            ml_model_info=MLModelInfo.detect_model(),
        ),
        diagnostics=DiagnosticsState(
            session_time_label="00:00",
            game_focus_label="Unknown",
            window_binding_label="Waiting for Diablo IV window",
            runtime_mode_label="Preview",
        ),
        is_running=False,
        status_detail="",
    )


def diagnostics_state_from_controller(controller: object) -> DiagnosticsState:
    title = str(getattr(controller, "window_title", "D4V Preview"))
    is_replay = "Replay" in title

    if is_replay:
        game_focus_label = "Replay mode"
        window_binding_label = "Fixture session"
        runtime_mode_label = "Replay"
    else:
        game_focus_label = "Focused" if is_diablo_iv_foreground() else "Background"
        bounds = get_diablo_iv_bounds()
        if bounds is None:
            window_binding_label = "Diablo IV window not found"
        else:
            window_binding_label = (
                f"{bounds.width}x{bounds.height} @ {bounds.left},{bounds.top}"
            )
        runtime_mode_label = "Live"

    return DiagnosticsState(
        session_time_label=format_elapsed_time(
            int(getattr(controller, "elapsed_ms", 0))
        ),
        game_focus_label=game_focus_label,
        window_binding_label=window_binding_label,
        runtime_mode_label=runtime_mode_label,
    )


def overlay_view_model_from_controller(controller: object) -> GameOverlayViewModel:
    stats = getattr(controller, "stats", None)
    last_hit = getattr(controller, "last_hit", None)
    if stats is None:
        return GameOverlayViewModel()

    return GameOverlayViewModel.from_stats(
        avg_damage=stats.average_hit,
        last_damage=last_hit,
        total_damage=stats.visible_damage_total,
        hits_count=stats.hit_count,
        dps=stats.rolling_dps(),
        peak_hit=stats.biggest_hit,
        elapsed_ms=int(getattr(controller, "elapsed_ms", 0)),
    )
