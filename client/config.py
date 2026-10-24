"""
Configuration settings for Battleship client.
Supports environment variables and default server connection settings.
"""

import os

# Server connection defaults
SERVER_HOST = os.environ.get("BATTLESHIP_HOST", "127.0.0.1")
SERVER_PORT = int(os.environ.get("BATTLESHIP_PORT", "8888"))

# Display configuration
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
FPS = 60
TITLE = "Battleship Online"

# Grid configuration
GRID_SIZE = 10
CELL_SIZE = 40  # 10 * 40 = 400px board
GRID_WIDTH = GRID_SIZE * CELL_SIZE
GRID_HEIGHT = GRID_SIZE * CELL_SIZE

# Ship configurations: sizes [2, 3, 3, 4, 5] matching server ship_id 0..4
SHIPS = [
    {"name": "Destroyer", "size": 2},
    {"name": "Submarine", "size": 3},
    {"name": "Cruiser", "size": 3},
    {"name": "Battleship", "size": 4},
    {"name": "Carrier", "size": 5},
]

# Color Palette (Dark Navy / Modern Theme)
COLOR_BG = (11, 19, 43)              # Deep space navy #0B132B
COLOR_PANEL = (28, 37, 65)           # Dark slate panel #1C2541
COLOR_PANEL_LIGHT = (44, 56, 88)     # Accent panel #2C3858
COLOR_PANEL_BORDER = (58, 80, 107)   # Border steel blue #3A506B
COLOR_TEXT_WHITE = (240, 244, 248)   # Crisp white
COLOR_TEXT_MUTED = (141, 153, 174)   # Subtle gray-blue
COLOR_PRIMARY = (0, 180, 216)        # Cyan blue #00B4D8
COLOR_PRIMARY_HOVER = (72, 202, 228) # Lighter cyan
COLOR_SUCCESS = (16, 185, 129)       # Emerald green
COLOR_SUCCESS_HOVER = (52, 211, 153)
COLOR_DANGER = (239, 68, 68)         # Vivid red
COLOR_DANGER_HOVER = (248, 113, 113)
COLOR_WARNING = (245, 158, 11)       # Amber
COLOR_WATER = (15, 30, 54)           # Dark ocean water
COLOR_WATER_HOVER = (25, 48, 82)
COLOR_GRID_LINE = (38, 60, 95)
COLOR_SHIP = (100, 116, 139)         # Ship steel gray
COLOR_SHIP_BORDER = (148, 163, 184)
COLOR_HIT = (239, 68, 68)            # Red hit
COLOR_MISS = (96, 165, 250)          # Blue/white splash miss
