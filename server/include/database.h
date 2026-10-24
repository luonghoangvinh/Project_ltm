#ifndef DATABASE_H
#define DATABASE_H

#include "common.h"
#include <stddef.h>

typedef struct {
    char match_id[64];
    char player1[32];
    char player2[32];
    char winner[32];
    char result[16];
    int p1_elo_before;
    int p2_elo_before;
    int p1_elo_after;
    int p2_elo_after;
    char player1_board[2048];
    char player2_board[2048];
    char player1_ships[2048];
    char player2_ships[2048];
    char start_time[32];
    char end_time[32];
} MatchRecord;

typedef struct {
    int id;
    char match_id[64];
    char player[32];
    int row;
    int col;
    char result[8];
    int sunk;
    int ship_size;
    int move_num;
    char created_at[32];
} MoveRecord;

int db_init(const char *db_path);
void db_close(void);

int db_register_user(const char *username, const char *password_hash);
int db_check_credentials(const char *username, const char *password_hash, int *out_elo);
int db_get_user_elo(const char *username, int *out_elo);
int db_update_elo(const char *username, int new_elo, int win, int loss, int draw);

int db_create_match(const char *match_id, const char *player1, const char *player2, int p1_elo, int p2_elo);
int db_save_match_boards(const char *match_id, const char *p1_board, const char *p2_board, const char *p1_ships, const char *p2_ships);
int db_save_match_result(const char *match_id, const char *winner, const char *result, int p1_elo_after, int p2_elo_after);
int db_log_move(const char *match_id, const char *player, int row, int col, const char *result, int sunk, int ship_size, int move_num);

int db_get_match_by_id(const char *match_id, MatchRecord *out_record);
int db_get_history(const char *username, int limit, MatchRecord **out_records, int *out_count);
void db_free_history(MatchRecord *records);

int db_get_replay_moves(const char *match_id, MoveRecord **out_moves, int *out_count);
void db_free_replay(MoveRecord *moves);

#endif /* DATABASE_H */
