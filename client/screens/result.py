"""
ResultScreen showing game outcome, ELO adjustments, and post-match options.
"""

from typing import Any, Dict
import pygame

from client.config import (
    COLOR_DANGER,
    COLOR_PANEL,
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


class ResultScreen(BaseScreen):
    """Displays match resolution: Victory, Defeat, or Draw with ELO rating changes."""

    def __init__(self, surface: pygame.Surface, game_state, network):
        super().__init__(surface, game_state, network)

        card_w, card_h = 560, 480
        self.card_rect = pygame.Rect(WINDOW_WIDTH // 2 - card_w // 2, WINDOW_HEIGHT // 2 - card_h // 2, card_w, card_h)

        # Buttons
        btn_w = 460
        btn_x = self.card_rect.centerx - btn_w // 2
        self.btn_again_rect = pygame.Rect(btn_x, self.card_rect.y + 270, btn_w, 48)
        self.btn_history_rect = pygame.Rect(btn_x, self.card_rect.y + 330, btn_w, 44)
        self.btn_lobby_rect = pygame.Rect(btn_x, self.card_rect.y + 386, btn_w, 44)

    def on_enter(self) -> None:
        super().on_enter()
        # If new ELO is reported in game_result, update game_state.elo
        if self.game_state.game_result:
            new_elo = self.game_state.game_result.get("new_elo")
            if new_elo:
                self.game_state.elo = int(new_elo)

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.active_modal:
            super().handle_event(event)
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if self.btn_again_rect.collidepoint((mx, my)) or self.btn_lobby_rect.collidepoint((mx, my)):
                self.game_state.reset_match()
                self.next_screen = "lobby"
            elif self.btn_history_rect.collidepoint((mx, my)):
                self.next_screen = "history"

    def handle_message(self, msg: Dict[str, Any]) -> None:
        super().handle_message(msg)

    def draw(self) -> None:
        super().draw()
        mouse_pos = pygame.mouse.get_pos()

        res = self.game_state.game_result or {}
        winner = res.get("winner", "")
        reason = res.get("reason", "Battle concluded")
        elo_diff = res.get("elo_change", 0)
        new_elo = res.get("new_elo", self.game_state.elo)

        is_win = (winner == self.game_state.username)
        is_draw = (winner.upper() == "DRAW" or reason.upper() == "DRAW" or "DRAW" in reason.upper())

        if is_win:
            title_text = "VICTORY"
            title_color = COLOR_SUCCESS
            banner_bg = (16, 75, 48)
        elif is_draw:
            title_text = "DRAW"
            title_color = COLOR_WARNING
            banner_bg = (70, 55, 20)
        else:
            title_text = "DEFEAT"
            title_color = COLOR_DANGER
            banner_bg = (75, 25, 25)

        # Card Panel
        self.draw_panel(self.card_rect, bg_color=COLOR_PANEL, border_radius=12)

        # Outcome Banner
        banner_rect = pygame.Rect(self.card_rect.x, self.card_rect.y, self.card_rect.width, 90)
        pygame.draw.rect(self.surface, banner_bg, banner_rect, border_top_left_radius=12, border_top_right_radius=12)
        self.draw_text(title_text, banner_rect.centerx, banner_rect.centery, color=title_color, size=38, bold=True, center=True)

        # Match Details
        opp_name = self.game_state.opponent or "Opponent"
        self.draw_text(f"Opponent: {opp_name}", self.card_rect.centerx, self.card_rect.y + 115, color=COLOR_TEXT_WHITE, size=18, center=True)
        self.draw_text(f"Outcome: {reason}", self.card_rect.centerx, self.card_rect.y + 145, color=COLOR_TEXT_MUTED, size=15, center=True)

        # ELO Change Box
        elo_box = pygame.Rect(self.card_rect.centerx - 160, self.card_rect.y + 175, 320, 60)
        pygame.draw.rect(self.surface, COLOR_PANEL_LIGHT, elo_box, border_radius=8)

        elo_sign = f"+{elo_diff}" if elo_diff > 0 else str(elo_diff)
        elo_color = COLOR_SUCCESS if elo_diff > 0 else (COLOR_DANGER if elo_diff < 0 else COLOR_TEXT_MUTED)
        elo_summary = f"Rating: {elo_sign}  →  {new_elo} ELO"
        self.draw_text(elo_summary, elo_box.centerx, elo_box.centery, color=elo_color, size=20, bold=True, center=True)

        # Buttons
        again_hover = self.btn_again_rect.collidepoint(mouse_pos)
        self.draw_button(self.btn_again_rect, "Play Again (Lobby)", hover=again_hover, bg_color=COLOR_PRIMARY, font_size=18)

        his_hover = self.btn_history_rect.collidepoint(mouse_pos)
        self.draw_button(self.btn_history_rect, "View Match History", hover=his_hover, bg_color=COLOR_PANEL_LIGHT, font_size=16)

        lob_hover = self.btn_lobby_rect.collidepoint(mouse_pos)
        self.draw_button(self.btn_lobby_rect, "Main Menu", hover=lob_hover, bg_color=COLOR_PANEL_LIGHT, font_size=16)

        # Toast
        self.draw_toast()
