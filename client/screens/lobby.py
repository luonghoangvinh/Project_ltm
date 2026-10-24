"""
LobbyScreen for matchmaking, challenging online players, and navigating to history.
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


class LobbyScreen(BaseScreen):
    """Displays the player lobby with online users and challenge options."""

    def __init__(self, surface: pygame.Surface, game_state, network):
        super().__init__(surface, game_state, network)

        # Header buttons
        self.btn_refresh_rect = pygame.Rect(WINDOW_WIDTH - 420, 24, 110, 42)
        self.btn_history_rect = pygame.Rect(WINDOW_WIDTH - 295, 24, 130, 42)
        self.btn_logout_rect = pygame.Rect(WINDOW_WIDTH - 150, 24, 110, 42)

        # Main Table Panel
        self.table_rect = pygame.Rect(60, 100, WINDOW_WIDTH - 120, WINDOW_HEIGHT - 140)

        # Scroll state for player list
        self.scroll_y = 0
        self.row_height = 54
        self.visible_rows = (self.table_rect.height - 60) // self.row_height

        self.pending_challenge_to: Optional[str] = None
        self.challenge_cooldown: float = 0.0

    def on_enter(self) -> None:
        super().on_enter()
        self.game_state.reset_match()
        self.pending_challenge_to = None
        self.challenge_cooldown = 0.0
        self.scroll_y = 0
        self._request_player_list()

    def _request_player_list(self) -> None:
        if self.network.connected and self.game_state.session_token:
            self.network.send({
                "type": "LIST_PLAYERS",
                "session_token": self.game_state.session_token,
            })

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.active_modal:
            super().handle_event(event)
            return

        # Mouse wheel scrolling
        if event.type == pygame.MOUSEWHEEL:
            max_scroll = max(0, len(self.game_state.players) - self.visible_rows)
            self.scroll_y = max(0, min(self.scroll_y - event.y, max_scroll))
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos

            # Header buttons
            if self.btn_refresh_rect.collidepoint((mx, my)):
                self._request_player_list()
                self.game_state.set_notification("Player list refreshed", duration=1.5, color=COLOR_PANEL_LIGHT)
                return

            if self.btn_history_rect.collidepoint((mx, my)):
                self.next_screen = "history"
                return

            if self.btn_logout_rect.collidepoint((mx, my)):
                self._handle_logout()
                return

            # Player rows challenge button clicks
            if self.table_rect.collidepoint((mx, my)):
                header_offset = 55
                clicked_y = my - (self.table_rect.y + header_offset)
                if clicked_y >= 0:
                    row_idx = self.scroll_y + (clicked_y // self.row_height)
                    if 0 <= row_idx < len(self.game_state.players):
                        p = self.game_state.players[row_idx]
                        btn_x = self.table_rect.right - 150
                        btn_y = self.table_rect.y + header_offset + (row_idx - self.scroll_y) * self.row_height + 8
                        btn_rect = pygame.Rect(btn_x, btn_y, 120, 36)

                        is_self = (p.get("username") == self.game_state.username)
                        p_status = p.get("status", "ONLINE").upper()
                        is_available = p_status in ("ONLINE", "IN_LOBBY")
                        if btn_rect.collidepoint((mx, my)) and not is_self and is_available and not self.pending_challenge_to:
                            self._send_challenge(p.get("username", ""))

    def _send_challenge(self, target_user: str) -> None:
        if not target_user:
            return
        self.pending_challenge_to = target_user
        self.challenge_cooldown = 15.0  # 15s timeout
        self.network.send({
            "type": "CHALLENGE",
            "session_token": self.game_state.session_token,
            "target": target_user,
            "opponent": target_user,
        })
        self.game_state.set_notification(f"Challenged {target_user}! Waiting for response...", duration=4.0, color=COLOR_PRIMARY)

    def _handle_logout(self) -> None:
        if self.network.connected and self.game_state.session_token:
            self.network.send({
                "type": "LOGOUT",
                "session_token": self.game_state.session_token,
            })
        self.game_state.session_token = ""
        self.game_state.username = ""
        self.next_screen = "login"

    def handle_message(self, msg: Dict[str, Any]) -> None:
        super().handle_message(msg)
        msg_type = msg.get("type")

        if msg_type in ("PLAYER_LIST", "PLAYER_UPDATE"):
            self.game_state.players = msg.get("players", [])

        elif msg_type == "CHALLENGE":
            # Incoming challenge from another player
            challenger = msg.get("from") or msg.get("challenger") or "Someone"
            match_id = msg.get("match_id", "")
            self._prompt_incoming_challenge(challenger, match_id)

        elif msg_type == "CHALLENGE_REPLY":
            accepted = msg.get("accept", False)
            opponent = msg.get("challenger") or msg.get("from") or msg.get("opponent") or "Opponent"
            self.pending_challenge_to = None
            if not accepted:
                self.game_state.set_notification(f"{opponent} declined the challenge.", duration=3.5, color=COLOR_WARNING)

        elif msg_type == "MATCH_FOUND":
            self.pending_challenge_to = None
            self.close_modal()
            self.game_state.match_id = msg.get("match_id", "")
            self.game_state.opponent = msg.get("opponent", "Opponent")
            self.game_state.opponent_elo = int(msg.get("opponent_elo", 1200))
            self.game_state.you_go_first = bool(msg.get("you_go_first", False))
            self.game_state.set_notification(f"Match found against {self.game_state.opponent}!", duration=2.0, color=COLOR_SUCCESS)
            self.next_screen = "place_ships"

    def _prompt_incoming_challenge(self, challenger: str, match_id: str) -> None:
        def on_accept():
            self.network.send({
                "type": "CHALLENGE_REPLY",
                "session_token": self.game_state.session_token,
                "challenger": challenger,
                "from": challenger,
                "accept": True,
                "match_id": match_id,
            })

        def on_decline():
            self.network.send({
                "type": "CHALLENGE_REPLY",
                "session_token": self.game_state.session_token,
                "challenger": challenger,
                "from": challenger,
                "accept": False,
                "match_id": match_id,
            })

        self.show_modal(
            title="CHALLENGE RECEIVED",
            message=f"Player '{challenger}' has challenged you\nto a Battleship duel!",
            buttons=[
                {"text": "Accept", "action": on_accept, "color": COLOR_SUCCESS},
                {"text": "Decline", "action": on_decline, "color": COLOR_DANGER},
            ],
        )

    def update(self, dt: float = 0.016) -> None:
        super().update(dt)
        if self.challenge_cooldown > 0:
            self.challenge_cooldown -= dt
            if self.challenge_cooldown <= 0:
                self.pending_challenge_to = None

    def draw(self) -> None:
        super().draw()
        mouse_pos = pygame.mouse.get_pos()

        # Top Bar: Logo & Current User Info
        self.draw_text("BATTLESHIP LOBBY", 60, 30, color=COLOR_PRIMARY_HOVER, size=26, bold=True)

        user_badge = f"{self.game_state.username} ({self.game_state.elo} ELO)"
        self.draw_text(user_badge, 340, 34, color=COLOR_SUCCESS, size=18, bold=True)

        # Header Buttons
        ref_hover = self.btn_refresh_rect.collidepoint(mouse_pos)
        self.draw_button(self.btn_refresh_rect, "Refresh", hover=ref_hover, bg_color=COLOR_PANEL_LIGHT, font_size=15)

        his_hover = self.btn_history_rect.collidepoint(mouse_pos)
        self.draw_button(self.btn_history_rect, "Match History", hover=his_hover, bg_color=COLOR_PANEL_LIGHT, font_size=15)

        log_hover = self.btn_logout_rect.collidepoint(mouse_pos)
        self.draw_button(self.btn_logout_rect, "Logout", hover=log_hover, bg_color=COLOR_DANGER, font_size=15)

        # Main Table Panel
        self.draw_panel(self.table_rect, bg_color=COLOR_PANEL, border_radius=10)

        # Table Header
        header_y = self.table_rect.y + 16
        self.draw_text("PLAYER", self.table_rect.x + 30, header_y, color=COLOR_TEXT_MUTED, size=15, bold=True)
        self.draw_text("RATING", self.table_rect.x + 360, header_y, color=COLOR_TEXT_MUTED, size=15, bold=True)
        self.draw_text("STATUS", self.table_rect.x + 580, header_y, color=COLOR_TEXT_MUTED, size=15, bold=True)
        self.draw_text("ACTION", self.table_rect.right - 140, header_y, color=COLOR_TEXT_MUTED, size=15, bold=True)

        pygame.draw.line(
            self.surface,
            COLOR_PANEL_BORDER,
            (self.table_rect.x, self.table_rect.y + 48),
            (self.table_rect.right, self.table_rect.y + 48),
            2,
        )

        # Player rows
        header_offset = 55
        players = self.game_state.players

        if not players:
            self.draw_text(
                "No other players online right now. Click Refresh or invite a friend!",
                self.table_rect.centerx,
                self.table_rect.centery,
                color=COLOR_TEXT_MUTED,
                size=18,
                center=True,
            )
        else:
            for i in range(self.visible_rows):
                idx = self.scroll_y + i
                if idx >= len(players):
                    break

                p = players[idx]
                uname = p.get("username", "Unknown")
                p_elo = str(p.get("elo", 1200))
                p_status = p.get("status", "ONLINE").upper()

                is_self = (uname == self.game_state.username)
                row_y = self.table_rect.y + header_offset + i * self.row_height

                # Alternate row background
                if i % 2 == 1:
                    row_bg_rect = pygame.Rect(self.table_rect.x + 2, row_y, self.table_rect.width - 4, self.row_height)
                    pygame.draw.rect(self.surface, (22, 30, 48), row_bg_rect)

                # Player name (tag if self)
                p_color = COLOR_PRIMARY_HOVER if is_self else COLOR_TEXT_WHITE
                p_display = f"{uname} (You)" if is_self else uname
                self.draw_text(p_display, self.table_rect.x + 30, row_y + 16, color=p_color, size=17, bold=is_self)

                # ELO
                self.draw_text(p_elo, self.table_rect.x + 360, row_y + 16, color=COLOR_TEXT_WHITE, size=16)

                # Status badge
                is_available = p_status in ("ONLINE", "IN_LOBBY")
                if is_available:
                    status_col = COLOR_SUCCESS
                elif p_status in ("IN_GAME", "PLAYING"):
                    status_col = COLOR_WARNING
                else:
                    status_col = COLOR_TEXT_MUTED

                self.draw_text(p_status, self.table_rect.x + 580, row_y + 16, color=status_col, size=16, bold=True)

                # Action button
                btn_rect = pygame.Rect(self.table_rect.right - 150, row_y + 8, 120, 36)
                if is_self:
                    self.draw_button(btn_rect, "You", disabled=True, font_size=14)
                elif not is_available:
                    self.draw_button(btn_rect, "In Game", disabled=True, font_size=14)
                elif self.pending_challenge_to == uname:
                    self.draw_button(btn_rect, "Waiting...", disabled=True, font_size=14, bg_color=COLOR_WARNING)
                else:
                    b_hover = btn_rect.collidepoint(mouse_pos)
                    self.draw_button(btn_rect, "Challenge", hover=b_hover, bg_color=COLOR_PRIMARY, font_size=14)

            # If the user is the only person online, show a helpful hint
            other_players = [p for p in players if p.get("username") != self.game_state.username]
            if not other_players:
                hint_y = self.table_rect.y + header_offset + len(players) * self.row_height + 30
                self.draw_text(
                    "You are currently the only player in the lobby.",
                    self.table_rect.centerx,
                    hint_y,
                    color=COLOR_TEXT_MUTED,
                    size=16,
                    center=True,
                )
                self.draw_text(
                    "Tip: Open a 2nd client window and login as another account to Challenge!",
                    self.table_rect.centerx,
                    hint_y + 26,
                    color=COLOR_PRIMARY_HOVER,
                    size=15,
                    center=True,
                )

        # Draw modal and toast
        self.draw_modal()
        self.draw_toast()
