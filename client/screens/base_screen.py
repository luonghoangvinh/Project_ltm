"""
BaseScreen class and reusable UI widgets for Battleship client.
"""

import math
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import pygame

from client.config import (
    CELL_SIZE,
    COLOR_BG,
    COLOR_DANGER,
    COLOR_DANGER_HOVER,
    COLOR_GRID_LINE,
    COLOR_HIT,
    COLOR_MISS,
    COLOR_PANEL,
    COLOR_PANEL_BORDER,
    COLOR_PANEL_LIGHT,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_SHIP,
    COLOR_SHIP_BORDER,
    COLOR_SUCCESS,
    COLOR_SUCCESS_HOVER,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_WHITE,
    COLOR_WARNING,
    COLOR_WATER,
    COLOR_WATER_HOVER,
    GRID_SIZE,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from client.game_state import GameState
from client.network import NetworkClient


# Global Font Cache
_FONT_CACHE: Dict[Tuple[int, bool], pygame.font.Font] = {}


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Returns a cached Pygame Font instance."""
    key = (size, bold)
    if key not in _FONT_CACHE:
        try:
            # Prefer clean modern sans-serif fonts
            font_name = pygame.font.match_font("segoeui") or pygame.font.match_font("helvetica") or pygame.font.match_font("arial")
            if font_name:
                _FONT_CACHE[key] = pygame.font.Font(font_name, size)
                _FONT_CACHE[key].set_bold(bold)
            else:
                _FONT_CACHE[key] = pygame.font.SysFont("sans-serif", size, bold=bold)
        except Exception:
            _FONT_CACHE[key] = pygame.font.SysFont(None, size, bold=bold)
    return _FONT_CACHE[key]


class TextInput:
    """Single-line text input field supporting focus, cursor blinking,

    and optional password masking.
    """

    def __init__(
        self,
        rect: pygame.Rect,
        placeholder: str = "",
        is_password: bool = False,
        max_length: int = 32,
        font_size: int = 20,
    ):
        self.rect = pygame.Rect(rect)
        self.placeholder = placeholder
        self.is_password = is_password
        self.max_length = max_length
        self.font_size = font_size
        self.text = ""
        self.focused = False
        self.cursor_visible = True
        self.cursor_timer = 0.0

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handles mouse clicks and keyboard typing. Returns True if consumed."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.focused = self.rect.collidepoint(event.pos)
            self.cursor_visible = True
            self.cursor_timer = 0.0
            return self.focused

        if self.focused and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                return True
            elif event.key in (pygame.K_TAB, pygame.K_ESCAPE):
                return False
            elif event.unicode and len(self.text) < self.max_length and event.unicode.isprintable():
                self.text += event.unicode
                return True
        return False

    def update(self, dt: float = 0.016) -> None:
        if self.focused:
            self.cursor_timer += dt
            if self.cursor_timer >= 0.5:
                self.cursor_visible = not self.cursor_visible
                self.cursor_timer = 0.0
        else:
            self.cursor_visible = False

    def draw(self, surface: pygame.Surface) -> None:
        font = get_font(self.font_size)

        # Background
        bg_col = (20, 29, 50) if self.focused else (16, 23, 40)
        border_col = COLOR_PRIMARY if self.focused else COLOR_PANEL_BORDER
        pygame.draw.rect(surface, bg_col, self.rect, border_radius=6)
        pygame.draw.rect(surface, border_col, self.rect, width=2, border_radius=6)

        # Text rendering
        display_str = ("•" * len(self.text)) if self.is_password else self.text
        if not self.text and not self.focused:
            # Placeholder
            ph_surf = font.render(self.placeholder, True, COLOR_TEXT_MUTED)
            surface.blit(ph_surf, (self.rect.x + 12, self.rect.y + (self.rect.height - ph_surf.get_height()) // 2))
        else:
            txt_surf = font.render(display_str, True, COLOR_TEXT_WHITE)
            surface.blit(txt_surf, (self.rect.x + 12, self.rect.y + (self.rect.height - txt_surf.get_height()) // 2))

            # Cursor
            if self.focused and self.cursor_visible:
                cx = self.rect.x + 14 + txt_surf.get_width()
                cy1 = self.rect.y + 8
                cy2 = self.rect.bottom - 8
                pygame.draw.line(surface, COLOR_PRIMARY_HOVER, (cx, cy1), (cx, cy2), 2)


class BaseScreen:
    """Base class for all Battleship client screens."""

    # Colors exposed as attributes for compatibility
    BLACK = (10, 15, 29)
    WHITE = COLOR_TEXT_WHITE
    GRAY = COLOR_TEXT_MUTED
    BLUE = COLOR_PRIMARY
    RED = COLOR_DANGER
    GREEN = COLOR_SUCCESS
    YELLOW = COLOR_WARNING
    DARK_BLUE = COLOR_PANEL
    LIGHT_BLUE = COLOR_PRIMARY_HOVER
    ORANGE = (249, 115, 22)

    def __init__(self, surface: pygame.Surface, game_state: GameState, network: NetworkClient):
        self.surface: pygame.Surface = surface
        self.game_state: GameState = game_state
        self.network: NetworkClient = network
        self.next_screen: Optional[str] = None
        self.active_modal: Optional[Dict[str, Any]] = None

    def on_enter(self) -> None:
        """Called whenever the screen becomes active."""
        self.next_screen = None
        self.active_modal = None

    def handle_event(self, event: pygame.event.Event) -> None:
        """Processes Pygame events. Override in subclasses."""
        if self.active_modal:
            self._handle_modal_event(event)

    def handle_message(self, msg: Dict[str, Any]) -> None:
        """Processes server messages. Override in subclasses."""
        msg_type = msg.get("type")
        if msg_type == "ERROR":
            err_msg = msg.get("message", "An unexpected error occurred.")
            self.game_state.set_notification(f"Error: {err_msg}", duration=4.0, color=COLOR_DANGER)
        elif msg_type == "DISCONNECTED":
            self.game_state.set_notification("Lost connection to server!", duration=5.0, color=COLOR_DANGER)

    def update(self, dt: float = 0.016) -> None:
        """Update animations and timers."""
        if self.game_state.notification_timer > 0:
            self.game_state.notification_timer -= dt
            if self.game_state.notification_timer <= 0:
                self.game_state.notification = ""

    def draw(self) -> None:
        """Renders the screen surface. Override in subclasses."""
        self.surface.fill(COLOR_BG)

    # ---------------- UI Helper Methods ----------------

    def draw_text(
        self,
        text: str,
        x: int,
        y: int,
        color: Tuple[int, int, int] = COLOR_TEXT_WHITE,
        size: int = 18,
        bold: bool = False,
        center: bool = False,
        right: bool = False,
    ) -> pygame.Rect:
        """Renders text with alignment options and returns its Rect."""
        font = get_font(size, bold)
        surf = font.render(str(text), True, color)
        rect = surf.get_rect()
        if center:
            rect.center = (x, y)
        elif right:
            rect.topright = (x, y)
        else:
            rect.topleft = (x, y)
        self.surface.blit(surf, rect)
        return rect

    def draw_button(
        self,
        rect: pygame.Rect,
        text: str,
        hover: bool = False,
        disabled: bool = False,
        bg_color: Optional[Tuple[int, int, int]] = None,
        text_color: Optional[Tuple[int, int, int]] = None,
        border_color: Optional[Tuple[int, int, int]] = None,
        font_size: int = 18,
        border_radius: int = 6,
    ) -> bool:
        """Draws a modern rounded button. Returns True if hover is active and not disabled."""
        rect = pygame.Rect(rect)
        if disabled:
            fill_col = (30, 40, 58)
            txt_col = (100, 115, 135)
            brd_col = (45, 60, 85)
        elif hover:
            fill_col = bg_color or COLOR_PRIMARY_HOVER
            txt_col = text_color or COLOR_TEXT_WHITE
            brd_col = border_color or COLOR_PRIMARY_HOVER
        else:
            fill_col = bg_color or COLOR_PRIMARY
            txt_col = text_color or COLOR_TEXT_WHITE
            brd_col = border_color or COLOR_PANEL_BORDER

        pygame.draw.rect(self.surface, fill_col, rect, border_radius=border_radius)
        if brd_col:
            pygame.draw.rect(self.surface, brd_col, rect, width=2, border_radius=border_radius)

        self.draw_text(text, rect.centerx, rect.centery, color=txt_col, size=font_size, bold=True, center=True)
        return hover and not disabled

    def draw_panel(
        self,
        rect: pygame.Rect,
        bg_color: Tuple[int, int, int] = COLOR_PANEL,
        border_color: Tuple[int, int, int] = COLOR_PANEL_BORDER,
        border_radius: int = 8,
        border_width: int = 2,
    ) -> None:
        """Draws a styled container panel."""
        pygame.draw.rect(self.surface, bg_color, rect, border_radius=border_radius)
        if border_width > 0:
            pygame.draw.rect(self.surface, border_color, rect, width=border_width, border_radius=border_radius)

    def draw_grid(
        self,
        top_left_x: int,
        top_left_y: int,
        cell_size: int = CELL_SIZE,
        grid_size: int = GRID_SIZE,
        board_data: Optional[List[List[int]]] = None,
        is_enemy: bool = False,
        preview_cells: Optional[List[Tuple[int, int]]] = None,
        preview_valid: bool = True,
        hover_cell: Optional[Tuple[int, int]] = None,
        title: Optional[str] = None,
    ) -> None:
        """Renders a standard 10x10 Battleship board with coordinates, ships, hits, and misses."""
        # Optional title above grid
        if title:
            self.draw_text(title, top_left_x + (grid_size * cell_size) // 2, top_left_y - 28, color=COLOR_PRIMARY_HOVER, size=20, bold=True, center=True)

        col_labels = [chr(65 + i) for i in range(grid_size)]  # A - J
        row_labels = [str(i + 1) for i in range(grid_size)]   # 1 - 10

        # Draw column headers
        for col in range(grid_size):
            cx = top_left_x + col * cell_size + cell_size // 2
            cy = top_left_y - 12
            self.draw_text(col_labels[col], cx, cy, color=COLOR_TEXT_MUTED, size=15, bold=True, center=True)

        # Draw row headers
        for row in range(grid_size):
            rx = top_left_x - 14
            ry = top_left_y + row * cell_size + cell_size // 2
            self.draw_text(row_labels[row], rx, ry, color=COLOR_TEXT_MUTED, size=15, bold=True, center=True)

        # Background water rect
        board_rect = pygame.Rect(top_left_x, top_left_y, grid_size * cell_size, grid_size * cell_size)
        pygame.draw.rect(self.surface, COLOR_WATER, board_rect, border_radius=4)

        preview_set = set(preview_cells) if preview_cells else set()

        # Cells
        for r in range(grid_size):
            for c in range(grid_size):
                cell_rect = pygame.Rect(top_left_x + c * cell_size, top_left_y + r * cell_size, cell_size, cell_size)
                state = board_data[r][c] if board_data else 0

                # Cell hover highlight
                if hover_cell == (r, c):
                    pygame.draw.rect(self.surface, COLOR_WATER_HOVER, cell_rect)

                # Placement Preview
                if (r, c) in preview_set:
                    prev_col = (16, 185, 129, 140) if preview_valid else (239, 68, 68, 140)
                    overlay = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
                    overlay.fill(prev_col)
                    self.surface.blit(overlay, cell_rect.topleft)

                # Board cell contents
                # For my_board: 0=empty, 1=ship, 2=hit, 3=miss
                # For enemy_board: 0=unknown, 1=hit, 2=miss
                if not is_enemy:
                    if state == 1:  # Ship
                        inner = cell_rect.inflate(-4, -4)
                        pygame.draw.rect(self.surface, COLOR_SHIP, inner, border_radius=4)
                        pygame.draw.rect(self.surface, COLOR_SHIP_BORDER, inner, width=2, border_radius=4)
                    elif state == 2:  # Hit on my ship
                        inner = cell_rect.inflate(-4, -4)
                        pygame.draw.rect(self.surface, (120, 20, 20), inner, border_radius=4)
                        # Draw X
                        pygame.draw.line(self.surface, COLOR_HIT, inner.topleft, inner.bottomright, 3)
                        pygame.draw.line(self.surface, COLOR_HIT, inner.bottomleft, inner.topright, 3)
                    elif state == 3:  # Miss
                        pygame.draw.circle(self.surface, COLOR_MISS, cell_rect.center, 5)
                else:
                    if state == 1:  # Hit on enemy ship
                        inner = cell_rect.inflate(-4, -4)
                        pygame.draw.rect(self.surface, (120, 20, 20), inner, border_radius=4)
                        pygame.draw.line(self.surface, COLOR_HIT, inner.topleft, inner.bottomright, 3)
                        pygame.draw.line(self.surface, COLOR_HIT, inner.bottomleft, inner.topright, 3)
                    elif state == 2:  # Miss on enemy board
                        pygame.draw.circle(self.surface, COLOR_TEXT_WHITE, cell_rect.center, 5)

                # Grid line
                pygame.draw.rect(self.surface, COLOR_GRID_LINE, cell_rect, width=1)

        # Outer border
        pygame.draw.rect(self.surface, COLOR_PANEL_BORDER, board_rect, width=2, border_radius=4)

    def get_grid_cell_from_pos(
        self,
        mouse_pos: Tuple[int, int],
        top_left_x: int,
        top_left_y: int,
        cell_size: int = CELL_SIZE,
        grid_size: int = GRID_SIZE,
    ) -> Optional[Tuple[int, int]]:
        """Converts mouse screen coordinates into (row, col) grid coordinates, or None."""
        mx, my = mouse_pos
        dx = mx - top_left_x
        dy = my - top_left_y
        if 0 <= dx < grid_size * cell_size and 0 <= dy < grid_size * cell_size:
            return dy // cell_size, dx // cell_size
        return None

    def show_modal(
        self,
        title: str,
        message: str,
        buttons: List[Dict[str, Any]],
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        """Opens a modal popup dialog.

        buttons: list of {'text': str, 'action': callable, 'color': tuple}
        """
        self.active_modal = {
            "title": title,
            "message": message,
            "buttons": buttons,
            "on_close": on_close,
        }

    def close_modal(self) -> None:
        """Closes the current modal."""
        if self.active_modal and self.active_modal.get("on_close"):
            try:
                self.active_modal["on_close"]()
            except Exception:
                pass
        self.active_modal = None

    def _handle_modal_event(self, event: pygame.event.Event) -> bool:
        if not self.active_modal:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            modal_rect = pygame.Rect(WINDOW_WIDTH // 2 - 250, WINDOW_HEIGHT // 2 - 130, 500, 260)
            buttons = self.active_modal.get("buttons", [])
            num_btn = len(buttons)
            btn_w = 120
            btn_h = 42
            spacing = 20
            total_w = num_btn * btn_w + (num_btn - 1) * spacing
            start_x = modal_rect.centerx - total_w // 2
            btn_y = modal_rect.bottom - 60

            for i, btn in enumerate(buttons):
                bx = start_x + i * (btn_w + spacing)
                brect = pygame.Rect(bx, btn_y, btn_w, btn_h)
                if brect.collidepoint((mx, my)):
                    action = btn.get("action")
                    if action:
                        action()
                    self.close_modal()
                    return True
            return True
        return True

    def draw_modal(self) -> None:
        """Renders the active modal dialog with dimming overlay."""
        if not self.active_modal:
            return

        # Dim overlay
        dim_surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        dim_surf.fill((0, 0, 0, 180))
        self.surface.blit(dim_surf, (0, 0))

        # Box
        modal_rect = pygame.Rect(WINDOW_WIDTH // 2 - 250, WINDOW_HEIGHT // 2 - 130, 500, 260)
        self.draw_panel(modal_rect, bg_color=COLOR_PANEL, border_color=COLOR_PRIMARY, border_radius=12, border_width=2)

        # Title
        self.draw_text(self.active_modal["title"], modal_rect.centerx, modal_rect.y + 36, color=COLOR_PRIMARY_HOVER, size=24, bold=True, center=True)

        # Message
        msg_lines = self.active_modal["message"].split("\n")
        line_y = modal_rect.y + 80
        for line in msg_lines:
            self.draw_text(line, modal_rect.centerx, line_y, color=COLOR_TEXT_WHITE, size=18, center=True)
            line_y += 26

        # Buttons
        mouse_pos = pygame.mouse.get_pos()
        buttons = self.active_modal.get("buttons", [])
        num_btn = len(buttons)
        btn_w = 120
        btn_h = 42
        spacing = 20
        total_w = num_btn * btn_w + (num_btn - 1) * spacing
        start_x = modal_rect.centerx - total_w // 2
        btn_y = modal_rect.bottom - 60

        for i, btn in enumerate(buttons):
            bx = start_x + i * (btn_w + spacing)
            brect = pygame.Rect(bx, btn_y, btn_w, btn_h)
            hover = brect.collidepoint(mouse_pos)
            bg_col = btn.get("color", COLOR_PRIMARY)
            self.draw_button(brect, btn["text"], hover=hover, bg_color=bg_col, font_size=16)

    def draw_toast(self) -> None:
        """Draws notification toast if active."""
        if self.game_state.notification and self.game_state.notification_timer > 0:
            toast_text = self.game_state.notification
            font = get_font(18, bold=True)
            text_surf = font.render(toast_text, True, COLOR_TEXT_WHITE)
            tw = text_surf.get_width() + 36
            th = 44
            rect = pygame.Rect(WINDOW_WIDTH // 2 - tw // 2, 20, tw, th)

            bg_col = self.game_state.notification_color or (30, 58, 138)
            pygame.draw.rect(self.surface, bg_col, rect, border_radius=8)
            pygame.draw.rect(self.surface, COLOR_PANEL_BORDER, rect, width=2, border_radius=8)
            self.surface.blit(text_surf, (rect.centerx - text_surf.get_width() // 2, rect.centery - text_surf.get_height() // 2))
