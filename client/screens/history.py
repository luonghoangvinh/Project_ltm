"""
HistoryScreen for viewing previous Battleship matches and initiating replays.
"""

from typing import Any, Dict, List, Optional
import pygame

from client.config import (
    COLOR_DANGER,
    COLOR_PANEL,
    COLOR_PANEL_BORDER,
    COLOR_PANEL_LIGHT,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_SUCCESS,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_WHITE,
    COLOR_WARNING,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from client.screens.base_screen import BaseScreen


class HistoryScreen(BaseScreen):
    """Displays match history with results and replay launcher."""

    def __init__(self, surface: pygame.Surface, game_state, network):
        super().__init__(surface, game_state, network)

        self.btn_back_rect = pygame.Rect(60, 24, 130, 42)
        self.btn_refresh_rect = pygame.Rect(WINDOW_WIDTH - 190, 24, 130, 42)

        # Main Table Panel
        self.table_rect = pygame.Rect(60, 95, WINDOW_WIDTH - 120, WINDOW_HEIGHT - 135)

        self.scroll_y = 0
        self.row_height = 56
        self.visible_rows = (self.table_rect.height - 60) // self.row_height
        self.is_loading = False

    def on_enter(self) -> None:
        super().on_enter()
        self.scroll_y = 0
        self.is_loading = True
        self._request_history()

    def _request_history(self) -> None:
        if self.network.connected and self.game_state.session_token:
            self.network.send({
                "type": "HISTORY",
                "session_token": self.game_state.session_token,
            })

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.active_modal:
            super().handle_event(event)
            return

        if event.type == pygame.MOUSEWHEEL:
            max_scroll = max(0, len(self.game_state.history) - self.visible_rows)
            self.scroll_y = max(0, min(self.scroll_y - event.y, max_scroll))
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos

            if self.btn_back_rect.collidepoint((mx, my)):
                self.next_screen = "lobby"
                return

            if self.btn_refresh_rect.collidepoint((mx, my)):
                self.is_loading = True
                self._request_history()
                return

            if self.table_rect.collidepoint((mx, my)):
                header_offset = 55
                clicked_y = my - (self.table_rect.y + header_offset)
                if clicked_y >= 0:
                    row_idx = self.scroll_y + (clicked_y // self.row_height)
                    if 0 <= row_idx < len(self.game_state.history):
                        item = self.game_state.history[row_idx]
                        match_id = str(item.get("id") or item.get("match_id") or "")
                        btn_x = self.table_rect.right - 140
                        btn_y = self.table_rect.y + header_offset + (row_idx - self.scroll_y) * self.row_height + 8
                        btn_rect = pygame.Rect(btn_x, btn_y, 110, 38)
                        if btn_rect.collidepoint((mx, my)) or self.table_rect.collidepoint((mx, my)):
                            self._launch_replay(match_id)

    def _launch_replay(self, match_id: str) -> None:
        if not match_id:
            return
        self.game_state.match_id = match_id
        self.network.send({
            "type": "REPLAY",
            "session_token": self.game_state.session_token,
            "match_id": match_id,
        })
        self.next_screen = "replay"

    def handle_message(self, msg: Dict[str, Any]) -> None:
        super().handle_message(msg)
        msg_type = msg.get("type")

        if msg_type == "HISTORY_DATA":
            self.is_loading = False
            matches = msg.get("matches") or msg.get("history") or []
            self.game_state.history = matches

        elif msg_type == "REPLAY_DATA":
            self.game_state.replay_moves = msg.get("moves", [])
            self.game_state.replay_player1 = msg.get("player1", "Player 1")
            self.game_state.replay_player2 = msg.get("player2", "Player 2")
            self.game_state.replay_winner = msg.get("winner", "")
            self.game_state.replay_result = msg.get("result", "")
            self.game_state.replay_player1_ships = msg.get("player1_ships", [])
            self.game_state.replay_player2_ships = msg.get("player2_ships", [])
            self.next_screen = "replay"

    def draw(self) -> None:
        super().draw()
        mouse_pos = pygame.mouse.get_pos()

        # Top Bar
        back_hover = self.btn_back_rect.collidepoint(mouse_pos)
        self.draw_button(self.btn_back_rect, "◀ Lobby", hover=back_hover, bg_color=COLOR_PANEL_LIGHT, font_size=15)

        self.draw_text("MATCH HISTORY", WINDOW_WIDTH // 2, 32, color=COLOR_PRIMARY_HOVER, size=24, bold=True, center=True)

        ref_hover = self.btn_refresh_rect.collidepoint(mouse_pos)
        self.draw_button(self.btn_refresh_rect, "Refresh", hover=ref_hover, bg_color=COLOR_PANEL_LIGHT, font_size=15)

        # Panel
        self.draw_panel(self.table_rect, bg_color=COLOR_PANEL, border_radius=10)

        # Headers
        hy = self.table_rect.y + 16
        self.draw_text("MATCH ID", self.table_rect.x + 30, hy, color=COLOR_TEXT_MUTED, size=14, bold=True)
        self.draw_text("OPPONENT", self.table_rect.x + 220, hy, color=COLOR_TEXT_MUTED, size=14, bold=True)
        self.draw_text("RESULT", self.table_rect.x + 460, hy, color=COLOR_TEXT_MUTED, size=14, bold=True)
        self.draw_text("RATING", self.table_rect.x + 620, hy, color=COLOR_TEXT_MUTED, size=14, bold=True)
        self.draw_text("DATE / TIME", self.table_rect.x + 780, hy, color=COLOR_TEXT_MUTED, size=14, bold=True)
        self.draw_text("ACTION", self.table_rect.right - 130, hy, color=COLOR_TEXT_MUTED, size=14, bold=True)

        pygame.draw.line(
            self.surface,
            COLOR_PANEL_BORDER,
            (self.table_rect.x, self.table_rect.y + 48),
            (self.table_rect.right, self.table_rect.y + 48),
            2,
        )

        header_offset = 55
        history_list = self.game_state.history

        if self.is_loading:
            self.draw_text("Loading match history...", self.table_rect.centerx, self.table_rect.centery, color=COLOR_TEXT_MUTED, size=18, center=True)
        elif not history_list:
            self.draw_text("No past matches found. Play some battles first!", self.table_rect.centerx, self.table_rect.centery, color=COLOR_TEXT_MUTED, size=18, center=True)
        else:
            for i in range(self.visible_rows):
                idx = self.scroll_y + i
                if idx >= len(history_list):
                    break

                m = history_list[idx]
                row_y = self.table_rect.y + header_offset + i * self.row_height

                # Alternate row coloring
                if i % 2 == 1:
                    row_bg = pygame.Rect(self.table_rect.x + 2, row_y, self.table_rect.width - 4, self.row_height)
                    pygame.draw.rect(self.surface, (22, 30, 48), row_bg)

                # Match ID
                mid = str(m.get("id") or m.get("match_id") or "---")
                mid_short = (mid[:10] + "...") if len(mid) > 12 else mid
                self.draw_text(mid_short, self.table_rect.x + 30, row_y + 17, color=COLOR_TEXT_MUTED, size=14)

                # Opponent
                p1 = m.get("player1", "")
                p2 = m.get("player2", "")
                opp = m.get("opponent") or (p2 if p1 == self.game_state.username else p1) or "Opponent"
                self.draw_text(opp, self.table_rect.x + 220, row_y + 17, color=COLOR_TEXT_WHITE, size=16, bold=True)

                # Result
                winner = m.get("winner", "")
                res_type = str(m.get("result", "")).upper()
                user_res = str(m.get("user_result", "")).upper()

                if user_res == "WIN" or (winner and winner == self.game_state.username):
                    res_str = "WIN"
                    res_col = COLOR_SUCCESS
                elif user_res in ("DRAW", "TIE") or res_type in ("DRAW", "TIE") or (not winner and res_type not in ("ONGOING",)):
                    res_str = "DRAW"
                    res_col = COLOR_WARNING
                elif user_res in ("LOSS", "LOSE") or (winner and winner != self.game_state.username):
                    res_str = "LOSS"
                    res_col = COLOR_DANGER
                elif res_type == "ONGOING" or user_res == "ONGOING":
                    res_str = "ONGOING"
                    res_col = COLOR_TEXT_MUTED
                else:
                    res_str = "LOSS"
                    res_col = COLOR_DANGER

                self.draw_text(res_str, self.table_rect.x + 460, row_y + 17, color=res_col, size=16, bold=True)

                # Rating change
                elo_diff = m.get("elo_change")
                if elo_diff is None:
                    # Try calculating from player1/player2 elo fields
                    if p1 == self.game_state.username and "player1_elo_after" in m and "player1_elo_before" in m:
                        elo_diff = (m["player1_elo_after"] or 0) - (m["player1_elo_before"] or 0)
                    elif p2 == self.game_state.username and "player2_elo_after" in m and "player2_elo_before" in m:
                        elo_diff = (m["player2_elo_after"] or 0) - (m["player2_elo_before"] or 0)
                    else:
                        elo_diff = 0

                elo_sign = f"+{elo_diff}" if elo_diff > 0 else str(elo_diff)
                elo_col = COLOR_SUCCESS if elo_diff > 0 else (COLOR_DANGER if elo_diff < 0 else COLOR_TEXT_MUTED)
                self.draw_text(elo_sign, self.table_rect.x + 620, row_y + 17, color=elo_col, size=16)

                # Date
                date_str = str(m.get("start_time") or m.get("date") or m.get("created_at") or "---")
                # Truncate seconds or fractional seconds if present
                if len(date_str) > 16:
                    date_str = date_str[:16].replace("T", " ")
                self.draw_text(date_str, self.table_rect.x + 780, row_y + 17, color=COLOR_TEXT_MUTED, size=14)

                # Replay Button
                btn_rect = pygame.Rect(self.table_rect.right - 140, row_y + 9, 110, 36)
                r_hover = btn_rect.collidepoint(mouse_pos)
                self.draw_button(btn_rect, "▶ Replay", hover=r_hover, bg_color=COLOR_PRIMARY, font_size=14)

        # Draw modal and toast
        self.draw_modal()
        self.draw_toast()
