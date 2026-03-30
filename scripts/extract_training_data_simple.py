#!/usr/bin/env python3
"""Quick training data extraction from replay analysis - standalone version.

No d4v package imports required.
"""

import json
from pathlib import Path


def extract_features_from_result(result: dict) -> dict:
    """Extract ML features from OCR result."""
    width = result.get("right", 0) - result.get("left", 0)
    height = result.get("bottom", 0) - result.get("top", 0)
    score = result.get("score", 5.0)
    raw_text = result.get("raw_text", "")
    parsed_value = result.get("parsed_value")
    
    return {
        "line_score": score,
        "fill_ratio": min(score / 12.0, 1.0),
        "aspect_ratio": width / max(height, 1),
        "member_count": 1,
        "width": width,
        "height": height,
        "has_digit": any(c.isdigit() for c in raw_text) if raw_text else False,
        "has_suffix": any(c in raw_text.upper() for c in "KMB") if raw_text else False,
        "has_decimal": "." in raw_text if raw_text else False,
        "starts_with_nonzero": (raw_text and raw_text[0].isdigit() and raw_text[0] != '0') if raw_text else False,
        "text_length": len(raw_text) if raw_text else 0,
        "parsed_value": parsed_value,
        "value_in_range": 100 <= parsed_value <= 100_000_000 if parsed_value else False,
        "is_plausible": result.get("is_plausible", False),
    }


def main():
    print("=" * 60)
    print("D4V Training Data Extraction (Standalone)")
    print("=" * 60)
    
    replays_dir = Path("fixtures/replays")
    if not replays_dir.exists():
        print(f"Error: {replays_dir} not found")
        return
    
    # Find all analysis files
    analysis_files = list(replays_dir.glob("*/analysis/combat-ocr/summary.json"))
    print(f"\nFound {len(analysis_files)} replay analyses")
    
    all_samples = []
    all_hits = []
    
    for analysis_path in analysis_files:
        session_id = analysis_path.parent.parent.parent.name
        
        try:
            with open(analysis_path, "r", encoding="utf-8") as f:
                analysis = json.load(f)
            
            # Extract samples from results
            results = analysis.get("results", [])
            session_samples = 0
            session_hits = 0
            
            for result in results:
                features = extract_features_from_result(result)
                confidence = result.get("confidence", 0.0)
                is_confident = result.get("is_confident", False)
                is_plausible = result.get("is_plausible", False)
                
                # Label based on confidence
                if is_confident and is_plausible and confidence >= 0.6:
                    label = 1  # Hit
                    session_hits += 1
                elif confidence < 0.3 or not is_plausible:
                    label = 0  # Miss
                else:
                    continue  # Skip ambiguous
                
                all_samples.append({
                    "features": features,
                    "label": label,
                    "session": session_id,
                })
                session_samples += 1
            
            # Extract stable hits as ground truth
            stable_hits = analysis.get("stable_hits", [])
            for hit in stable_hits:
                all_hits.append({
                    "frame": hit.get("frame_index", 0),
                    "value": hit.get("parsed_value", 0),
                    "x": hit.get("center_x", 0),
                    "y": hit.get("center_y", 0),
                    "session": session_id,
                })
            
            print(f"  {session_id}: {session_samples} samples, {len(stable_hits)} stable hits")
            
        except Exception as e:
            print(f"  {session_id}: Error - {e}")
    
    # Summary
    positive = sum(1 for s in all_samples if s["label"] == 1)
    negative = len(all_samples) - positive
    
    print(f"\n{'=' * 60}")
    print(f"Total Training Samples: {len(all_samples)}")
    print(f"  Positive (hits): {positive}")
    print(f"  Negative (misses): {negative}")
    print(f"  Positive ratio: {positive/len(all_samples) if all_samples else 0:.1%}")
    print(f"\nTotal Ground Truth Hits: {len(all_hits)}")
    
    # Save training data
    output_dir = Path("fixtures")
    output_dir.mkdir(exist_ok=True)
    
    training_data = {
        "samples": all_samples,
        "total_samples": len(all_samples),
        "positive_samples": positive,
        "negative_samples": negative,
    }
    
    with open(output_dir / "training_data.json", "w", encoding="utf-8") as f:
        json.dump(training_data, f, indent=2)
    
    print(f"\nSaved training data to: {output_dir / 'training_data.json'}")
    
    # Save sample benchmark annotations
    benchmarks_dir = output_dir / "benchmarks"
    benchmarks_dir.mkdir(exist_ok=True)
    
    # Group hits by session
    from collections import defaultdict
    hits_by_session = defaultdict(list)
    for hit in all_hits:
        hits_by_session[hit["session"]].append(hit)
    
    for session, hits in list(hits_by_session.items())[:5]:  # First 5 sessions
        annotation = {
            "session_id": session,
            "session_name": session,
            "description": f"Auto-generated from replay analysis",
            "resolution": "1920x1080",
            "ui_scale": 100.0,
            "total_frames": 300,
            "fps": 10.0,
            "hits": [
                {
                    "frame": h["frame"],
                    "value": h["value"],
                    "x": h["x"],
                    "y": h["y"],
                    "damage_type": "direct",
                }
                for h in hits
            ],
        }
        
        with open(benchmarks_dir / f"{session}.json", "w", encoding="utf-8") as f:
            json.dump(annotation, f, indent=2)
    
    print(f"Saved {len(hits_by_session)} benchmark annotations to: {benchmarks_dir}")
    
    print("\n" + "=" * 60)
    print("Next: python scripts/train_confidence_model.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
