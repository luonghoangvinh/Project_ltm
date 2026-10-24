"""
RegisterScreen for new account creation.
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


class RegisterScreen(BaseScreen):
    """Handles new player registration."""

    def __init__(self, surface: pygame.Surface, game_state, network):
        super().__init__(surface, game_state, network)

        card_w, card_h = 440, 540
        self.card_rect = pygame.Rect(WINDOW_WIDTH // 2 - card_w // 2, WINDOW_HEIGHT // 2 - card_h // 2 - 10, card_w, card_h)

        # Input fields
        self.username_input = TextInput(
            pygame.Rect(self.card_rect.x + 40, self.card_rect.y + 120, 360, 46),
            placeholder="Username (min 3 chars)",
            font_size=17,
        )
        self.password_input = TextInput(
            pygame.Rect(self.card_rect.x + 40, self.card_rect.y + 195, 360, 46),
            placeholder="Password (min 4 chars)",
            is_password=True,
            font_size=17,
        )
        self.confirm_input = TextInput(
            pygame.Rect(self.card_rect.x + 40, self.card_rect.y + 270, 360, 46),
            placeholder="Confirm Password",
            is_password=True,
            font_size=17,
        )

        # Buttons
        self.btn_register_rect = pygame.Rect(self.card_rect.x + 40, self.card_rect.y + 355, 360, 48)
        self.btn_back_rect = pygame.Rect(self.card_rect.x + 40, self.card_rect.y + 418, 360, 44)

        self.is_submitting = False
        self.error_message = ""

    def on_enter(self) -> None:
        super().on_enter()
        self.username_input.text = ""
        self.password_input.text = ""
        self.confirm_input.text = ""
        self.is_submitting = False
        self.error_message = ""

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.active_modal:
            super().handle_event(event)
            return

        # Tab navigation
        if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
            if self.username_input.focused:
                self.username_input.focused = False
                self.password_input.focused = True
            elif self.password_input.focused:
                self.password_input.focused = False
                self.confirm_input.focused = True
            else:
                self.username_input.focused = True
                self.confirm_input.focused = False
            return

        # Enter key submission
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self._attempt_register()
            return

        self.username_input.handle_event(event)
        self.password_input.handle_event(event)
        self.confirm_input.handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if self.btn_register_rect.collidepoint((mx, my)) and not self.is_submitting:
                self._attempt_register()
            elif self.btn_back_rect.collidepoint((mx, my)):
                self.next_screen = "login"

    def _attempt_register(self) -> None:
        u = self.username_input.text.strip()
        p = self.password_input.text.strip()
        cp = self.confirm_input.text.strip()

        if len(u) < 3:
            self.error_message = "Username must be at least 3 characters."
            return
        if len(p) < 4:
            self.error_message = "Password must be at least 4 characters."
            return
        if p != cp:
            self.error_message = "Passwords do not match."
            return

        if not self.network.connected:
            if not self.network.connect():
                self.error_message = f"Cannot reach server at {self.network.host}:{self.network.port}"
                return

        self.is_submitting = True
        self.error_message = ""
        success = self.network.send({"type": "REGISTER", "username": u, "password": p})
        if not success:
            self.is_submitting = False
            self.error_message = "Failed to send registration request."

    def handle_message(self, msg: dict) -> None:
        super().handle_message(msg)
        msg_type = msg.get("type")

        if msg_type == "REGISTER_OK":
            self.is_submitting = False
            self.game_state.set_notification("Account created! Please log in.", duration=3.0, color=COLOR_SUCCESS)
            self.next_screen = "login"

        elif msg_type == "ERROR":
            self.is_submitting = False
            self.error_message = msg.get("message", "Registration failed.")

        elif msg_type == "DISCONNECTED":
            self.is_submitting = False
            self.error_message = "Disconnected from server."

    def update(self, dt: float = 0.016) -> None:
        super().update(dt)
        self.username_input.update(dt)
        self.password_input.update(dt)
        self.confirm_input.update(dt)

    def draw(self) -> None:
        super().draw()
        mouse_pos = pygame.mouse.get_pos()

        # Registration Panel
        self.draw_panel(self.card_rect, bg_color=COLOR_PANEL, border_radius=12)

        # Title
        self.draw_text("CREATE ACCOUNT", self.card_rect.centerx, self.card_rect.y + 35, color=COLOR_PRIMARY_HOVER, size=28, bold=True, center=True)
        self.draw_text("Join the fleet commanders", self.card_rect.centerx, self.card_rect.y + 70, color=COLOR_TEXT_MUTED, size=15, center=True)

        # Labels & Inputs
        self.draw_text("USERNAME", self.username_input.rect.x, self.username_input.rect.y - 18, color=COLOR_TEXT_MUTED, size=12, bold=True)
        self.username_input.draw(self.surface)

        self.draw_text("PASSWORD", self.password_input.rect.x, self.password_input.rect.y - 18, color=COLOR_TEXT_MUTED, size=12, bold=True)
        self.password_input.draw(self.surface)

        self.draw_text("CONFIRM PASSWORD", self.confirm_input.rect.x, self.confirm_input.rect.y - 18, color=COLOR_TEXT_MUTED, size=12, bold=True)
        self.confirm_input.draw(self.surface)

        # Error display
        if self.error_message:
            self.draw_text(self.error_message, self.card_rect.centerx, self.card_rect.y + 332, color=COLOR_DANGER, size=14, bold=True, center=True)

        # Register Button
        reg_hover = self.btn_register_rect.collidepoint(mouse_pos)
        reg_label = "Creating Account..." if self.is_submitting else "Register"
        self.draw_button(
            self.btn_register_rect,
            reg_label,
            hover=reg_hover,
            disabled=self.is_submitting,
            bg_color=COLOR_PRIMARY,
            font_size=18,
        )

        # Back Button
        back_hover = self.btn_back_rect.collidepoint(mouse_pos)
        self.draw_button(
            self.btn_back_rect,
            "Back to Login",
            hover=back_hover,
            disabled=self.is_submitting,
            bg_color=COLOR_PANEL_LIGHT,
            font_size=16,
        )

        self.draw_modal()
        self.draw_toast()
