#include "game.h"
#include "database.h"
#include "rating.h"
#include "network.h"
#include "protocol.h"
#include "cjson/cJSON.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>

static Game *g_games_head = NULL;
static pthread_mutex_t g_games_mutex = PTHREAD_MUTEX_INITIALIZER;

void game_manager_init(void) {
    pthread_mutex_lock(&g_games_mutex);
    g_games_head = NULL;
    pthread_mutex_unlock(&g_games_mutex);
}

Game* create_game(const char *match_id, const char *p1, int fd1, int elo1, const char *p2, int fd2, int elo2) {
    if (!match_id || !p1 || !p2) return NULL;

    Game *g = (Game *)malloc(sizeof(Game));
    if (!g) return NULL;

    memset(g, 0, sizeof(Game));
    strncpy(g->match_id, match_id, sizeof(g->match_id) - 1);
    strncpy(g->player1, p1, sizeof(g->player1) - 1);
    strncpy(g->player2, p2, sizeof(g->player2) - 1);
    g->player1_fd = fd1;
    g->player2_fd = fd2;
    g->player1_elo_before = elo1;
    g->player2_elo_before = elo2;

    init_board(&g->board1);
    init_board(&g->board2);

    g->ready1 = 0;
    g->ready2 = 0;
    g->current_turn = (rand() % 2) + 1; /* Randomize starting turn */
    g->state = GAME_STATE_PLACING;
    g->start_time = time(NULL);
    g->end_time = 0;
    g->draw_offered_by = 0;
    g->move_count = 0;

    /* Record match creation in database */
    db_create_match(match_id, p1, p2, elo1, elo2);

    pthread_mutex_lock(&g_games_mutex);
    g->next = g_games_head;
    g_games_head = g;
    pthread_mutex_unlock(&g_games_mutex);

    return g;
}

Game* find_game_by_id(const char *match_id) {
    if (!match_id) return NULL;

    pthread_mutex_lock(&g_games_mutex);
    Game *curr = g_games_head;
    while (curr) {
        if (strcmp(curr->match_id, match_id) == 0) {
            pthread_mutex_unlock(&g_games_mutex);
            return curr;
        }
        curr = curr->next;
    }
    pthread_mutex_unlock(&g_games_mutex);
    return NULL;
}

Game* find_game_by_username(const char *username) {
    if (!username) return NULL;

    pthread_mutex_lock(&g_games_mutex);
    Game *curr = g_games_head;
    while (curr) {
        if ((strcmp(curr->player1, username) == 0 || strcmp(curr->player2, username) == 0) &&
            curr->state != GAME_STATE_FINISHED) {
            pthread_mutex_unlock(&g_games_mutex);
            return curr;
        }
        curr = curr->next;
    }
    pthread_mutex_unlock(&g_games_mutex);
    return NULL;
}

int handle_place_ship(const char *username, const char *match_id, int ship_id, int row, int col, int direction, char *err_msg, size_t err_size) {
    pthread_mutex_lock(&g_games_mutex);
    Game *g = g_games_head;
    while (g) {
        if (strcmp(g->match_id, match_id) == 0) break;
        g = g->next;
    }

    if (!g) {
        pthread_mutex_unlock(&g_games_mutex);
        if (err_msg) snprintf(err_msg, err_size, "Match not found");
        return -1;
    }

    if (g->state != GAME_STATE_PLACING) {
        pthread_mutex_unlock(&g_games_mutex);
        if (err_msg) snprintf(err_msg, err_size, "Cannot place ships outside of PLACING state");
        return -1;
    }

    Board *target_board = NULL;
    if (strcmp(g->player1, username) == 0) {
        if (g->ready1) {
            pthread_mutex_unlock(&g_games_mutex);
            if (err_msg) snprintf(err_msg, err_size, "Cannot alter placement after declaring READY");
            return -1;
        }
        target_board = &g->board1;
    } else if (strcmp(g->player2, username) == 0) {
        if (g->ready2) {
            pthread_mutex_unlock(&g_games_mutex);
            if (err_msg) snprintf(err_msg, err_size, "Cannot alter placement after declaring READY");
            return -1;
        }
        target_board = &g->board2;
    } else {
        pthread_mutex_unlock(&g_games_mutex);
        if (err_msg) snprintf(err_msg, err_size, "User not in this match");
        return -1;
    }

    int rc = place_ship(target_board, ship_id, row, col, direction, err_msg, err_size);
    pthread_mutex_unlock(&g_games_mutex);
    return rc;
}

int handle_ready(const char *username, const char *match_id, int *out_both_ready, int *out_first_player, char *err_msg, size_t err_size) {
    if (out_both_ready) *out_both_ready = 0;
    if (out_first_player) *out_first_player = 0;

    pthread_mutex_lock(&g_games_mutex);
    Game *g = g_games_head;
    while (g) {
        if (strcmp(g->match_id, match_id) == 0) break;
        g = g->next;
    }

    if (!g) {
        pthread_mutex_unlock(&g_games_mutex);
        if (err_msg) snprintf(err_msg, err_size, "Match not found");
        return -1;
    }

    if (g->state != GAME_STATE_PLACING) {
        pthread_mutex_unlock(&g_games_mutex);
        if (err_msg) snprintf(err_msg, err_size, "Cannot declare READY in current game state");
        return -1;
    }

    if (strcmp(g->player1, username) == 0) {
        if (!validate_all_ships_placed(&g->board1)) {
            pthread_mutex_unlock(&g_games_mutex);
            if (err_msg) snprintf(err_msg, err_size, "Must place all 5 ships before READY");
            return -1;
        }
        g->ready1 = 1;
    } else if (strcmp(g->player2, username) == 0) {
        if (!validate_all_ships_placed(&g->board2)) {
            pthread_mutex_unlock(&g_games_mutex);
            if (err_msg) snprintf(err_msg, err_size, "Must place all 5 ships before READY");
            return -1;
        }
        g->ready2 = 1;
    } else {
        pthread_mutex_unlock(&g_games_mutex);
        if (err_msg) snprintf(err_msg, err_size, "User not in this match");
        return -1;
    }

    if (g->ready1 && g->ready2) {
        g->state = GAME_STATE_PLAYING;
        if (out_both_ready) *out_both_ready = 1;
        if (out_first_player) *out_first_player = g->current_turn;
    }

    pthread_mutex_unlock(&g_games_mutex);
    return 0;
}

void finish_and_record_game(Game *g, const char *winner, const char *reason) {
    if (!g || g->state == GAME_STATE_FINISHED) return;

    g->state = GAME_STATE_FINISHED;
    g->end_time = time(NULL);

    int is_draw = (strcmp(reason, "DRAW") == 0);
    double score1 = 0.5;
    if (!is_draw) {
        score1 = (strcmp(winner, g->player1) == 0) ? 1.0 : 0.0;
    }

    int delta1 = 0, delta2 = 0;
    calc_elo_change(g->player1_elo_before, g->player2_elo_before, score1, &delta1, &delta2);
    int new_elo1 = update_elo_value(g->player1_elo_before, delta1);
    int new_elo2 = update_elo_value(g->player2_elo_before, delta2);

    int p1_win = (score1 == 1.0) ? 1 : 0;
    int p1_loss = (score1 == 0.0) ? 1 : 0;
    int p2_win = p1_loss;
    int p2_loss = p1_win;
    int draw_val = is_draw ? 1 : 0;

    db_save_match_result(g->match_id, winner, reason, new_elo1, new_elo2);
    db_update_elo(g->player1, new_elo1, p1_win, p1_loss, draw_val);
    db_update_elo(g->player2, new_elo2, p2_win, p2_loss, draw_val);

    /* Construct and send GAME_OVER to both players */
    cJSON *msg1 = cJSON_CreateObject();
    cJSON_AddStringToObject(msg1, "type", "GAME_OVER");
    cJSON_AddStringToObject(msg1, "winner", winner ? winner : "");
    cJSON_AddStringToObject(msg1, "reason", reason ? reason : "");
    cJSON_AddNumberToObject(msg1, "elo_change", delta1);
    cJSON_AddNumberToObject(msg1, "new_elo", new_elo1);
    char *str1 = cJSON_PrintUnformatted(msg1);
    cJSON_Delete(msg1);

    cJSON *msg2 = cJSON_CreateObject();
    cJSON_AddStringToObject(msg2, "type", "GAME_OVER");
    cJSON_AddStringToObject(msg2, "winner", winner ? winner : "");
    cJSON_AddStringToObject(msg2, "reason", reason ? reason : "");
    cJSON_AddNumberToObject(msg2, "elo_change", delta2);
    cJSON_AddNumberToObject(msg2, "new_elo", new_elo2);
    char *str2 = cJSON_PrintUnformatted(msg2);
    cJSON_Delete(msg2);

    if (g->player1_fd > 0 && str1) {
        send_message(g->player1_fd, str1);
    }
    if (g->player2_fd > 0 && str2) {
        send_message(g->player2_fd, str2);
    }

    if (str1) free(str1);
    if (str2) free(str2);

    /* Set players back to IN_LOBBY */
    set_client_status(g->player1, STATUS_IN_LOBBY);
    set_client_status(g->player2, STATUS_IN_LOBBY);
    broadcast_player_update();
}

int handle_fire(const char *username, const char *match_id, int row, int col,
                int *out_result, int *out_sunk, int *out_ship_size, int *out_game_over,
                char *out_opponent, int *out_opp_fd, char *err_msg, size_t err_size) {
    pthread_mutex_lock(&g_games_mutex);
    Game *g = g_games_head;
    while (g) {
        if (strcmp(g->match_id, match_id) == 0) break;
        g = g->next;
    }

    if (!g) {
        pthread_mutex_unlock(&g_games_mutex);
        if (err_msg) snprintf(err_msg, err_size, "Match not found");
        return -1;
    }

    if (g->state != GAME_STATE_PLAYING) {
        pthread_mutex_unlock(&g_games_mutex);
        if (err_msg) snprintf(err_msg, err_size, "Game is not in PLAYING state");
        return -1;
    }

    int is_p1 = (strcmp(g->player1, username) == 0);
    int is_p2 = (strcmp(g->player2, username) == 0);
    if (!is_p1 && !is_p2) {
        pthread_mutex_unlock(&g_games_mutex);
        if (err_msg) snprintf(err_msg, err_size, "User not in this match");
        return -1;
    }

    if ((is_p1 && g->current_turn != 1) || (is_p2 && g->current_turn != 2)) {
        pthread_mutex_unlock(&g_games_mutex);
        if (err_msg) snprintf(err_msg, err_size, "Not your turn");
        return -1;
    }

    Board *target_board = is_p1 ? &g->board2 : &g->board1;
    const char *opp_name = is_p1 ? g->player2 : g->player1;
    int opp_fd = is_p1 ? g->player2_fd : g->player1_fd;

    if (out_opponent) snprintf(out_opponent, 32, "%s", opp_name);
    if (out_opp_fd) *out_opp_fd = opp_fd;

    int shot_res = fire_shot(target_board, row, col, out_sunk, out_ship_size, out_game_over);
    if (shot_res == -2) {
        pthread_mutex_unlock(&g_games_mutex);
        if (err_msg) snprintf(err_msg, err_size, "Cell (%d, %d) has already been fired upon", row, col);
        return -1;
    } else if (shot_res == -1) {
        pthread_mutex_unlock(&g_games_mutex);
        if (err_msg) snprintf(err_msg, err_size, "Coordinates (%d, %d) out of bounds", row, col);
        return -1;
    }

    if (out_result) *out_result = shot_res;

    g->move_count++;
    const char *res_str = (shot_res == CELL_HIT) ? "HIT" : "MISS";
    db_log_move(g->match_id, username, row, col, res_str, out_sunk ? *out_sunk : 0, out_ship_size ? *out_ship_size : 0, g->move_count);

    /* If draw was pending, cancel it on new move */
    g->draw_offered_by = 0;

    if (out_game_over && *out_game_over) {
        /* Win condition met */
        finish_and_record_game(g, username, "WIN");
    } else {
        /* Alternate turn */
        g->current_turn = (g->current_turn == 1) ? 2 : 1;
    }

    pthread_mutex_unlock(&g_games_mutex);
    return 0;
}

int handle_surrender(const char *username, const char *match_id, char *out_winner, char *out_loser, int *out_p1_fd, int *out_p2_fd) {
    pthread_mutex_lock(&g_games_mutex);
    Game *g = g_games_head;
    while (g) {
        if (strcmp(g->match_id, match_id) == 0) break;
        g = g->next;
    }

    if (!g || g->state == GAME_STATE_FINISHED) {
        pthread_mutex_unlock(&g_games_mutex);
        return -1;
    }

    const char *winner = NULL;
    const char *loser = username;
    if (strcmp(g->player1, username) == 0) {
        winner = g->player2;
    } else if (strcmp(g->player2, username) == 0) {
        winner = g->player1;
    } else {
        pthread_mutex_unlock(&g_games_mutex);
        return -1;
    }

    if (out_winner) snprintf(out_winner, 32, "%s", winner);
    if (out_loser) snprintf(out_loser, 32, "%s", loser);
    if (out_p1_fd) *out_p1_fd = g->player1_fd;
    if (out_p2_fd) *out_p2_fd = g->player2_fd;

    finish_and_record_game(g, winner, "SURRENDER");
    pthread_mutex_unlock(&g_games_mutex);
    return 0;
}

int handle_draw_offer(const char *username, const char *match_id, char *out_opponent, int *out_opp_fd, char *err_msg, size_t err_size) {
    pthread_mutex_lock(&g_games_mutex);
    Game *g = g_games_head;
    while (g) {
        if (strcmp(g->match_id, match_id) == 0) break;
        g = g->next;
    }

    if (!g || g->state != GAME_STATE_PLAYING) {
        pthread_mutex_unlock(&g_games_mutex);
        if (err_msg) snprintf(err_msg, err_size, "Game is not active");
        return -1;
    }

    int is_p1 = (strcmp(g->player1, username) == 0);
    int is_p2 = (strcmp(g->player2, username) == 0);
    if (!is_p1 && !is_p2) {
        pthread_mutex_unlock(&g_games_mutex);
        if (err_msg) snprintf(err_msg, err_size, "User not in match");
        return -1;
    }

    int player_num = is_p1 ? 1 : 2;
    if (g->draw_offered_by == player_num) {
        pthread_mutex_unlock(&g_games_mutex);
        if (err_msg) snprintf(err_msg, err_size, "Draw offer already pending");
        return -1;
    }

    g->draw_offered_by = player_num;
    const char *opp_name = is_p1 ? g->player2 : g->player1;
    int opp_fd = is_p1 ? g->player2_fd : g->player1_fd;

    if (out_opponent) snprintf(out_opponent, 32, "%s", opp_name);
    if (out_opp_fd) *out_opp_fd = opp_fd;

    pthread_mutex_unlock(&g_games_mutex);
    return 0;
}

int handle_draw_reply(const char *username, const char *match_id, int accept,
                      char *out_p1, char *out_p2, int *out_p1_fd, int *out_p2_fd, char *err_msg, size_t err_size) {
    pthread_mutex_lock(&g_games_mutex);
    Game *g = g_games_head;
    while (g) {
        if (strcmp(g->match_id, match_id) == 0) break;
        g = g->next;
    }

    if (!g || g->state != GAME_STATE_PLAYING) {
        pthread_mutex_unlock(&g_games_mutex);
        if (err_msg) snprintf(err_msg, err_size, "Game is not active");
        return -1;
    }

    int is_p1 = (strcmp(g->player1, username) == 0);
    int is_p2 = (strcmp(g->player2, username) == 0);
    if (!is_p1 && !is_p2) {
        pthread_mutex_unlock(&g_games_mutex);
        if (err_msg) snprintf(err_msg, err_size, "User not in match");
        return -1;
    }

    int opp_num = is_p1 ? 2 : 1;

    if (g->draw_offered_by != opp_num) {
        pthread_mutex_unlock(&g_games_mutex);
        if (err_msg) snprintf(err_msg, err_size, "No pending draw offer to respond to");
        return -1;
    }

    if (out_p1) snprintf(out_p1, 32, "%s", g->player1);
    if (out_p2) snprintf(out_p2, 32, "%s", g->player2);
    if (out_p1_fd) *out_p1_fd = g->player1_fd;
    if (out_p2_fd) *out_p2_fd = g->player2_fd;

    if (accept) {
        finish_and_record_game(g, "", "DRAW");
    } else {
        g->draw_offered_by = 0;
    }

    pthread_mutex_unlock(&g_games_mutex);
    return 0;
}

int handle_disconnect_game(const char *username, char *out_match_id, char *out_winner, int *out_winner_fd) {
    if (!username) return -1;

    pthread_mutex_lock(&g_games_mutex);
    Game *g = g_games_head;
    while (g) {
        if ((strcmp(g->player1, username) == 0 || strcmp(g->player2, username) == 0) &&
            g->state != GAME_STATE_FINISHED) {
            break;
        }
        g = g->next;
    }

    if (!g) {
        pthread_mutex_unlock(&g_games_mutex);
        return -1;
    }

    const char *winner = NULL;
    int win_fd = -1;
    if (strcmp(g->player1, username) == 0) {
        winner = g->player2;
        win_fd = g->player2_fd;
    } else {
        winner = g->player1;
        win_fd = g->player1_fd;
    }

    if (out_match_id) snprintf(out_match_id, 64, "%s", g->match_id);
    if (out_winner) snprintf(out_winner, 32, "%s", winner);
    if (out_winner_fd) *out_winner_fd = win_fd;

    finish_and_record_game(g, winner, "FORFEIT");
    pthread_mutex_unlock(&g_games_mutex);
    return 0;
}

void remove_game(const char *match_id) {
    if (!match_id) return;

    pthread_mutex_lock(&g_games_mutex);
    Game **curr = &g_games_head;
    while (*curr) {
        if (strcmp((*curr)->match_id, match_id) == 0) {
            Game *to_free = *curr;
            *curr = (*curr)->next;
            free(to_free);
            break;
        }
        curr = &(*curr)->next;
    }
    pthread_mutex_unlock(&g_games_mutex);
}

void game_manager_cleanup(void) {
    pthread_mutex_lock(&g_games_mutex);
    Game *curr = g_games_head;
    while (curr) {
        Game *next = curr->next;
        free(curr);
        curr = next;
    }
    g_games_head = NULL;
    pthread_mutex_unlock(&g_games_mutex);
}
