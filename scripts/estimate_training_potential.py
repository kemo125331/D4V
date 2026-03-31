#!/usr/bin/env python3
"""Estimate training data potential from all replay sessions."""

import json
from pathlib import Path


def count_frames(session_path: Path) -> int:
    """Count frames in a session."""
    frames_dir = session_path / "frames"
    if frames_dir.exists():
        return len(list(frames_dir.glob("frame_*.png")))

    # Frames might be in root
    return len(list(session_path.glob("frame_*.png")))


def estimate_samples(frame_count: int) -> dict:
    """Estimate training samples from frame count.

    Based on observed ratio from 7 sessions:
    - ~107 candidates per 290 frames = 0.37 candidates/frame
    - ~29 hits per 290 frames = 0.10 hits/frame
    """
    candidates_per_frame = 0.37
    hits_per_frame = 0.10

    return {
        "estimated_candidates": int(frame_count * candidates_per_frame),
        "estimated_hits": int(frame_count * hits_per_frame),
    }


def main():
    print("=" * 60)
    print("D4V Training Data Potential Estimator")
    print("=" * 60)

    replays_dir = Path("fixtures/replays")

    if not replays_dir.exists():
        print(f"Error: {replays_dir} not found")
        return

    # Find all session directories
    sessions = [d for d in replays_dir.iterdir() if d.is_dir()]

    print(f"\nFound {len(sessions)} replay sessions")
    print("\n" + "=" * 60)
    print("Session Details")
    print("=" * 60)
    print(f"{'Session':<45} {'Frames':>8} {'Est. Samples':>14} {'Has Analysis':>14}")
    print("-" * 60)

    total_frames = 0
    total_estimated_samples = 0
    total_estimated_hits = 0
    has_analysis_count = 0

    for session in sorted(sessions):
        frame_count = count_frames(session)
        estimates = estimate_samples(frame_count)
        has_analysis = (session / "analysis" / "combat-ocr" / "summary.json").exists()

        total_frames += frame_count
        total_estimated_samples += estimates["estimated_candidates"]
        total_estimated_hits += estimates["estimated_hits"]
        if has_analysis:
            has_analysis_count += 1

        status = "✓ Yes" if has_analysis else "✗ No"
        print(
            f"{session.name:<45} {frame_count:>8} {estimates['estimated_candidates']:>14} {status:>14}"
        )

    print("=" * 60)
    print(
        f"{'TOTAL':<45} {total_frames:>8} {total_estimated_samples:>14} {has_analysis_count:>14}/ {len(sessions)}"
    )
    print("=" * 60)

    # Summary
    print(f"\n{'=' * 60}")
    print("Summary")
    print("=" * 60)
    print(f"Total Sessions: {len(sessions)}")
    print(
        f"Sessions with Analysis: {has_analysis_count} ({has_analysis_count / len(sessions) * 100:.0f}%)"
    )
    print(f"Sessions Needing Analysis: {len(sessions) - has_analysis_count}")
    print(f"Total Frames: {total_frames:,}")
    print(f"\nEstimated Training Data:")
    print(f"  OCR Candidates: ~{total_estimated_samples:,}")
    print(f"  Confirmed Hits: ~{total_estimated_hits:,}")
    print(
        f"  Expected Ratio: {total_estimated_hits / total_estimated_samples * 100:.0f}% positive"
    )

    # Comparison
    print(f"\n{'=' * 60}")
    print("Comparison")
    print("=" * 60)
    print(f"Current (7 sessions):   362 samples, 134 hits")
    print(
        f"Potential (all):        ~{total_estimated_samples} samples, ~{total_estimated_hits} hits"
    )
    print(f"Improvement:            {total_estimated_samples / 362:.1f}x more data")

    print(f"\n{'=' * 60}")
    print("Next Steps")
    print("=" * 60)
    print("1. Run: python scripts/process_all_replays_parallel.py --workers 8")
    print("2. Wait ~10-20 minutes for OCR analysis")
    print("3. Retrain: python scripts/train_confidence_model.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
