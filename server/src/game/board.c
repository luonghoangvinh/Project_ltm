#include "game.h"
#include <stdio.h>
#include <string.h>

const int DEFAULT_SHIP_SIZES[NUM_SHIPS] = {2, 3, 3, 4, 5};
const char *SHIP_NAMES[NUM_SHIPS] = {"Destroyer", "Submarine", "Cruiser", "Battleship", "Carrier"};

void init_board(Board *board) {
    if (!board) return;
    memset(board, 0, sizeof(Board));

    for (int r = 0; r < BOARD_SIZE; r++) {
        for (int c = 0; c < BOARD_SIZE; c++) {
            board->grid[r][c] = CELL_EMPTY;
            board->ship_grid[r][c] = -1;
        }
    }

    for (int i = 0; i < NUM_SHIPS; i++) {
        board->ships[i].id = i;
        board->ships[i].size = DEFAULT_SHIP_SIZES[i];
        board->ships[i].row = -1;
        board->ships[i].col = -1;
        board->ships[i].direction = DIR_HORIZONTAL;
        board->ships[i].hits = 0;
        board->ships[i].is_placed = 0;
        board->ships[i].is_sunk = 0;
    }
    board->ships_placed_count = 0;
}

static void clear_placed_ship(Board *board, int ship_id) {
    if (ship_id < 0 || ship_id >= NUM_SHIPS) return;
    if (!board->ships[ship_id].is_placed) return;

    for (int r = 0; r < BOARD_SIZE; r++) {
        for (int c = 0; c < BOARD_SIZE; c++) {
            if (board->ship_grid[r][c] == ship_id) {
                board->grid[r][c] = CELL_EMPTY;
                board->ship_grid[r][c] = -1;
            }
        }
    }
    board->ships[ship_id].is_placed = 0;
    board->ships[ship_id].hits = 0;
    board->ships[ship_id].is_sunk = 0;
    board->ships[ship_id].row = -1;
    board->ships[ship_id].col = -1;
    if (board->ships_placed_count > 0) {
        board->ships_placed_count--;
    }
}

int place_ship(Board *board, int ship_id, int row, int col, int direction, char *err_msg, size_t err_size) {
    if (!board) {
        if (err_msg) snprintf(err_msg, err_size, "Invalid board");
        return -1;
    }

    if (ship_id < 0 || ship_id >= NUM_SHIPS) {
        if (err_msg) snprintf(err_msg, err_size, "Invalid ship_id %d (must be 0..%d)", ship_id, NUM_SHIPS - 1);
        return -1;
    }

    if (direction != DIR_HORIZONTAL && direction != DIR_VERTICAL) {
        if (err_msg) snprintf(err_msg, err_size, "Invalid direction (must be 0 for Horizontal or 1 for Vertical)");
        return -1;
    }

    int size = DEFAULT_SHIP_SIZES[ship_id];

    /* Check bounds */
    if (direction == DIR_HORIZONTAL) {
        if (row < 0 || row >= BOARD_SIZE || col < 0 || (col + size) > BOARD_SIZE) {
            if (err_msg) snprintf(err_msg, err_size, "Ship placement out of bounds (row %d, col %d, size %d, H)", row, col, size);
            return -1;
        }
    } else {
        if (row < 0 || (row + size) > BOARD_SIZE || col < 0 || col >= BOARD_SIZE) {
            if (err_msg) snprintf(err_msg, err_size, "Ship placement out of bounds (row %d, col %d, size %d, V)", row, col, size);
            return -1;
        }
    }

    /* Check overlap against other ships */
    for (int i = 0; i < size; i++) {
        int r = (direction == DIR_HORIZONTAL) ? row : row + i;
        int c = (direction == DIR_HORIZONTAL) ? col + i : col;
        int existing_sid = board->ship_grid[r][c];
        if (existing_sid != -1 && existing_sid != ship_id) {
            if (err_msg) snprintf(err_msg, err_size, "Ship overlaps with another ship at (%d, %d)", r, c);
            return -1;
        }
    }

    /* If ship was already placed, clear previous placement */
    if (board->ships[ship_id].is_placed) {
        clear_placed_ship(board, ship_id);
    }

    /* Place ship */
    for (int i = 0; i < size; i++) {
        int r = (direction == DIR_HORIZONTAL) ? row : row + i;
        int c = (direction == DIR_HORIZONTAL) ? col + i : col;
        board->grid[r][c] = CELL_SHIP;
        board->ship_grid[r][c] = ship_id;
    }

    board->ships[ship_id].id = ship_id;
    board->ships[ship_id].size = size;
    board->ships[ship_id].row = row;
    board->ships[ship_id].col = col;
    board->ships[ship_id].direction = direction;
    board->ships[ship_id].hits = 0;
    board->ships[ship_id].is_placed = 1;
    board->ships[ship_id].is_sunk = 0;
    board->ships_placed_count++;

    return 0;
}

int fire_shot(Board *target_board, int row, int col, int *out_sunk, int *out_ship_size, int *out_game_over) {
    if (!target_board) return -1;

    if (row < 0 || row >= BOARD_SIZE || col < 0 || col >= BOARD_SIZE) {
        return -1;
    }

    int current_cell = target_board->grid[row][col];
    if (current_cell == CELL_HIT || current_cell == CELL_MISS) {
        /* Already fired at this location */
        return -2;
    }

    if (out_sunk) *out_sunk = 0;
    if (out_ship_size) *out_ship_size = 0;
    if (out_game_over) *out_game_over = 0;

    if (current_cell == CELL_SHIP) {
        target_board->grid[row][col] = CELL_HIT;
        int sid = target_board->ship_grid[row][col];
        if (sid >= 0 && sid < NUM_SHIPS) {
            target_board->ships[sid].hits++;
            if (target_board->ships[sid].hits >= target_board->ships[sid].size) {
                target_board->ships[sid].is_sunk = 1;
                if (out_sunk) *out_sunk = 1;
                if (out_ship_size) *out_ship_size = target_board->ships[sid].size;
            }
        }
        if (out_game_over) {
            *out_game_over = check_win(target_board);
        }
        return CELL_HIT;
    } else {
        target_board->grid[row][col] = CELL_MISS;
        return CELL_MISS;
    }
}

int check_win(const Board *board) {
    if (!board) return 0;
    for (int i = 0; i < NUM_SHIPS; i++) {
        if (!board->ships[i].is_placed || !board->ships[i].is_sunk) {
            return 0;
        }
    }
    return 1;
}

int get_ship_at(const Board *board, int row, int col) {
    if (!board || row < 0 || row >= BOARD_SIZE || col < 0 || col >= BOARD_SIZE) {
        return -1;
    }
    return board->ship_grid[row][col];
}
