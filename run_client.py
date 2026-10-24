#!/usr/bin/env python3
"""
Battleship Online — launcher script.
Run from the project root: python3 run_client.py [--host HOST] [--port PORT]
"""
import sys
import os

# Ensure project root is on the Python path so 'client.*' imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from client.main import main

if __name__ == "__main__":
    main()
