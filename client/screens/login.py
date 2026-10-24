"""
LoginScreen for user authentication.
"""

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
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from client.screens.base_screen import BaseScreen, TextInput


class LoginScreen(BaseScreen):
    """Handles player login and navigation to registration."""

    def __init__(self, surface: pygame.Surface, game_state, network):
        super().__init__(surface, game_state, network)

        card_w, card_h = 440, 480
        self.card_rect = pygame.Rect(WINDOW_WIDTH // 2 - card_w // 2, WINDOW_HEIGHT // 2 - card_h // 2 - 20, card_w, card_h)

        # Input fields
        self.username_input = TextInput(
            pygame.Rect(self.card_rect.x + 40, self.card_rect.y + 140, 360, 48),
            placeholder="Username",
            font_size=18,
        )
        self.password_input = TextInput(
            pygame.Rect(self.card_rect.x + 40, self.card_rect.y + 220, 360, 48),
            placeholder="Password",
            is_password=True,
            font_size=18,
        )

        # Buttons
        self.btn_login_rect = pygame.Rect(self.card_rect.x + 40, self.card_rect.y + 295, 360, 48)
        self.btn_register_rect = pygame.Rect(self.card_rect.x + 40, self.card_rect.y + 360, 360, 44)
        self.btn_reconnect_rect = pygame.Rect(WINDOW_WIDTH - 150, 20, 130, 34)

        self.is_logging_in = False
        self.error_message = ""

    def on_enter(self) -> None:
        super().on_enter()
        self.username_input.text = ""
        self.password_input.text = ""
        self.is_logging_in = False
        self.error_message = ""

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.active_modal:
            super().handle_event(event)
            return

        # Tab key to switch focus
        if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
            if self.username_input.focused:
                self.username_input.focused = False
                self.password_input.focused = True
            else:
                self.username_input.focused = True
                self.password_input.focused = False
            return

        # Enter key to submit
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self._attempt_login()
            return

        self.username_input.handle_event(event)
        self.password_input.handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if self.btn_login_rect.collidepoint((mx, my)) and not self.is_logging_in:
                self._attempt_login()
            elif self.btn_register_rect.collidepoint((mx, my)) and not self.is_logging_in:
                self.next_screen = "register"
            elif self.btn_reconnect_rect.collidepoint((mx, my)):
                self._attempt_reconnect()

    def _attempt_reconnect(self) -> None:
        if not self.network.connected:
            if self.network.connect():
                self.game_state.set_notification("Connected to server!", duration=2.5, color=COLOR_SUCCESS)
            else:
                self.game_state.set_notification("Failed to connect to server.", duration=3.0, color=COLOR_DANGER)

    def _attempt_login(self) -> None:
        u = self.username_input.text.strip()
        p = self.password_input.text.strip()

        if not u or not p:
            self.error_message = "Please enter both username and password."
            return

        # Connect if not already connected
        if not self.network.connected:
            if not self.network.connect():
                self.error_message = f"Cannot reach server at {self.network.host}:{self.network.port}"
                return

        self.is_logging_in = True
        self.error_message = ""
        success = self.network.send({"type": "LOGIN", "username": u, "password": p})
        if not success:
            self.is_logging_in = False
            self.error_message = "Failed to send login request."

    def handle_message(self, msg: dict) -> None:
        super().handle_message(msg)
        msg_type = msg.get("type")

        if msg_type == "LOGIN_OK":
            self.is_logging_in = False
            self.game_state.session_token = msg.get("session_token", "")
            self.game_state.username = msg.get("username", self.username_input.text.strip())
            self.game_state.elo = int(msg.get("elo", 1200))
            self.game_state.set_notification(f"Welcome back, {self.game_state.username}!", duration=2.0, color=COLOR_SUCCESS)
            self.next_screen = "lobby"

        elif msg_type == "ERROR":
            self.is_logging_in = False
            self.error_message = msg.get("message", "Login failed.")

        elif msg_type == "DISCONNECTED":
            self.is_logging_in = False
            self.error_message = "Disconnected from server."

    def update(self, dt: float = 0.016) -> None:
        super().update(dt)
        self.username_input.update(dt)
        self.password_input.update(dt)

    def draw(self) -> None:
        super().draw()
        mouse_pos = pygame.mouse.get_pos()

        # Server status top-right
        status_text = f"Server: {self.network.host}:{self.network.port}"
        status_color = COLOR_SUCCESS if self.network.connected else COLOR_DANGER
        self.draw_text(status_text, WINDOW_WIDTH - 160, 28, color=status_color, size=14, right=True)

        if not self.network.connected:
            rec_hover = self.btn_reconnect_rect.collidepoint(mouse_pos)
            self.draw_button(self.btn_reconnect_rect, "Reconnect", hover=rec_hover, font_size=14, bg_color=COLOR_PANEL_LIGHT)

        # Login Card Panel
        self.draw_panel(self.card_rect, bg_color=COLOR_PANEL, border_radius=12)

        # Title
        self.draw_text("BATTLESHIP", self.card_rect.centerx, self.card_rect.y + 40, color=COLOR_PRIMARY_HOVER, size=32, bold=True, center=True)
        self.draw_text("Sign in to your account", self.card_rect.centerx, self.card_rect.y + 80, color=COLOR_TEXT_MUTED, size=16, center=True)

        # Labels
        self.draw_text("USERNAME", self.username_input.rect.x, self.username_input.rect.y - 20, color=COLOR_TEXT_MUTED, size=13, bold=True)
        self.draw_text("PASSWORD", self.password_input.rect.x, self.password_input.rect.y - 20, color=COLOR_TEXT_MUTED, size=13, bold=True)

        # Inputs
        self.username_input.draw(self.surface)
        self.password_input.draw(self.surface)

        # Error display
        if self.error_message:
            self.draw_text(self.error_message, self.card_rect.centerx, self.card_rect.y + 275, color=COLOR_DANGER, size=14, bold=True, center=True)

        # Login Button
        login_hover = self.btn_login_rect.collidepoint(mouse_pos)
        login_label = "Logging in..." if self.is_logging_in else "Login"
        self.draw_button(
            self.btn_login_rect,
            login_label,
            hover=login_hover,
            disabled=self.is_logging_in,
            bg_color=COLOR_PRIMARY,
            font_size=18,
        )

        # Register switch button
        reg_hover = self.btn_register_rect.collidepoint(mouse_pos)
        self.draw_button(
            self.btn_register_rect,
            "Create New Account",
            hover=reg_hover,
            disabled=self.is_logging_in,
            bg_color=COLOR_PANEL_LIGHT,
            font_size=16,
        )

        # Modal & Toast
        self.draw_modal()
        self.draw_toast()
