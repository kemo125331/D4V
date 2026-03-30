#!/usr/bin/env python3
"""Simple tkinter test window."""

import tkinter as tk

def main():
    print("Creating tkinter window...")
    root = tk.Tk()
    root.title("Test Window")
    root.geometry("300x200+100+100")
    
    label = tk.Label(root, text="Hello! This is a test window.", font=("Arial", 14))
    label.pack(pady=20)
    
    btn = tk.Button(root, text="Close", command=root.destroy)
    btn.pack()
    
    print("Window created. It should be visible on screen.")
    print("Close the window to exit.")
    
    root.mainloop()
    print("Window closed.")

if __name__ == "__main__":
    main()
