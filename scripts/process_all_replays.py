#!/usr/bin/env python3
"""Batch process all replay sessions to extract training data.

Runs OCR analysis on sessions that need it, then extracts training data.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def check_session_analysis(session_path: Path) -> bool:
    """Check if session has OCR analysis."""
    analysis_file = session_path / "analysis" / "combat-ocr" / "summary.json"
    return analysis_file.exists()

def run_ocr_analysis(session_path: Path) -> bool:
    """Run OCR analysis on a session.
    
    Args:
        session_path: Path to session directory.
        
    Returns:
        True if successful.
    """
    try:
        # Import analysis tools
        from d4v.tools.analyze_replay_ocr import analyze_replay
        
        print(f"  Running OCR analysis on {session_path.name}...")
        
        # Run analysis
        analyze_replay(session_path)
        
        return True
        
    except Exception as e:
        print(f"  Error analyzing {session_path.name}: {e}")
        return False

def main():
    print("=" * 60)
    print("D4V Batch Training Data Processing")
    print("=" * 60)
    
    replays_dir = Path("fixtures/replays")
    
    if not replays_dir.exists():
        print(f"Error: {replays_dir} not found")
        return
    
    # Find all session directories
    sessions = [d for d in replays_dir.iterdir() if d.is_dir()]
    print(f"\nFound {len(sessions)} replay sessions")
    
    # Check which need analysis
    needs_analysis = []
    has_analysis = []
    
    for session in sessions:
        if check_session_analysis(session):
            has_analysis.append(session)
        else:
            needs_analysis.append(session)
    
    print(f"  Already analyzed: {len(has_analysis)}")
    print(f"  Need analysis: {len(needs_analysis)}")
    
    # Run analysis on sessions that need it
    if needs_analysis:
        print(f"\n{'=' * 60}")
        print(f"Running OCR analysis on {len(needs_analysis)} sessions...")
        print("=" * 60)
        
        successful = 0
        failed = 0
        
        for session in needs_analysis:
            if run_ocr_analysis(session):
                successful += 1
            else:
                failed += 1
        
        print(f"\nAnalysis complete: {successful} successful, {failed} failed")
    
    # Now extract training data from all sessions
    print(f"\n{'=' * 60}")
    print("Extracting training data...")
    print("=" * 60)
    
    # Run extraction script
    from scripts.extract_training_data_simple import main as extract_main
    extract_main()

if __name__ == "__main__":
    main()
