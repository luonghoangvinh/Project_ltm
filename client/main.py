"""
Battleship Online Pygame Client
Entry point initializing display, network, game state, and main loop.
"""

import argparse
import sys
import pygame

from client.config import (
    FPS,
    SERVER_HOST,
    SERVER_PORT,
    TITLE,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from client.game_state import GameState
from client.network import NetworkClient
from client.screens.game import GameScreen
from client.screens.history import HistoryScreen
from client.screens.lobby import LobbyScreen
from client.screens.login import LoginScreen
from client.screens.place_ships import PlaceShipsScreen
from client.screens.register import RegisterScreen
from client.screens.replay import ReplayScreen
from client.screens.result import ResultScreen


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Battleship Online Pygame Client")
    parser.add_argument(
        "--host",
        type=str,
        default=SERVER_HOST,
        help=f"Server IP or hostname (default: {SERVER_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=SERVER_PORT,
        help=f"Server TCP port (default: {SERVER_PORT})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    pygame.init()
    pygame.font.init()

    surface = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption(TITLE)
    clock = pygame.time.Clock()

    # Network client and Game state
    network = NetworkClient(host=args.host, port=args.port)
    game_state = GameState()

    # Try connecting to server initially
    network.connect()

    # Instantiate screen handlers
    screens = {
        "login": LoginScreen(surface, game_state, network),
        "register": RegisterScreen(surface, game_state, network),
        "lobby": LobbyScreen(surface, game_state, network),
        "place_ships": PlaceShipsScreen(surface, game_state, network),
        "game": GameScreen(surface, game_state, network),
        "result": ResultScreen(surface, game_state, network),
        "history": HistoryScreen(surface, game_state, network),
        "replay": ReplayScreen(surface, game_state, network),
    }

    current_screen_name = "login"
    current_screen = screens[current_screen_name]
    current_screen.on_enter()

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0  # seconds elapsed

        # 1. Process Pygame OS events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
            current_screen.handle_event(event)

        if not running:
            break

        # 2. Process incoming server messages
        incoming_messages = network.get_messages()
        for msg in incoming_messages:
            msg_type = msg.get("type")
            if msg_type == "DISCONNECTED":
                # Connection was lost
                if current_screen_name not in ("login", "register"):
                    game_state.set_notification("Disconnected from server. Returning to login.", duration=4.0)
                    current_screen.next_screen = "login"

            # Dispatch to active screen
            current_screen.handle_message(msg)

        # 3. Check for screen transitions
        if current_screen.next_screen:
            target = current_screen.next_screen
            current_screen.next_screen = None
            if target in screens:
                current_screen_name = target
                game_state.screen = target
                current_screen = screens[current_screen_name]
                current_screen.on_enter()

        # 4. Update screen state
        current_screen.update(dt)

        # 5. Render
        current_screen.draw()
        pygame.display.flip()

    # Clean shutdown
    network.disconnect()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
