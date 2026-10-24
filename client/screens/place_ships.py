"""
PlaceShipsScreen for positioning fleet on 10x10 grid before battle.
"""

import random
from typing import Any, Dict, List, Optional, Tuple
import pygame

from client.config import (
    CELL_SIZE,
    COLOR_DANGER,
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
    GRID_SIZE,
    SHIPS,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from client.screens.base_screen import BaseScreen


class PlaceShipsScreen(BaseScreen):
    """Grid placement screen for 5 battleships with rotation, validation,

    randomization, and ready confirmation.
    """

    def __init__(self, surface: pygame.Surface, game_state, network):
        super().__init__(surface, game_state, network)

        # Board placement coordinates (Left side)
        self.grid_x = 100
        self.grid_y = 160

        # Right Panel for Ship Selector and controls
        self.panel_rect = pygame.Rect(580, 100, 600, 540)

        # Placement Controls
        self.selected_ship_idx: Optional[int] = 0
        self.orientation: str = "H"  # "H" or "V"

        # Action Buttons
        self.btn_rotate_rect = pygame.Rect(self.panel_rect.x + 30, self.panel_rect.y + 350, 160, 44)
        self.btn_random_rect = pygame.Rect(self.panel_rect.x + 210, self.panel_rect.y + 350, 160, 44)
        self.btn_clear_rect = pygame.Rect(self.panel_rect.x + 390, self.panel_rect.y + 350, 160, 44)
        self.btn_ready_rect = pygame.Rect(self.panel_rect.x + 30, self.panel_rect.y + 420, 520, 52)

        # State tracking
        self.ready_sent: bool = False
        self.ready_confirmed: bool = False
        self.opponent_ready: bool = False

        # Ships definition
        self.ships_catalog = [dict(s) for s in SHIPS]
        # Track placement status for each catalog entry
        self.ship_placement: List[Optional[Dict[str, Any]]] = [None for _ in self.ships_catalog]

    def on_enter(self) -> None:
        super().on_enter()
        self.ready_sent = False
        self.ready_confirmed = False
        self.opponent_ready = False
        self.game_state.reset_boards_only()
        self.ship_placement = [None for _ in self.ships_catalog]
        self.selected_ship_idx = 0
        self.orientation = "H"

    def _get_occupied_cells(self, exclude_idx: Optional[int] = None) -> set:
        occupied = set()
        for i, ship in enumerate(self.ship_placement):
            if ship and i != exclude_idx:
                for cell in ship["cells"]:
                    occupied.add(cell)
        return occupied

    def _calc_cells(self, row: int, col: int, size: int, orientation: str) -> List[Tuple[int, int]]:
        cells = []
        for i in range(size):
            r = row if orientation == "H" else row + i
            c = col + i if orientation == "H" else col
            cells.append((r, c))
        return cells

    def _is_placement_valid(self, row: int, col: int, size: int, orientation: str, exclude_idx: Optional[int] = None) -> bool:
        cells = self._calc_cells(row, col, size, orientation)
        occupied = self._get_occupied_cells(exclude_idx)

        for r, c in cells:
            if r < 0 or r >= GRID_SIZE or c < 0 or c >= GRID_SIZE:
                return False
            if (r, c) in occupied:
                return False
        return True

    def _apply_placement_to_game_state(self) -> None:
        # Rebuild game_state.my_board and game_state.placed_ships
        self.game_state.reset_boards_only()
        placed_list = []
        for item in self.ship_placement:
            if item:
                placed_list.append(item)
                for r, c in item["cells"]:
                    self.game_state.my_board[r][c] = 1
        self.game_state.placed_ships = placed_list

    def _place_ship(self, catalog_idx: int, row: int, col: int, orientation: str) -> bool:
        if self.ready_sent:
            return False

        ship_info = self.ships_catalog[catalog_idx]
        size = ship_info["size"]

        if not self._is_placement_valid(row, col, size, orientation, exclude_idx=catalog_idx):
            return False

        cells = self._calc_cells(row, col, size, orientation)
        self.ship_placement[catalog_idx] = {
            "name": ship_info["name"],
            "size": size,
            "row": row,
            "col": col,
            "orientation": orientation,
            "cells": cells,
        }

        self._apply_placement_to_game_state()

        # Send placement to server
        self.network.send({
            "type": "PLACE_SHIP",
            "session_token": self.game_state.session_token,
            "match_id": self.game_state.match_id,
            "ship_id": catalog_idx,
            "ship_size": size,
            "row": row,
            "col": col,
            "direction": orientation,
            "orientation": orientation,
        })

        # Select next unplaced ship
        self._select_next_unplaced()
        return True

    def _select_next_unplaced(self) -> None:
        for i, p in enumerate(self.ship_placement):
            if p is None:
                self.selected_ship_idx = i
                return
        self.selected_ship_idx = None

    def _randomize_all(self) -> None:
        if self.ready_sent:
            return

        self.ship_placement = [None for _ in self.ships_catalog]
        for idx, ship_info in enumerate(self.ships_catalog):
            size = ship_info["size"]
            placed = False
            attempts = 0
            while not placed and attempts < 200:
                attempts += 1
                orient = random.choice(["H", "V"])
                if orient == "H":
                    r = random.randint(0, GRID_SIZE - 1)
                    c = random.randint(0, GRID_SIZE - size)
                else:
                    r = random.randint(0, GRID_SIZE - size)
                    c = random.randint(0, GRID_SIZE - 1)

                if self._is_placement_valid(r, c, size, orient, exclude_idx=idx):
                    cells = self._calc_cells(r, c, size, orient)
                    self.ship_placement[idx] = {
                        "name": ship_info["name"],
                        "size": size,
                        "row": r,
                        "col": c,
                        "orientation": orient,
                        "cells": cells,
                    }
                    placed = True

            # Inform server of each ship placement
            if placed:
                p = self.ship_placement[idx]
                self.network.send({
                    "type": "PLACE_SHIP",
                    "session_token": self.game_state.session_token,
                    "match_id": self.game_state.match_id,
                    "ship_id": idx,
                    "ship_size": size,
                    "row": p["row"],
                    "col": p["col"],
                    "direction": p["orientation"],
                    "orientation": p["orientation"],
                })

        self._apply_placement_to_game_state()
        self._select_next_unplaced()

    def _clear_all(self) -> None:
        if self.ready_sent:
            return
        self.ship_placement = [None for _ in self.ships_catalog]
        self._apply_placement_to_game_state()
        self.selected_ship_idx = 0

    def _send_ready(self) -> None:
        if not all(self.ship_placement) or self.ready_sent:
            return

        self.ready_sent = True
        self.network.send({
            "type": "READY",
            "session_token": self.game_state.session_token,
            "match_id": self.game_state.match_id,
        })
        self.game_state.set_notification("Ready sent! Waiting for match start...", duration=3.0, color=COLOR_PRIMARY)

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.active_modal:
            super().handle_event(event)
            return

        # R key toggles rotation
        if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
            self.orientation = "V" if self.orientation == "H" else "H"
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos

            # Board click
            cell = self.get_grid_cell_from_pos((mx, my), self.grid_x, self.grid_y)
            if cell and self.selected_ship_idx is not None and not self.ready_sent:
                r, c = cell
                self._place_ship(self.selected_ship_idx, r, c, self.orientation)
                return

            # Ship selection buttons
            ship_list_y = self.panel_rect.y + 80
            for i in range(len(self.ships_catalog)):
                rect = pygame.Rect(self.panel_rect.x + 30, ship_list_y + i * 50, 520, 42)
                if rect.collidepoint((mx, my)) and not self.ready_sent:
                    self.selected_ship_idx = i
                    return

            # Controls
            if self.btn_rotate_rect.collidepoint((mx, my)) and not self.ready_sent:
                self.orientation = "V" if self.orientation == "H" else "H"
                return

            if self.btn_random_rect.collidepoint((mx, my)) and not self.ready_sent:
                self._randomize_all()
                return

            if self.btn_clear_rect.collidepoint((mx, my)) and not self.ready_sent:
                self._clear_all()
                return

            if self.btn_ready_rect.collidepoint((mx, my)) and all(self.ship_placement) and not self.ready_sent:
                self._send_ready()
                return

    def handle_message(self, msg: Dict[str, Any]) -> None:
        super().handle_message(msg)
        msg_type = msg.get("type")

        if msg_type == "READY_OK":
            self.ready_confirmed = True
            if self.opponent_ready:
                self._check_transition_to_game()

        elif msg_type == "OPPONENT_READY":
            self.opponent_ready = True
            self.game_state.set_notification(f"{self.game_state.opponent} is ready!", duration=2.5, color=COLOR_SUCCESS)
            if self.ready_confirmed:
                self._check_transition_to_game()

        elif msg_type == "YOUR_TURN":
            self.game_state.my_turn = True
            self.next_screen = "game"

        elif msg_type in ("GAME_START", "OPPONENT_FIRED"):
            # Match started
            self.next_screen = "game"

    def _check_transition_to_game(self) -> None:
        # Both players confirmed ready
        if not self.game_state.you_go_first:
            self.game_state.my_turn = False
        self.next_screen = "game"

    def draw(self) -> None:
        super().draw()
        mouse_pos = pygame.mouse.get_pos()

        # Header
        self.draw_text("FLEET DEPLOYMENT", 60, 30, color=COLOR_PRIMARY_HOVER, size=26, bold=True)
        sub_info = f"Match vs {self.game_state.opponent} ({self.game_state.opponent_elo} ELO)"
        self.draw_text(sub_info, 60, 64, color=COLOR_TEXT_MUTED, size=16)

        # Placement Preview
        preview_cells = None
        preview_valid = False
        hover_cell = self.get_grid_cell_from_pos(mouse_pos, self.grid_x, self.grid_y)

        if hover_cell and self.selected_ship_idx is not None and not self.ready_sent:
            hr, hc = hover_cell
            size = self.ships_catalog[self.selected_ship_idx]["size"]
            preview_valid = self._is_placement_valid(hr, hc, size, self.orientation, exclude_idx=self.selected_ship_idx)
            preview_cells = self._calc_cells(hr, hc, size, self.orientation)

        # 10x10 Grid
        self.draw_grid(
            top_left_x=self.grid_x,
            top_left_y=self.grid_y,
            board_data=self.game_state.my_board,
            is_enemy=False,
            preview_cells=preview_cells,
            preview_valid=preview_valid,
            hover_cell=hover_cell,
            title="YOUR BATTLEGRID",
        )

        # Ships Panel
        self.draw_panel(self.panel_rect, bg_color=COLOR_PANEL, border_radius=10)
        self.draw_text("DEPLOYABLE SHIPS", self.panel_rect.x + 30, self.panel_rect.y + 24, color=COLOR_PRIMARY_HOVER, size=20, bold=True)
        self.draw_text("Click a ship or press R to rotate", self.panel_rect.x + 30, self.panel_rect.y + 50, color=COLOR_TEXT_MUTED, size=14)

        # Ship Catalog List
        ship_list_y = self.panel_rect.y + 80
        for i, ship in enumerate(self.ships_catalog):
            item_rect = pygame.Rect(self.panel_rect.x + 30, ship_list_y + i * 50, 520, 42)
            is_selected = (self.selected_ship_idx == i)
            is_placed = (self.ship_placement[i] is not None)

            # Styling
            if is_selected:
                bg_col = (35, 55, 88)
                brd_col = COLOR_PRIMARY
            elif is_placed:
                bg_col = (20, 32, 50)
                brd_col = COLOR_PANEL_BORDER
            else:
                bg_col = COLOR_PANEL_LIGHT
                brd_col = COLOR_PANEL_BORDER

            pygame.draw.rect(self.surface, bg_col, item_rect, border_radius=6)
            pygame.draw.rect(self.surface, brd_col, item_rect, width=2 if is_selected else 1, border_radius=6)

            # Ship Name & Size
            name_text = f"{ship['name']} ({ship['size']} cells)"
            self.draw_text(name_text, item_rect.x + 16, item_rect.centery - 9, color=COLOR_TEXT_WHITE if not is_placed else COLOR_TEXT_MUTED, size=16, bold=is_selected)

            # Visual representation blocks
            block_start_x = item_rect.x + 280
            for b in range(ship["size"]):
                b_rect = pygame.Rect(block_start_x + b * 20, item_rect.centery - 7, 16, 14)
                block_col = COLOR_SUCCESS if is_placed else COLOR_SHIP
                pygame.draw.rect(self.surface, block_col, b_rect, border_radius=2)

            # Status label
            status_str = "PLACED" if is_placed else "UNPLACED"
            status_col = COLOR_SUCCESS if is_placed else COLOR_WARNING
            self.draw_text(status_str, item_rect.right - 20, item_rect.centery - 9, color=status_col, size=14, bold=True, right=True)

        # Control Buttons
        rot_hover = self.btn_rotate_rect.collidepoint(mouse_pos)
        rot_label = f"Rotate: {self.orientation} (R)"
        self.draw_button(self.btn_rotate_rect, rot_label, hover=rot_hover, disabled=self.ready_sent, bg_color=COLOR_PANEL_LIGHT, font_size=15)

        rand_hover = self.btn_random_rect.collidepoint(mouse_pos)
        self.draw_button(self.btn_random_rect, "Randomize", hover=rand_hover, disabled=self.ready_sent, bg_color=COLOR_PANEL_LIGHT, font_size=15)

        clr_hover = self.btn_clear_rect.collidepoint(mouse_pos)
        self.draw_button(self.btn_clear_rect, "Clear", hover=clr_hover, disabled=self.ready_sent, bg_color=COLOR_PANEL_LIGHT, font_size=15)

        # Ready Button
        all_placed = all(self.ship_placement)
        ready_hover = self.btn_ready_rect.collidepoint(mouse_pos)
        if self.ready_sent:
            ready_txt = "Waiting for Opponent..." if not self.opponent_ready else "Opponent Ready! Starting..."
            ready_bg = COLOR_PANEL_LIGHT
            self.draw_button(self.btn_ready_rect, ready_txt, disabled=True, bg_color=ready_bg, font_size=18)
        else:
            ready_bg = COLOR_SUCCESS if all_placed else (40, 50, 70)
            self.draw_button(
                self.btn_ready_rect,
                "READY FOR BATTLE" if all_placed else "Place all 5 ships to Ready",
                hover=ready_hover,
                disabled=not all_placed,
                bg_color=ready_bg,
                font_size=18,
            )

        # Draw modal and toast
        self.draw_modal()
        self.draw_toast()
