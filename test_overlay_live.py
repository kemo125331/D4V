#!/usr/bin/env python3
"""Test overlay with live-preview style updates."""

import sys
sys.path.insert(0, 'src')

from d4v.overlay.game_overlay import GameOverlayWindow, GameOverlayController
from d4v.domain.session_stats import SessionStats
import tkinter as tk
import random

def main():
    print("Starting Live Overlay Test...")
    
    # Create shared stats
    stats = SessionStats()
    
    # Create controller
    controller = GameOverlayController(stats=stats)
    
    # Create overlay window with debug mode (visible border)
    overlay_app = GameOverlayWindow(controller, auto_start=False, debug=True)
    controller.start()
    
    # Simulate live hits
    def add_random_hit():
        value = random.randint(10000, 500000)
        stats.add_hit(0, 0, value, 1.0)
        controller.last_hit = value
        print(f"Added hit: {value:,}")
        
        # Update overlay display
        vm = controller.view_model()
        overlay_app._apply_view_model(vm)
        overlay_app._update_position()
        
        # Schedule next hit
        overlay_app.root.after(500, add_random_hit)
    
    # Initial display
    vm = controller.view_model()
    overlay_app._apply_view_model(vm)
    
    print("Overlay will show random hits every 500ms")
    print("The window should have a RED border for visibility testing.")
    print("Close the window to exit.")
    
    return overlay_app.run()

if __name__ == "__main__":
    raise SystemExit(main())
