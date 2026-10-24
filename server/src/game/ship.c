#include "game.h"
#include <stdio.h>

int validate_all_ships_placed(const Board *board) {
    if (!board) return 0;
    if (board->ships_placed_count != NUM_SHIPS) {
        return 0;
    }
    for (int i = 0; i < NUM_SHIPS; i++) {
        if (!board->ships[i].is_placed) {
            return 0;
        }
    }
    return 1;
}

int count_placed_ships(const Board *board) {
    if (!board) return 0;
    int count = 0;
    for (int i = 0; i < NUM_SHIPS; i++) {
        if (board->ships[i].is_placed) {
            count++;
        }
    }
    return count;
}
