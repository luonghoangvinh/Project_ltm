"""
ReplayScreen for step-by-step match playback and analysis.
"""

from typing import Any, Dict, List, Optional, Tuple
import pygame

from client.config import (
    CELL_SIZE,
    COLOR_DANGER,
    COLOR_PANEL,
    COLOR_PANEL_LIGHT,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_SUCCESS,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_WHITE,
    COLOR_WARNING,
    GRID_SIZE,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from client.screens.base_screen import BaseScreen


class ReplayScreen(BaseScreen):
    """Visualizes recorded matches move-by-move on dual boards."""

    def __init__(self, surface: pygame.Surface, game_state, network):
        super().__init__(surface, game_state, network)

        # Header Navigation
        self.btn_back_rect = pygame.Rect(60, 20, 140, 40)

        # Dual Boards layout
        self.p1_board_x = 120
        self.p1_board_y = 140

        self.p2_board_x = 760
        self.p2_board_y = 140

        # Controls panel at bottom
        self.ctrl_panel_rect = pygame.Rect(WINDOW_WIDTH // 2 - 320, 580, 640, 90)

        btn_y = self.ctrl_panel_rect.y + 36
        self.btn_first_rect = pygame.Rect(self.ctrl_panel_rect.x + 30, btn_y, 70, 38)
        self.btn_prev_rect = pygame.Rect(self.ctrl_panel_rect.x + 115, btn_y, 80, 38)
        self.btn_play_rect = pygame.Rect(self.ctrl_panel_rect.x + 210, btn_y, 110, 38)
        self.btn_next_rect = pygame.Rect(self.ctrl_panel_rect.x + 335, btn_y, 80, 38)
        self.btn_last_rect = pygame.Rect(self.ctrl_panel_rect.x + 430, btn_y, 70, 38)
        self.btn_speed_rect = pygame.Rect(self.ctrl_panel_rect.x + 515, btn_y, 90, 38)

        # Replay playback state
        self.moves: List[Dict[str, Any]] = []
        self.current_step: int = 0
        self.auto_playing: bool = False
        self.play_timer: float = 0.0
        self.play_speed: float = 0.8  # seconds per step
        self.last_move_info: str = "Ready to start replay."

        # Board states up to current_step
        self.p1_board = self._create_empty_board()
        self.p2_board = self._create_empty_board()

    @staticmethod
    def _create_empty_board() -> List[List[int]]:
        return [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]

    def on_enter(self) -> None:
        super().on_enter()
        self.moves = self.game_state.replay_moves
        self.current_step = 0
        self.auto_playing = False
        self.play_timer = 0.0
        self._recompute_boards()

    def handle_message(self, msg: Dict[str, Any]) -> None:
        super().handle_message(msg)
        if msg.get("type") == "REPLAY_DATA":
            self.game_state.replay_moves = msg.get("moves", [])
            self.game_state.replay_player1 = msg.get("player1", "Player 1")
            self.game_state.replay_player2 = msg.get("player2", "Player 2")
            self.game_state.replay_winner = msg.get("winner", "")
            self.moves = self.game_state.replay_moves
            self.current_step = 0
            self.auto_playing = False
            self._recompute_boards()

    def _recompute_boards(self) -> None:
        """Rebuilds the board states by executing moves from index 0 to current_step - 1."""
        self.p1_board = self._create_empty_board()
        self.p2_board = self._create_empty_board()

        p1_name = self.game_state.replay_player1 or "Player 1"
        p2_name = self.game_state.replay_player2 or "Player 2"

        if not self.moves or self.current_step == 0:
            self.last_move_info = "Move 0: Initial battle setup."
            return

        last_move = None
        for step_idx in range(self.current_step):
            m = self.moves[step_idx]
            last_move = m
            shooter = m.get("player", "")
            r = int(m.get("row", 0))
            c = int(m.get("col", 0))
            res = str(m.get("result", "MISS")).upper()
            val = 1 if res == "HIT" else 2

            # The victim board receives the shot
            if shooter == p1_name:
                self.p2_board[r][c] = val
            else:
                self.p1_board[r][c] = val

        if last_move:
            shooter = last_move.get("player", "Player")
            r = int(last_move.get("row", 0))
            c = int(last_move.get("col", 0))
            res = str(last_move.get("result", "MISS")).upper()
            sunk = bool(last_move.get("sunk", False))
            coord = f"{chr(65 + c)}{r + 1}"
            sunk_msg = " (SUNK SHIP!)" if sunk else ""
            self.last_move_info = f"Move {self.current_step}: {shooter} fired at {coord} → {res}{sunk_msg}"

    def _step_next(self) -> None:
        if self.current_step < len(self.moves):
            self.current_step += 1
            self._recompute_boards()
        else:
            self.auto_playing = False

    def _step_prev(self) -> None:
        if self.current_step > 0:
            self.current_step -= 1
            self._recompute_boards()

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.active_modal:
            super().handle_event(event)
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RIGHT:
                self._step_next()
            elif event.key == pygame.K_LEFT:
                self._step_prev()
            elif event.key == pygame.K_SPACE:
                self.auto_playing = not self.auto_playing

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos

            if self.btn_back_rect.collidepoint((mx, my)):
                self.auto_playing = False
                self.next_screen = "history"
                return

            if self.btn_first_rect.collidepoint((mx, my)):
                self.auto_playing = False
                self.current_step = 0
                self._recompute_boards()
                return

            if self.btn_prev_rect.collidepoint((mx, my)):
                self.auto_playing = False
                self._step_prev()
                return

            if self.btn_play_rect.collidepoint((mx, my)):
                self.auto_playing = not self.auto_playing
                return

            if self.btn_next_rect.collidepoint((mx, my)):
                self.auto_playing = False
                self._step_next()
                return

            if self.btn_last_rect.collidepoint((mx, my)):
                self.auto_playing = False
                self.current_step = len(self.moves)
                self._recompute_boards()
                return

            if self.btn_speed_rect.collidepoint((mx, my)):
                # Cycle speed: 0.8s -> 0.4s -> 0.2s -> 1.2s
                speeds = [0.8, 0.4, 0.2, 1.2]
                curr_idx = speeds.index(self.play_speed) if self.play_speed in speeds else 0
                self.play_speed = speeds[(curr_idx + 1) % len(speeds)]
                return

    def update(self, dt: float = 0.016) -> None:
        super().update(dt)

        if self.auto_playing:
            self.play_timer += dt
            if self.play_timer >= self.play_speed:
                self.play_timer = 0.0
                if self.current_step < len(self.moves):
                    self._step_next()
                else:
                    self.auto_playing = False

    def draw(self) -> None:
        super().draw()
        mouse_pos = pygame.mouse.get_pos()

        # Top Bar
        b_hover = self.btn_back_rect.collidepoint(mouse_pos)
        self.draw_button(self.btn_back_rect, "◀ Back to History", hover=b_hover, bg_color=COLOR_PANEL_LIGHT, font_size=14)

        self.draw_text("MATCH REPLAY", WINDOW_WIDTH // 2, 28, color=COLOR_PRIMARY_HOVER, size=24, bold=True, center=True)

        mid_text = f"Match ID: {self.game_state.match_id}"
        self.draw_text(mid_text, WINDOW_WIDTH // 2, 54, color=COLOR_TEXT_MUTED, size=14, center=True)

        p1_name = self.game_state.replay_player1 or "Player 1"
        p2_name = self.game_state.replay_player2 or "Player 2"

        # Determine last fired cell to highlight
        p1_highlight = None
        p2_highlight = None
        if self.current_step > 0 and self.current_step <= len(self.moves):
            lm = self.moves[self.current_step - 1]
            lr, lc = int(lm.get("row", 0)), int(lm.get("col", 0))
            if lm.get("player") == p1_name:
                p2_highlight = (lr, lc)
            else:
                p1_highlight = (lr, lc)

        # Draw Player 1 Board (Left)
        p1_title = f"{p1_name}'s Board (Defending)"
        self.draw_grid(
            top_left_x=self.p1_board_x,
            top_left_y=self.p1_board_y,
            board_data=self.p1_board,
            is_enemy=True,
            hover_cell=p1_highlight,
            title=p1_title,
        )

        # Draw Player 2 Board (Right)
        p2_title = f"{p2_name}'s Board (Defending)"
        self.draw_grid(
            top_left_x=self.p2_board_x,
            top_left_y=self.p2_board_y,
            board_data=self.p2_board,
            is_enemy=True,
            hover_cell=p2_highlight,
            title=p2_title,
        )

        # Controls Panel
        self.draw_panel(self.ctrl_panel_rect, bg_color=COLOR_PANEL, border_radius=10)

        # Move Counter & Last Move Summary
        total_moves = len(self.moves)
        counter_txt = f"Move {self.current_step} of {total_moves}"
        self.draw_text(counter_txt, self.ctrl_panel_rect.centerx, self.ctrl_panel_rect.y + 16, color=COLOR_PRIMARY_HOVER, size=16, bold=True, center=True)

        # Info line above controls
        self.draw_text(self.last_move_info, WINDOW_WIDTH // 2, 555, color=COLOR_TEXT_WHITE, size=15, bold=True, center=True)

        # First Button
        f_hover = self.btn_first_rect.collidepoint(mouse_pos)
        self.draw_button(self.btn_first_rect, "⏮", hover=f_hover, disabled=self.current_step == 0, bg_color=COLOR_PANEL_LIGHT, font_size=16)

        # Prev Button
        p_hover = self.btn_prev_rect.collidepoint(mouse_pos)
        self.draw_button(self.btn_prev_rect, "◀ Prev", hover=p_hover, disabled=self.current_step == 0, bg_color=COLOR_PANEL_LIGHT, font_size=15)

        # Play / Pause Button
        play_label = "⏸ Pause" if self.auto_playing else "▶ Play"
        play_bg = COLOR_SUCCESS if not self.auto_playing else COLOR_WARNING
        play_hover = self.btn_play_rect.collidepoint(mouse_pos)
        self.draw_button(self.btn_play_rect, play_label, hover=play_hover, disabled=total_moves == 0, bg_color=play_bg, font_size=15)

        # Next Button
        n_hover = self.btn_next_rect.collidepoint(mouse_pos)
        self.draw_button(self.btn_next_rect, "Next ▶", hover=n_hover, disabled=self.current_step >= total_moves, bg_color=COLOR_PANEL_LIGHT, font_size=15)

        # Last Button
        l_hover = self.btn_last_rect.collidepoint(mouse_pos)
        self.draw_button(self.btn_last_rect, "⏭", hover=l_hover, disabled=self.current_step >= total_moves, bg_color=COLOR_PANEL_LIGHT, font_size=16)

        # Speed Button
        speed_label = f"{self.play_speed}s"
        s_hover = self.btn_speed_rect.collidepoint(mouse_pos)
        self.draw_button(self.btn_speed_rect, speed_label, hover=s_hover, bg_color=COLOR_PANEL_LIGHT, font_size=14)

        # Toast
        self.draw_toast()
