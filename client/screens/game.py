"""
GameScreen for active Battleship gameplay, firing missiles, and managing match events.
"""

from typing import Any, Dict, List, Optional
import pygame

from client.config import (
    CELL_SIZE,
    COLOR_DANGER,
    COLOR_PANEL,
    COLOR_PANEL_BORDER,
    COLOR_PANEL_LIGHT,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_SUCCESS,
    COLOR_SUCCESS_HOVER,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_WHITE,
    COLOR_WARNING,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from client.screens.base_screen import BaseScreen

# Mapping ship sizes to display names
SIZE_TO_NAME = {
    5: "Carrier",
    4: "Battleship",
    3: "Cruiser",
    2: "Destroyer",
}


class GameScreen(BaseScreen):
    """Main battle screen displaying both fleets, turn management, and combat logs."""

    def __init__(self, surface: pygame.Surface, game_state, network):
        super().__init__(surface, game_state, network)

        # Board layout coordinates
        # Left board: My fleet
        self.my_board_x = 100
        self.my_board_y = 150

        # Right board: Enemy radar
        self.enemy_board_x = 780
        self.enemy_board_y = 150

        # Bottom action buttons
        self.btn_draw_rect = pygame.Rect(WINDOW_WIDTH // 2 - 190, WINDOW_HEIGHT - 70, 180, 44)
        self.btn_surrender_rect = pygame.Rect(WINDOW_WIDTH // 2 + 10, WINDOW_HEIGHT - 70, 180, 44)

        # Combat logs
        self.combat_logs: List[str] = []
        self.waiting_fire_ack: bool = False
        self.announcement: str = ""
        self.announcement_timer: float = 0.0

    def on_enter(self) -> None:
        super().on_enter()
        self.waiting_fire_ack = False
        self.combat_logs = ["Battle commenced! Good luck Commander."]
        self.announcement = ""
        self.announcement_timer = 0.0

    def _coord_str(self, row: int, col: int) -> str:
        return f"{chr(65 + col)}{row + 1}"

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.active_modal:
            super().handle_event(event)
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos

            # Fire on enemy board
            if self.game_state.my_turn and not self.waiting_fire_ack:
                cell = self.get_grid_cell_from_pos((mx, my), self.enemy_board_x, self.enemy_board_y)
                if cell:
                    r, c = cell
                    # Only fire if cell hasn't been targeted yet (0 = untargeted)
                    if self.game_state.enemy_board[r][c] == 0:
                        self._fire(r, c)
                        return

            # Offer Draw Button
            if self.btn_draw_rect.collidepoint((mx, my)) and not self.game_state.draw_offered:
                self._offer_draw()
                return

            # Surrender Button
            if self.btn_surrender_rect.collidepoint((mx, my)):
                self._confirm_surrender()
                return

    def _fire(self, row: int, col: int) -> None:
        self.waiting_fire_ack = True
        self.game_state.my_turn = False
        self.network.send({
            "type": "FIRE",
            "session_token": self.game_state.session_token,
            "match_id": self.game_state.match_id,
            "row": row,
            "col": col,
        })
        self._add_log(f"Turn {self.game_state.turn_number}: Firing missile at {self._coord_str(row, col)}...")

    def _offer_draw(self) -> None:
        self.game_state.draw_offered = True
        self.network.send({
            "type": "DRAW_OFFER",
            "session_token": self.game_state.session_token,
            "match_id": self.game_state.match_id,
        })
        self.game_state.set_notification("Draw offer sent to opponent.", duration=3.0, color=COLOR_PRIMARY)
        self._add_log("You offered a draw to opponent.")

    def _confirm_surrender(self) -> None:
        def on_surrender():
            self.network.send({
                "type": "SURRENDER",
                "session_token": self.game_state.session_token,
                "match_id": self.game_state.match_id,
            })
            self.game_state.set_notification("Surrender submitted.", duration=2.0, color=COLOR_DANGER)

        self.show_modal(
            title="SURRENDER CONFIRMATION",
            message="Are you certain you want to forfeit this battle?\nThis will count as an immediate defeat.",
            buttons=[
                {"text": "Surrender", "action": on_surrender, "color": COLOR_DANGER},
                {"text": "Cancel", "action": lambda: None, "color": COLOR_PANEL_LIGHT},
            ],
        )

    def _add_log(self, text: str) -> None:
        self.combat_logs.append(text)
        if len(self.combat_logs) > 6:
            self.combat_logs.pop(0)

    def _show_announcement(self, text: str, duration: float = 3.0) -> None:
        self.announcement = text
        self.announcement_timer = duration

    def handle_message(self, msg: Dict[str, Any]) -> None:
        super().handle_message(msg)
        msg_type = msg.get("type")

        if msg_type == "YOUR_TURN":
            self.game_state.my_turn = True
            self.waiting_fire_ack = False
            self.game_state.turn_number += 1

        elif msg_type == "FIRE_RESULT":
            self.waiting_fire_ack = False
            r = int(msg.get("row", 0))
            c = int(msg.get("col", 0))
            result = str(msg.get("result", "MISS")).upper()
            sunk = bool(msg.get("sunk", False))
            ship_size = int(msg.get("ship_size", 0))
            game_over = bool(msg.get("game_over", False))

            # Update enemy board (1=hit, 2=miss)
            self.game_state.enemy_board[r][c] = 1 if result == "HIT" else 2

            coord = self._coord_str(r, c)
            if sunk:
                s_name = SIZE_TO_NAME.get(ship_size, f"{ship_size}-cell ship")
                self._add_log(f"DIRECT HIT on {coord}! You SUNK opponent's {s_name}!")
                self._show_announcement(f"ENEMY {s_name.upper()} SUNK!", duration=3.0)
            elif result == "HIT":
                self._add_log(f"HIT at {coord}!")
                self._show_announcement("DIRECT HIT!", duration=1.5)
            else:
                self._add_log(f"MISSED at {coord}.")

            if game_over:
                self.game_state.game_result = {
                    "winner": msg.get("winner", self.game_state.username),
                    "reason": "All enemy ships destroyed",
                    "elo_change": msg.get("elo_change", 0),
                    "new_elo": msg.get("new_elo", self.game_state.elo),
                }
                self.next_screen = "result"

        elif msg_type == "OPPONENT_FIRED":
            r = int(msg.get("row", 0))
            c = int(msg.get("col", 0))
            result = str(msg.get("result", "MISS")).upper()
            sunk = bool(msg.get("sunk", False))
            ship_size = int(msg.get("ship_size", 0))

            # Update my board (2=hit, 3=miss)
            self.game_state.my_board[r][c] = 2 if result == "HIT" else 3

            coord = self._coord_str(r, c)
            if sunk:
                s_name = SIZE_TO_NAME.get(ship_size, "Ship")
                self._add_log(f"OPPONENT HIT {coord}! Your {s_name} was SUNK!")
                self._show_announcement(f"YOUR {s_name.upper()} WAS SUNK!", duration=3.0)
            elif result == "HIT":
                self._add_log(f"Opponent hit your ship at {coord}!")
            else:
                self._add_log(f"Opponent missed at {coord}.")

        elif msg_type == "DRAW_OFFER":
            # Opponent offered draw
            self._prompt_incoming_draw()

        elif msg_type == "DRAW_RESULT":
            accepted = bool(msg.get("accepted", False))
            res_msg = msg.get("message", "Draw response received.")
            if not accepted:
                self.game_state.set_notification(f"Draw declined: {res_msg}", duration=3.0, color=COLOR_WARNING)
                self.game_state.draw_offered = False

        elif msg_type == "GAME_OVER":
            self.close_modal()
            self.game_state.game_result = {
                "winner": msg.get("winner", ""),
                "reason": msg.get("reason", "Game finished"),
                "elo_change": msg.get("elo_change", 0),
                "new_elo": msg.get("new_elo", self.game_state.elo),
            }
            self.next_screen = "result"

    def _prompt_incoming_draw(self) -> None:
        def on_accept():
            self.network.send({
                "type": "DRAW_REPLY",
                "session_token": self.game_state.session_token,
                "match_id": self.game_state.match_id,
                "accept": True,
            })

        def on_decline():
            self.network.send({
                "type": "DRAW_REPLY",
                "session_token": self.game_state.session_token,
                "match_id": self.game_state.match_id,
                "accept": False,
            })

        self.show_modal(
            title="DRAW OFFER",
            message=f"Opponent {self.game_state.opponent} offers a draw.\nDo you wish to end this battle peacefully?",
            buttons=[
                {"text": "Accept Draw", "action": on_accept, "color": COLOR_SUCCESS},
                {"text": "Decline", "action": on_decline, "color": COLOR_DANGER},
            ],
        )

    def update(self, dt: float = 0.016) -> None:
        super().update(dt)
        if self.announcement_timer > 0:
            self.announcement_timer -= dt
            if self.announcement_timer <= 0:
                self.announcement = ""

    def draw(self) -> None:
        super().draw()
        mouse_pos = pygame.mouse.get_pos()

        # Top Status Bar
        match_info = f"Match: #{self.game_state.match_id[:8]}..." if len(self.game_state.match_id) > 8 else f"Match: {self.game_state.match_id}"
        self.draw_text(match_info, 60, 24, color=COLOR_TEXT_MUTED, size=15)

        # Turn indicator banner (Center)
        turn_box = pygame.Rect(WINDOW_WIDTH // 2 - 200, 16, 400, 52)
        if self.game_state.my_turn:
            turn_bg = (16, 70, 45)
            turn_border = COLOR_SUCCESS
            turn_text = "YOUR TURN - Fire at enemy radar!"
            turn_col = COLOR_SUCCESS_HOVER
        else:
            turn_bg = (30, 42, 65)
            turn_border = COLOR_PANEL_BORDER
            turn_text = f"{self.game_state.opponent}'s turn... waiting"
            turn_col = COLOR_TEXT_MUTED

        pygame.draw.rect(self.surface, turn_bg, turn_box, border_radius=8)
        pygame.draw.rect(self.surface, turn_border, turn_box, width=2, border_radius=8)
        self.draw_text(turn_text, turn_box.centerx, turn_box.centery, color=turn_col, size=18, bold=True, center=True)

        # Opponent info top right
        opp_info = f"Enemy: {self.game_state.opponent} ({self.game_state.opponent_elo} ELO)"
        self.draw_text(opp_info, WINDOW_WIDTH - 60, 24, color=COLOR_DANGER, size=16, bold=True, right=True)

        # Hover cell on enemy radar
        enemy_hover_cell = None
        if self.game_state.my_turn and not self.waiting_fire_ack:
            enemy_hover_cell = self.get_grid_cell_from_pos(mouse_pos, self.enemy_board_x, self.enemy_board_y)

        # Left Grid: My Fleet
        self.draw_grid(
            top_left_x=self.my_board_x,
            top_left_y=self.my_board_y,
            board_data=self.game_state.my_board,
            is_enemy=False,
            title="MY FLEET",
        )

        # Right Grid: Enemy Radar
        self.draw_grid(
            top_left_x=self.enemy_board_x,
            top_left_y=self.enemy_board_y,
            board_data=self.game_state.enemy_board,
            is_enemy=True,
            hover_cell=enemy_hover_cell,
            title="ENEMY RADAR",
        )

        # Floating Announcement Banner
        if self.announcement:
            ann_rect = pygame.Rect(WINDOW_WIDTH // 2 - 250, 80, 500, 42)
            pygame.draw.rect(self.surface, (220, 38, 38), ann_rect, border_radius=8)
            pygame.draw.rect(self.surface, COLOR_TEXT_WHITE, ann_rect, width=2, border_radius=8)
            self.draw_text(self.announcement, ann_rect.centerx, ann_rect.centery, color=COLOR_TEXT_WHITE, size=19, bold=True, center=True)

        # Combat Log Panel (Center between boards or bottom)
        log_panel = pygame.Rect(self.my_board_x, 575, 560, 120)
        self.draw_panel(log_panel, bg_color=COLOR_PANEL, border_radius=8)
        self.draw_text("COMBAT LOG", log_panel.x + 14, log_panel.y + 10, color=COLOR_PRIMARY_HOVER, size=13, bold=True)

        log_y = log_panel.y + 32
        for log in self.combat_logs[-4:]:
            self.draw_text(log, log_panel.x + 14, log_y, color=COLOR_TEXT_WHITE, size=14)
            log_y += 20

        # Action Buttons
        draw_hover = self.btn_draw_rect.collidepoint(mouse_pos)
        draw_txt = "Draw Offered" if self.game_state.draw_offered else "Offer Draw"
        self.draw_button(
            self.btn_draw_rect,
            draw_txt,
            hover=draw_hover,
            disabled=self.game_state.draw_offered,
            bg_color=COLOR_PANEL_LIGHT,
            font_size=15,
        )

        surr_hover = self.btn_surrender_rect.collidepoint(mouse_pos)
        self.draw_button(self.btn_surrender_rect, "Surrender", hover=surr_hover, bg_color=COLOR_DANGER, font_size=15)

        # Draw modal and toast
        self.draw_modal()
        self.draw_toast()
