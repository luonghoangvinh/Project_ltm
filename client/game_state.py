"""
Central game state holding session, boards, match info, and player lists.
"""

from typing import Any, Dict, List, Optional
from client.config import GRID_SIZE, SHIPS


class GameState:
    """Encapsulates the entire application and game state."""

    def __init__(self):
        # User session
        self.session_token: str = ""
        self.username: str = ""
        self.elo: int = 1200
        self.screen: str = "login"

        # Match info
        self.match_id: str = ""
        self.opponent: str = ""
        self.opponent_elo: int = 1200
        self.you_go_first: bool = False
        self.my_turn: bool = False
        self.turn_number: int = 1

        # Board states
        # my_board: 0=empty, 1=ship, 2=hit, 3=miss
        self.my_board: List[List[int]] = self._create_empty_board()
        # enemy_board: 0=unknown, 1=hit, 2=miss
        self.enemy_board: List[List[int]] = self._create_empty_board()

        # Ships placement state
        self.placed_ships: List[Dict[str, Any]] = []
        self.ships_to_place: List[Dict[str, Any]] = [dict(s) for s in SHIPS]

        # Lobby / Matchmaking
        self.players: List[Dict[str, Any]] = []
        self.pending_challenge: Optional[Dict[str, Any]] = None

        # In-game negotiations
        self.draw_offered: bool = False
        self.draw_received: bool = False

        # End game summary
        self.game_result: Optional[Dict[str, Any]] = None

        # History and Replay
        self.history: List[Dict[str, Any]] = []
        self.replay_moves: List[Dict[str, Any]] = []
        self.replay_player1: str = ""
        self.replay_player2: str = ""
        self.replay_winner: str = ""
        self.replay_result: str = ""
        self.replay_player1_ships: List[Dict[str, Any]] = []
        self.replay_player2_ships: List[Dict[str, Any]] = []

        # Notification / Error toast
        self.notification: str = ""
        self.notification_color: Optional[tuple] = None
        self.notification_timer: float = 0.0

    @staticmethod
    def _create_empty_board() -> List[List[int]]:
        return [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]

    def reset_match(self) -> None:
        """Resets game board and match states for a new game or returning to lobby."""
        self.match_id = ""
        self.opponent = ""
        self.opponent_elo = 1200
        self.you_go_first = False
        self.my_turn = False
        self.turn_number = 1
        self.my_board = self._create_empty_board()
        self.enemy_board = self._create_empty_board()
        self.placed_ships = []
        self.ships_to_place = [dict(s) for s in SHIPS]
        self.draw_offered = False
        self.draw_received = False
        self.game_result = None

    def reset_boards_only(self) -> None:
        """Resets the boards and ships without clearing opponent info."""
        self.my_board = self._create_empty_board()
        self.enemy_board = self._create_empty_board()
        self.placed_ships = []
        self.ships_to_place = [dict(s) for s in SHIPS]

    def set_notification(self, text: str, duration: float = 3.0, color: Optional[tuple] = None) -> None:
        """Sets a timed notification message."""
        self.notification = text
        self.notification_timer = duration
        self.notification_color = color
