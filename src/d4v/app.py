import sys

from d4v.tools.analyze_candidates import main as analyze_candidates_main
from d4v.tools.analyze_replay_ocr import main as analyze_replay_ocr_main
from d4v.tools.analyze_replay_roi import main as analyze_replay_roi_main
from d4v.tools.analyze_replay_tokens import main as analyze_replay_tokens_main
from d4v.tools.capture_round import main as capture_round_main
from d4v.tools.live_preview import main_live as live_preview_live_main
from d4v.tools.live_preview import main_replay as live_preview_replay_main


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        return 0

    if args[0] == "analyze-candidates" and len(args) == 2:
        return analyze_candidates_main(args[1])

    if args[0] == "analyze-replay-roi" and len(args) == 2:
        return analyze_replay_roi_main(args[1])

    if args[0] == "analyze-replay-tokens" and len(args) == 2:
        return analyze_replay_tokens_main(args[1])

    if args[0] == "analyze-replay-ocr" and len(args) == 2:
        return analyze_replay_ocr_main(args[1])

    if args[0] == "capture-round" and len(args) == 1:
        return capture_round_main()

    if args[0] == "live-preview" and len(args) == 3 and args[1] == "--replay":
        return live_preview_replay_main(args[2])

    if args[0] == "live-preview" and len(args) == 2 and args[1] == "--live":
        return live_preview_live_main()

    raise SystemExit(
        "Usage: python -m d4v.app analyze-candidates <path-to-candidates.json>\n"
        "   or: python -m d4v.app analyze-replay-roi <path-to-session-dir>\n"
        "   or: python -m d4v.app analyze-replay-tokens <path-to-session-dir>\n"
        "   or: python -m d4v.app analyze-replay-ocr <path-to-session-dir>\n"
        "   or: python -m d4v.app capture-round\n"
        "   or: python -m d4v.app live-preview --replay <path-to-session-dir>\n"
        "   or: python -m d4v.app live-preview --live"
    )


if __name__ == "__main__":
    raise SystemExit(main())
