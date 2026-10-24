#ifndef GAME_H
#define GAME_H

#include "common.h"
#include <stddef.h>

typedef struct {
    int id;             /* 0 to NUM_SHIPS-1 */
    int size;           /* 2, 3, 3, 4, 5 */
    int row;            /* top-left start row */
    int col;            /* top-left start col */
    int direction;      /* DIR_HORIZONTAL (0) or DIR_VERTICAL (1) */
    int hits;           /* number of hits taken */
    int is_placed;      /* 1 if placed, 0 otherwise */
    int is_sunk;        /* 1 if sunk, 0 otherwise */
} Ship;

typedef struct {
    int grid[BOARD_SIZE][BOARD_SIZE];       /* CELL_EMPTY, CELL_SHIP, CELL_HIT, CELL_MISS */
    int ship_grid[BOARD_SIZE][BOARD_SIZE];  /* ship_id (0..4) or -1 if empty */
    Ship ships[NUM_SHIPS];
    int ships_placed_count;
} Board;

typedef struct Game {
    char match_id[64];
    char player1[32];
    char player2[32];
    int player1_fd;
    int player2_fd;
    int player1_elo_before;
    int player2_elo_before;
    Board board1;       /* player1's ships & opponent's shots */
    Board board2;       /* player2's ships & opponent's shots */
    int ready1;         /* 1 if ready, 0 otherwise */
    int ready2;         /* 1 if ready, 0 otherwise */
    int current_turn;   /* 1 for player1, 2 for player2 */
    int state;          /* GAME_STATE_PLACING, GAME_STATE_PLAYING, GAME_STATE_FINISHED */
    time_t start_time;
    time_t end_time;
    int draw_offered_by;/* 0: none, 1: player1, 2: player2 */
    int move_count;
    struct Game *next;
} Game;

/* Board & Ship operations */
void init_board(Board *board);
int place_ship(Board *board, int ship_id, int row, int col, int direction, char *err_msg, size_t err_size);
int validate_all_ships_placed(const Board *board);
int fire_shot(Board *target_board, int row, int col, int *out_sunk, int *out_ship_size, int *out_game_over);
int check_win(const Board *board);
int get_ship_at(const Board *board, int row, int col);

/* Game manager operations */
void game_manager_init(void);
Game* create_game(const char *match_id, const char *p1, int fd1, int elo1, const char *p2, int fd2, int elo2);
Game* find_game_by_id(const char *match_id);
Game* find_game_by_username(const char *username);

int handle_place_ship(const char *username, const char *match_id, int ship_id, int row, int col, int direction, char *err_msg, size_t err_size);
int handle_ready(const char *username, const char *match_id, int *out_both_ready, int *out_first_player, char *err_msg, size_t err_size);
int handle_fire(const char *username, const char *match_id, int row, int col,
                int *out_result, int *out_sunk, int *out_ship_size, int *out_game_over,
                char *out_opponent, int *out_opp_fd, char *err_msg, size_t err_size);
int handle_surrender(const char *username, const char *match_id, char *out_winner, char *out_loser, int *out_p1_fd, int *out_p2_fd);
int handle_draw_offer(const char *username, const char *match_id, char *out_opponent, int *out_opp_fd, char *err_msg, size_t err_size);
int handle_draw_reply(const char *username, const char *match_id, int accept,
                      char *out_p1, char *out_p2, int *out_p1_fd, int *out_p2_fd, char *err_msg, size_t err_size);
int handle_disconnect_game(const char *username, char *out_match_id, char *out_winner, int *out_winner_fd);
void finish_and_record_game(Game *game, const char *winner, const char *reason);
char* serialize_board_ships(const Board *board);
void remove_game(const char *match_id);
char* get_replay_json(const char *match_id);
void game_manager_cleanup(void);

#endif /* GAME_H */
