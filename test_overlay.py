#!/usr/bin/env python3
"""Test script for game overlay - shows overlay with test data."""

import sys
sys.path.insert(0, 'src')

from d4v.overlay.game_overlay import GameOverlayWindow, GameOverlayController
from d4v.domain.session_stats import SessionStats

def main():
    print("Starting Game Overlay Test...")
    
    # Create controller with test data
    controller = GameOverlayController(stats=SessionStats())
    controller.start()
    
    # Add test hits
    print("Adding test hits...")
    controller.add_hit(123456)
    controller.add_hit(78900)
    controller.add_hit(234567)
    controller.add_hit(45678)
    
    print(f"Stats: total={controller.stats.visible_damage_total}, hits={controller.stats.hit_count}")
    print(f"Average: {controller.stats.average_hit}")
    
    # Get view model to verify
    vm = controller.view_model()
    print(f"View Model: AVG={vm.avg_damage_label}, LAST={vm.last_damage_label}, TOTAL={vm.total_damage_label}")
    
    print("\nOpening overlay window...")
    print("The overlay should appear showing the test data.")
    print("Close the window to exit.")
    
    # Create and run overlay
    app = GameOverlayWindow(controller)
    return app.run()

if __name__ == "__main__":
    raise SystemExit(main())
