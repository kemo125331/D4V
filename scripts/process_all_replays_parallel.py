#!/usr/bin/env python3
"""Parallel batch processing with optimized performance.

Uses multiprocessing to process multiple replay sessions simultaneously.
"""

import json
import multiprocessing as mp
import sys
from pathlib import Path
from typing import Tuple


def check_session_analysis(session_path: Path) -> bool:
    """Check if session has OCR analysis."""
    analysis_file = session_path / "analysis" / "combat-ocr" / "summary.json"
    return analysis_file.exists()


def process_session_worker(args: Tuple[Path, bool]) -> Tuple[str, bool, str]:
    """Worker function for processing a single session.

    Args:
        args: Tuple of (session_path, force_reprocess)

    Returns:
        Tuple of (session_name, success, message)
    """
    session_path, force_reprocess = args
    session_name = session_path.name

    try:
        # Check if already processed
        if not force_reprocess and check_session_analysis(session_path):
            return (session_name, True, "Already processed")

        # Import here to avoid issues in multiprocessing
        try:
            from d4v.tools.analyze_replay_ocr import analyze_replay_ocr
        except ImportError:
            # Try alternative import
            sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
            from d4v.tools.analyze_replay_ocr import analyze_replay_ocr

        # Run analysis
        analyze_replay_ocr(session_path)

        return (session_name, True, "Processed successfully")

    except Exception as e:
        return (session_name, False, str(e))


def main():
    print("=" * 60)
    print("D4V Parallel Batch Processing")
    print("=" * 60)

    # Configuration
    import argparse

    parser = argparse.ArgumentParser(description="Process replay sessions in parallel")
    parser.add_argument(
        "--workers",
        type=int,
        default=min(8, mp.cpu_count()),
        help=f"Number of parallel workers (default: {min(8, mp.cpu_count())})",
    )
    parser.add_argument(
        "--force", action="store_true", help="Reprocess already analyzed sessions"
    )
    args = parser.parse_args()

    replays_dir = Path("fixtures/replays")

    if not replays_dir.exists():
        print(f"Error: {replays_dir} not found")
        return

    # Find all session directories
    sessions = [d for d in replays_dir.iterdir() if d.is_dir()]
    print(f"\nFound {len(sessions)} replay sessions")

    # Filter sessions that need processing
    if args.force:
        sessions_to_process = sessions
    else:
        sessions_to_process = [s for s in sessions if not check_session_analysis(s)]

    print(f"Sessions to process: {len(sessions_to_process)}")
    print(f"Workers: {args.workers}")
    print(f"CPU cores available: {mp.cpu_count()}")

    if not sessions_to_process:
        print("\nAll sessions already processed!")
        # Just run extraction
        from scripts.extract_training_data_simple import main as extract_main

        extract_main()
        return

    # Process in parallel
    print(f"\n{'=' * 60}")
    print(
        f"Processing {len(sessions_to_process)} sessions with {args.workers} workers..."
    )
    print("=" * 60)

    # Prepare worker arguments
    worker_args = [(session, args.force) for session in sessions_to_process]

    # Run parallel processing
    successful = 0
    failed = 0
    errors = []

    with mp.Pool(processes=args.workers) as pool:
        results = pool.imap_unordered(process_session_worker, worker_args)

        for i, (session_name, success, message) in enumerate(results, 1):
            if success:
                successful += 1
                print(f"[{i}/{len(sessions_to_process)}] ✓ {session_name}: {message}")
            else:
                failed += 1
                errors.append((session_name, message))
                print(f"[{i}/{len(sessions_to_process)}] ✗ {session_name}: {message}")

    # Summary
    print(f"\n{'=' * 60}")
    print("Processing Summary")
    print("=" * 60)
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

    if errors:
        print("\nFailed sessions:")
        for session_name, error in errors:
            print(f"  - {session_name}: {error}")

    # Extract training data from all sessions
    print(f"\n{'=' * 60}")
    print("Extracting training data from all sessions...")
    print("=" * 60)

    # Run extraction directly
    import sys

    sys.path.insert(0, str(Path(__file__).parent))
    from extract_training_data_simple import main as extract_main

    extract_main()

    print(f"\n{'=' * 60}")
    print("Batch processing complete!")
    print("=" * 60)
    print("\nNext step: Retrain model with new data")
    print(
        "Command: python scripts/train_confidence_model.py --output models/confidence_model_v2.joblib"
    )


if __name__ == "__main__":
    # Freeze support for Windows multiprocessing
    mp.freeze_support()
    main()
