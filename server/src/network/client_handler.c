#include "network.h"
#include "protocol.h"
#include "auth.h"
#include "session.h"
#include "matchmaking.h"
#include "game.h"
#include "database.h"
#include "cjson/cJSON.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void handle_client_disconnect(ClientInfo *client) {
    if (!client) return;

    if (strlen(client->username) > 0) {
        printf("[INFO] Client '%s' disconnected (fd=%d)\n", client->username, client->fd);

        /* Cancel any pending matchmaking challenges and remove from matchmaking queue */
        cancel_challenges_for_user(client->username);
        matchmaking_queue_remove(client->username);

        /* Handle match disconnect if player was in an active game */
        char match_id[64] = {0};
        char winner[32] = {0};
        int winner_fd = -1;
        if (handle_disconnect_game(client->username, match_id, winner, &winner_fd) == 0) {
            printf("[INFO] Match %s ended by forfeit due to %s disconnect. Winner: %s\n",
                   match_id, client->username, winner);
        }

        /* Destroy session */
        destroy_session_by_username(client->username);
    } else {
        printf("[INFO] Unauthenticated client disconnected (fd=%d)\n", client->fd);
    }

    /* Mark inactive and close socket */
    pthread_mutex_lock(&g_server.clients_mutex);
    client->active = 0;
    client->username[0] = '\0';
    client->session_token[0] = '\0';
    client->current_match_id[0] = '\0';
    client->status = STATUS_OFFLINE;
    close(client->fd);
    client->fd = -1;
    pthread_mutex_unlock(&g_server.clients_mutex);

    broadcast_player_update();
}

static void handle_login(ClientInfo *client, cJSON *root) {
    cJSON *user_item = cJSON_GetObjectItemCaseSensitive(root, "username");
    cJSON *pass_item = cJSON_GetObjectItemCaseSensitive(root, "password");

    if (!cJSON_IsString(user_item) || !cJSON_IsString(pass_item)) {
        send_error(client->fd, "Invalid username or password format");
        return;
    }

    const char *username = user_item->valuestring;
    const char *password = pass_item->valuestring;

    char err_msg[128];
    int elo = 1200;
    if (login_user(username, password, &elo, err_msg, sizeof(err_msg)) != 0) {
        send_error(client->fd, err_msg);
        return;
    }

    char token[64];
    if (create_session(username, token, sizeof(token)) != 0) {
        send_error(client->fd, "Failed to create session");
        return;
    }

    pthread_mutex_lock(&g_server.clients_mutex);
    strncpy(client->username, username, sizeof(client->username) - 1);
    client->username[sizeof(client->username) - 1] = '\0';
    strncpy(client->session_token, token, sizeof(client->session_token) - 1);
    client->session_token[sizeof(client->session_token) - 1] = '\0';
    client->status = STATUS_IN_LOBBY;
    pthread_mutex_unlock(&g_server.clients_mutex);

    cJSON *resp = cJSON_CreateObject();
    cJSON_AddStringToObject(resp, "type", "LOGIN_OK");
    cJSON_AddStringToObject(resp, "session_token", token);
    cJSON_AddStringToObject(resp, "username", username);
    cJSON_AddNumberToObject(resp, "elo", elo);
    char *s = cJSON_PrintUnformatted(resp);
    cJSON_Delete(resp);

    if (s) {
        send_message(client->fd, s);
        free(s);
    }

    printf("[INFO] User '%s' logged in successfully (fd=%d, elo=%d)\n", username, client->fd, elo);
    broadcast_player_update();
}

static void handle_register(ClientInfo *client, cJSON *root) {
    cJSON *user_item = cJSON_GetObjectItemCaseSensitive(root, "username");
    cJSON *pass_item = cJSON_GetObjectItemCaseSensitive(root, "password");

    if (!cJSON_IsString(user_item) || !cJSON_IsString(pass_item)) {
        send_error(client->fd, "Invalid username or password format");
        return;
    }

    char err_msg[128];
    if (register_user(user_item->valuestring, pass_item->valuestring, err_msg, sizeof(err_msg)) != 0) {
        send_error(client->fd, err_msg);
        return;
    }

    cJSON *resp = cJSON_CreateObject();
    cJSON_AddStringToObject(resp, "type", "REGISTER_OK");
    cJSON_AddStringToObject(resp, "message", "Registration successful");
    char *s = cJSON_PrintUnformatted(resp);
    cJSON_Delete(resp);

    if (s) {
        send_message(client->fd, s);
        free(s);
    }
    printf("[INFO] User '%s' registered successfully\n", user_item->valuestring);
}

static void handle_logout(ClientInfo *client, const char *token) {
    destroy_session(token);

    /* If user was in an active game, forfeit */
    char match_id[64] = {0};
    char winner[32] = {0};
    int win_fd = -1;
    handle_disconnect_game(client->username, match_id, winner, &win_fd);
    cancel_challenges_for_user(client->username);
    matchmaking_queue_remove(client->username);

    pthread_mutex_lock(&g_server.clients_mutex);
    client->username[0] = '\0';
    client->session_token[0] = '\0';
    client->current_match_id[0] = '\0';
    client->status = STATUS_ONLINE;
    pthread_mutex_unlock(&g_server.clients_mutex);

    cJSON *resp = cJSON_CreateObject();
    cJSON_AddStringToObject(resp, "type", "LOGOUT_OK");
    char *s = cJSON_PrintUnformatted(resp);
    cJSON_Delete(resp);

    if (s) {
        send_message(client->fd, s);
        free(s);
    }

    broadcast_player_update();
}

static void handle_list_players(ClientInfo *client) {
    cJSON *resp = cJSON_CreateObject();
    cJSON_AddStringToObject(resp, "type", "PLAYER_LIST");
    cJSON *arr = cJSON_CreateArray();

    pthread_mutex_lock(&g_server.clients_mutex);
    for (int i = 0; i < MAX_CLIENTS; i++) {
        if (g_server.clients[i].active && strlen(g_server.clients[i].username) > 0) {
            cJSON *p = cJSON_CreateObject();
            cJSON_AddStringToObject(p, "username", g_server.clients[i].username);

            int elo = 1200;
            db_get_user_elo(g_server.clients[i].username, &elo);
            cJSON_AddNumberToObject(p, "elo", elo);

            const char *st = "ONLINE";
            if (g_server.clients[i].status == STATUS_IN_LOBBY) st = "IN_LOBBY";
            else if (g_server.clients[i].status == STATUS_IN_GAME) st = "IN_GAME";
            else if (g_server.clients[i].status == STATUS_MATCHMAKING) st = "MATCHMAKING";

            cJSON_AddStringToObject(p, "status", st);
            cJSON_AddItemToArray(arr, p);
        }
    }
    pthread_mutex_unlock(&g_server.clients_mutex);

    cJSON_AddItemToObject(resp, "players", arr);
    char *s = cJSON_PrintUnformatted(resp);
    cJSON_Delete(resp);

    if (s) {
        send_message(client->fd, s);
        free(s);
    }
}

static void handle_challenge(ClientInfo *client, cJSON *root) {
    if (client->status == STATUS_MATCHMAKING) {
        send_error(client->fd, "You cannot challenge while searching for a match. Cancel matchmaking first.");
        return;
    }

    cJSON *target_item = cJSON_GetObjectItemCaseSensitive(root, "target");
    if (!cJSON_IsString(target_item)) {
        target_item = cJSON_GetObjectItemCaseSensitive(root, "opponent");
    }
    if (!cJSON_IsString(target_item)) {
        send_error(client->fd, "Missing target player");
        return;
    }

    char match_id[64];
    char err[128];
    if (challenge_player(client->username, target_item->valuestring, match_id, sizeof(match_id), err, sizeof(err)) != 0) {
        send_error(client->fd, err);
        return;
    }

    cJSON *resp = cJSON_CreateObject();
    cJSON_AddStringToObject(resp, "type", "CHALLENGE_SENT");
    cJSON_AddStringToObject(resp, "target", target_item->valuestring);
    cJSON_AddStringToObject(resp, "match_id", match_id);
    char *s = cJSON_PrintUnformatted(resp);
    cJSON_Delete(resp);

    if (s) {
        send_message(client->fd, s);
        free(s);
    }
}

static void handle_challenge_reply(ClientInfo *client, cJSON *root) {
    cJSON *mid_item = cJSON_GetObjectItemCaseSensitive(root, "match_id");
    cJSON *acc_item = cJSON_GetObjectItemCaseSensitive(root, "accept");

    if (!cJSON_IsString(mid_item) || !cJSON_IsBool(acc_item)) {
        send_error(client->fd, "Invalid challenge reply format");
        return;
    }

    char err[128];
    int accept = cJSON_IsTrue(acc_item) ? 1 : 0;
    if (reply_challenge(client->username, mid_item->valuestring, accept, err, sizeof(err)) != 0) {
        send_error(client->fd, err);
    }
}

/* Xử lý yêu cầu tham gia hàng chờ tìm trận (Random Matchmaking) */
static void handle_find_match(ClientInfo *client) {
    if (!client || strlen(client->username) == 0) return;

    if (client->status == STATUS_IN_GAME) {
        send_error(client->fd, "You are currently in a game");
        return;
    }

    if (matchmaking_is_queued(client->username)) {
        cJSON *resp = cJSON_CreateObject();
        cJSON_AddStringToObject(resp, "type", "FIND_MATCH_RESPONSE");
        cJSON_AddStringToObject(resp, "status", "ALREADY_QUEUED");
        cJSON_AddStringToObject(resp, "message", "Already in matchmaking queue");
        char *s = cJSON_PrintUnformatted(resp);
        cJSON_Delete(resp);
        if (s) {
            send_message(client->fd, s);
            free(s);
        }
        return;
    }

    int res = matchmaking_queue_add(client->username);
    if (res == 0 || res == 1) {
        if (client->status != STATUS_IN_GAME) {
            set_client_status(client->username, STATUS_MATCHMAKING);
        }
        broadcast_player_update();

        cJSON *resp = cJSON_CreateObject();
        cJSON_AddStringToObject(resp, "type", "FIND_MATCH_RESPONSE");
        cJSON_AddStringToObject(resp, "status", "QUEUED");
        cJSON_AddStringToObject(resp, "message", "Joined matchmaking queue");
        char *s = cJSON_PrintUnformatted(resp);
        cJSON_Delete(resp);
        if (s) {
            send_message(client->fd, s);
            free(s);
        }
    } else {
        send_error(client->fd, "Failed to join matchmaking queue");
    }
}

/* Xử lý hủy tìm trận */
static void handle_cancel_find_match(ClientInfo *client) {
    if (!client || strlen(client->username) == 0) return;

    matchmaking_queue_remove(client->username);
    if (client->status == STATUS_MATCHMAKING) {
        set_client_status(client->username, STATUS_IN_LOBBY);
    }
    broadcast_player_update();

    cJSON *resp = cJSON_CreateObject();
    cJSON_AddStringToObject(resp, "type", "CANCEL_FIND_MATCH_RESPONSE");
    cJSON_AddStringToObject(resp, "status", "CANCELLED");
    cJSON_AddStringToObject(resp, "message", "Left matchmaking queue");
    char *s = cJSON_PrintUnformatted(resp);
    cJSON_Delete(resp);
    if (s) {
        send_message(client->fd, s);
        free(s);
    }
}

static void handle_place_ship_msg(ClientInfo *client, cJSON *root) {
    const char *match_id = NULL;
    cJSON *mid_item = cJSON_GetObjectItemCaseSensitive(root, "match_id");
    if (cJSON_IsString(mid_item) && strlen(mid_item->valuestring) > 0) {
        match_id = mid_item->valuestring;
    } else if (strlen(client->current_match_id) > 0) {
        match_id = client->current_match_id;
    }

    if (!match_id) {
        send_error(client->fd, "Missing match_id for PLACE_SHIP");
        return;
    }

    int ship_id = -1;
    cJSON *sid_item = cJSON_GetObjectItemCaseSensitive(root, "ship_id");
    if (!sid_item) sid_item = cJSON_GetObjectItemCaseSensitive(root, "ship_idx");
    if (cJSON_IsNumber(sid_item)) {
        ship_id = sid_item->valueint;
    } else if (cJSON_IsString(sid_item)) {
        ship_id = atoi(sid_item->valuestring);
    } else {
        cJSON *sz_item = cJSON_GetObjectItemCaseSensitive(root, "ship_size");
        if (!sz_item) sz_item = cJSON_GetObjectItemCaseSensitive(root, "size");
        if (cJSON_IsNumber(sz_item)) {
            int sz = sz_item->valueint;
            if (sz == 2) ship_id = 0;
            else if (sz == 3) ship_id = 1;
            else if (sz == 4) ship_id = 3;
            else if (sz == 5) ship_id = 4;
        }
    }

    if (ship_id < 0 || ship_id >= NUM_SHIPS) {
        send_error(client->fd, "Invalid PLACE_SHIP: ship_id out of range (0..4)");
        return;
    }

    cJSON *row_item = cJSON_GetObjectItemCaseSensitive(root, "row");
    cJSON *col_item = cJSON_GetObjectItemCaseSensitive(root, "col");
    if (!row_item || !col_item) {
        send_error(client->fd, "Invalid PLACE_SHIP: missing row or col");
        return;
    }

    int row = cJSON_IsNumber(row_item) ? row_item->valueint : atoi(row_item->valuestring);
    int col = cJSON_IsNumber(col_item) ? col_item->valueint : atoi(col_item->valuestring);

    cJSON *dir_item = cJSON_GetObjectItemCaseSensitive(root, "direction");
    if (!dir_item) {
        dir_item = cJSON_GetObjectItemCaseSensitive(root, "orientation");
    }

    int direction = DIR_HORIZONTAL;
    if (cJSON_IsString(dir_item)) {
        char d = dir_item->valuestring[0];
        if (d == 'V' || d == 'v' || d == '1') {
            direction = DIR_VERTICAL;
        }
    } else if (cJSON_IsNumber(dir_item)) {
        direction = (dir_item->valueint == 1) ? DIR_VERTICAL : DIR_HORIZONTAL;
    }

    char err[128];
    if (handle_place_ship(client->username, match_id,
                          ship_id, row, col,
                          direction, err, sizeof(err)) != 0) {
        send_error(client->fd, err);
        return;
    }

    cJSON *resp = cJSON_CreateObject();
    cJSON_AddStringToObject(resp, "type", "PLACE_SHIP_OK");
    cJSON_AddNumberToObject(resp, "ship_id", ship_id);
    char *s = cJSON_PrintUnformatted(resp);
    cJSON_Delete(resp);

    if (s) {
        send_message(client->fd, s);
        free(s);
    }
}

static void handle_ready_msg(ClientInfo *client, cJSON *root) {
    const char *match_id = NULL;
    cJSON *mid_item = cJSON_GetObjectItemCaseSensitive(root, "match_id");
    if (cJSON_IsString(mid_item) && strlen(mid_item->valuestring) > 0) {
        match_id = mid_item->valuestring;
    } else if (strlen(client->current_match_id) > 0) {
        match_id = client->current_match_id;
    }

    if (!match_id) {
        send_error(client->fd, "Missing match_id for READY");
        return;
    }

    int both_ready = 0;
    int first_player = 0;
    char err[128];
    if (handle_ready(client->username, match_id, &both_ready, &first_player, err, sizeof(err)) != 0) {
        send_error(client->fd, err);
        return;
    }

    /* Send READY_OK to current client */
    cJSON *resp = cJSON_CreateObject();
    cJSON_AddStringToObject(resp, "type", "READY_OK");
    char *s = cJSON_PrintUnformatted(resp);
    cJSON_Delete(resp);
    if (s) {
        send_message(client->fd, s);
        free(s);
    }

    /* Notify opponent of readiness */
    Game *g = find_game_by_id(match_id);
    if (g) {
        int opp_fd = (strcmp(g->player1, client->username) == 0) ? g->player2_fd : g->player1_fd;
        cJSON *opp_msg = cJSON_CreateObject();
        cJSON_AddStringToObject(opp_msg, "type", "OPPONENT_READY");
        cJSON_AddStringToObject(opp_msg, "player", client->username);
        char *opp_str = cJSON_PrintUnformatted(opp_msg);
        cJSON_Delete(opp_msg);
        if (opp_str) {
            send_message(opp_fd, opp_str);
            free(opp_str);
        }
    }

    /* If both are ready, game starts! Notify first player with YOUR_TURN and second player with GAME_START */
    if (both_ready && g) {
        int first_fd = (first_player == 1) ? g->player1_fd : g->player2_fd;
        int second_fd = (first_player == 1) ? g->player2_fd : g->player1_fd;

        cJSON *start_msg = cJSON_CreateObject();
        cJSON_AddStringToObject(start_msg, "type", "GAME_START");
        cJSON_AddStringToObject(start_msg, "match_id", g->match_id);
        char *start_str = cJSON_PrintUnformatted(start_msg);
        cJSON_Delete(start_msg);
        if (start_str) {
            send_message(second_fd, start_str);
            free(start_str);
        }

        cJSON *turn_msg = cJSON_CreateObject();
        cJSON_AddStringToObject(turn_msg, "type", "YOUR_TURN");
        cJSON_AddStringToObject(turn_msg, "match_id", g->match_id);
        char *turn_str = cJSON_PrintUnformatted(turn_msg);
        cJSON_Delete(turn_msg);
        if (turn_str) {
            send_message(first_fd, turn_str);
            free(turn_str);
        }
    }
}

static void handle_fire_msg(ClientInfo *client, cJSON *root) {
    const char *match_id = NULL;
    cJSON *mid_item = cJSON_GetObjectItemCaseSensitive(root, "match_id");
    if (cJSON_IsString(mid_item) && strlen(mid_item->valuestring) > 0) {
        match_id = mid_item->valuestring;
    } else if (strlen(client->current_match_id) > 0) {
        match_id = client->current_match_id;
    }

    if (!match_id) {
        send_error(client->fd, "Missing match_id for FIRE");
        return;
    }

    cJSON *row_item = cJSON_GetObjectItemCaseSensitive(root, "row");
    cJSON *col_item = cJSON_GetObjectItemCaseSensitive(root, "col");
    if (!row_item || !col_item) {
        send_error(client->fd, "Invalid FIRE parameters: missing row or col");
        return;
    }

    int row = cJSON_IsNumber(row_item) ? row_item->valueint : atoi(row_item->valuestring);
    int col = cJSON_IsNumber(col_item) ? col_item->valueint : atoi(col_item->valuestring);
    int result = 0, sunk = 0, ship_size = 0, game_over = 0;
    char opponent[32] = {0};
    int opp_fd = -1;
    char err[128];

    if (handle_fire(client->username, match_id, row, col,
                    &result, &sunk, &ship_size, &game_over,
                    opponent, &opp_fd, err, sizeof(err)) != 0) {
        send_error(client->fd, err);
        return;
    }

    const char *res_str = (result == CELL_HIT) ? "HIT" : "MISS";

    /* Send FIRE_RESULT to shooter */
    cJSON *res_msg = cJSON_CreateObject();
    cJSON_AddStringToObject(res_msg, "type", "FIRE_RESULT");
    cJSON_AddNumberToObject(res_msg, "row", row);
    cJSON_AddNumberToObject(res_msg, "col", col);
    cJSON_AddStringToObject(res_msg, "result", res_str);
    cJSON_AddBoolToObject(res_msg, "sunk", sunk ? 1 : 0);
    cJSON_AddNumberToObject(res_msg, "ship_size", ship_size);
    cJSON_AddBoolToObject(res_msg, "game_over", game_over ? 1 : 0);
    cJSON_AddStringToObject(res_msg, "winner", game_over ? client->username : "");
    char *res_str_json = cJSON_PrintUnformatted(res_msg);
    cJSON_Delete(res_msg);

    if (res_str_json) {
        send_message(client->fd, res_str_json);
        free(res_str_json);
    }

    /* Send OPPONENT_FIRED to opponent */
    if (opp_fd > 0) {
        cJSON *opp_msg = cJSON_CreateObject();
        cJSON_AddStringToObject(opp_msg, "type", "OPPONENT_FIRED");
        cJSON_AddNumberToObject(opp_msg, "row", row);
        cJSON_AddNumberToObject(opp_msg, "col", col);
        cJSON_AddStringToObject(opp_msg, "result", res_str);
        cJSON_AddBoolToObject(opp_msg, "sunk", sunk ? 1 : 0);
        cJSON_AddNumberToObject(opp_msg, "ship_size", ship_size);
        char *opp_str_json = cJSON_PrintUnformatted(opp_msg);
        cJSON_Delete(opp_msg);

        if (opp_str_json) {
            send_message(opp_fd, opp_str_json);
            free(opp_str_json);
        }

        /* If game is not over, send YOUR_TURN to opponent */
        if (!game_over) {
            cJSON *turn_msg = cJSON_CreateObject();
            cJSON_AddStringToObject(turn_msg, "type", "YOUR_TURN");
            cJSON_AddStringToObject(turn_msg, "match_id", mid_item->valuestring);
            char *t_str = cJSON_PrintUnformatted(turn_msg);
            cJSON_Delete(turn_msg);

            if (t_str) {
                send_message(opp_fd, t_str);
                free(t_str);
            }
        }
    }
}

static void handle_surrender_msg(ClientInfo *client, cJSON *root) {
    cJSON *mid_item = cJSON_GetObjectItemCaseSensitive(root, "match_id");
    if (!cJSON_IsString(mid_item)) {
        send_error(client->fd, "Missing match_id");
        return;
    }

    char winner[32] = {0};
    char loser[32] = {0};
    int p1_fd = -1, p2_fd = -1;
    if (handle_surrender(client->username, mid_item->valuestring, winner, loser, &p1_fd, &p2_fd) != 0) {
        send_error(client->fd, "Failed to surrender match");
    }
}

static void handle_draw_offer_msg(ClientInfo *client, cJSON *root) {
    cJSON *mid_item = cJSON_GetObjectItemCaseSensitive(root, "match_id");
    if (!cJSON_IsString(mid_item)) {
        send_error(client->fd, "Missing match_id");
        return;
    }

    char opponent[32] = {0};
    int opp_fd = -1;
    char err[128];
    if (handle_draw_offer(client->username, mid_item->valuestring, opponent, &opp_fd, err, sizeof(err)) != 0) {
        send_error(client->fd, err);
        return;
    }

    if (opp_fd > 0) {
        cJSON *offer = cJSON_CreateObject();
        cJSON_AddStringToObject(offer, "type", "DRAW_OFFER");
        cJSON_AddStringToObject(offer, "match_id", mid_item->valuestring);
        cJSON_AddStringToObject(offer, "from", client->username);
        char *s = cJSON_PrintUnformatted(offer);
        cJSON_Delete(offer);

        if (s) {
            send_message(opp_fd, s);
            free(s);
        }
    }
}

static void handle_draw_reply_msg(ClientInfo *client, cJSON *root) {
    cJSON *mid_item = cJSON_GetObjectItemCaseSensitive(root, "match_id");
    cJSON *acc_item = cJSON_GetObjectItemCaseSensitive(root, "accept");

    if (!cJSON_IsString(mid_item) || !cJSON_IsBool(acc_item)) {
        send_error(client->fd, "Invalid DRAW_REPLY parameters");
        return;
    }

    int accept = cJSON_IsTrue(acc_item) ? 1 : 0;
    char p1[32] = {0}, p2[32] = {0};
    int p1_fd = -1, p2_fd = -1;
    char err[128];

    if (handle_draw_reply(client->username, mid_item->valuestring, accept,
                          p1, p2, &p1_fd, &p2_fd, err, sizeof(err)) != 0) {
        send_error(client->fd, err);
        return;
    }

    cJSON *res = cJSON_CreateObject();
    cJSON_AddStringToObject(res, "type", "DRAW_RESULT");
    cJSON_AddBoolToObject(res, "accept", accept);
    cJSON_AddStringToObject(res, "message", accept ? "Draw offer accepted" : "Draw offer declined");
    char *s = cJSON_PrintUnformatted(res);
    cJSON_Delete(res);

    if (s) {
        if (p1_fd > 0) send_message(p1_fd, s);
        if (p2_fd > 0 && p2_fd != p1_fd) send_message(p2_fd, s);
        free(s);
    }
}

static void handle_history_msg(ClientInfo *client, cJSON *root) {
    cJSON *lim_item = cJSON_GetObjectItemCaseSensitive(root, "limit");
    int limit = 10;
    if (cJSON_IsNumber(lim_item)) {
        limit = lim_item->valueint;
    }

    MatchRecord *records = NULL;
    int count = 0;
    if (db_get_history(client->username, limit, &records, &count) != 0) {
        send_error(client->fd, "Failed to retrieve history");
        return;
    }

    cJSON *resp = cJSON_CreateObject();
    cJSON_AddStringToObject(resp, "type", "HISTORY_DATA");
    cJSON *arr = cJSON_CreateArray();

    for (int i = 0; i < count; i++) {
        cJSON *item = cJSON_CreateObject();
        cJSON_AddStringToObject(item, "id", records[i].match_id);
        cJSON_AddStringToObject(item, "player1", records[i].player1);
        cJSON_AddStringToObject(item, "player2", records[i].player2);
        cJSON_AddStringToObject(item, "winner", records[i].winner);
        cJSON_AddStringToObject(item, "result", records[i].result);

        const char *user_res = "DRAW";
        if (strlen(records[i].winner) > 0) {
            if (strcmp(records[i].winner, client->username) == 0) {
                user_res = "WIN";
            } else {
                user_res = "LOSS";
            }
        } else if (strcmp(records[i].result, "ONGOING") == 0) {
            user_res = "ONGOING";
        }
        cJSON_AddStringToObject(item, "user_result", user_res);

        cJSON_AddNumberToObject(item, "player1_elo_before", records[i].p1_elo_before);
        cJSON_AddNumberToObject(item, "player2_elo_before", records[i].p2_elo_before);
        cJSON_AddNumberToObject(item, "player1_elo_after", records[i].p1_elo_after);
        cJSON_AddNumberToObject(item, "player2_elo_after", records[i].p2_elo_after);
        cJSON_AddStringToObject(item, "start_time", records[i].start_time);
        cJSON_AddStringToObject(item, "end_time", records[i].end_time);
        cJSON_AddItemToArray(arr, item);
    }

    cJSON_AddItemToObject(resp, "matches", arr);
    char *s = cJSON_PrintUnformatted(resp);
    cJSON_Delete(resp);
    db_free_history(records);

    if (s) {
        send_message(client->fd, s);
        free(s);
    }
}

static void handle_replay_msg(ClientInfo *client, cJSON *root) {
    cJSON *mid_item = cJSON_GetObjectItemCaseSensitive(root, "match_id");
    if (!cJSON_IsString(mid_item)) {
        send_error(client->fd, "Missing match_id for replay");
        return;
    }

    char *json_str = get_replay_json(mid_item->valuestring);
    if (!json_str) {
        send_error(client->fd, "Replay data not found");
        return;
    }

    send_message(client->fd, json_str);
    free(json_str);
}

void* client_thread_handler(void *arg) {
    ClientInfo *client = (ClientInfo *)arg;
    char line_buf[MSG_MAX];

    line_buffer_init(&client->line_buf);

    while (g_server.running && client->active) {
        int rc = recv_message(client->fd, &client->line_buf, line_buf, sizeof(line_buf));
        if (rc != 0) {
            /* Client disconnected or socket error */
            break;
        }

        /* Parse line as JSON */
        cJSON *root = cJSON_Parse(line_buf);
        if (!root) {
            send_error(client->fd, "Malformed JSON message");
            continue;
        }

        cJSON *type_item = cJSON_GetObjectItemCaseSensitive(root, "type");
        if (!cJSON_IsString(type_item)) {
            send_error(client->fd, "Missing or invalid 'type' field");
            cJSON_Delete(root);
            continue;
        }

        const char *type = type_item->valuestring;

        if (strcmp(type, "LOGIN") == 0) {
            handle_login(client, root);
        } else if (strcmp(type, "REGISTER") == 0) {
            handle_register(client, root);
        } else {
            /* All other messages require a valid session token */
            cJSON *token_item = cJSON_GetObjectItemCaseSensitive(root, "session_token");
            if (!cJSON_IsString(token_item)) {
                send_error(client->fd, "Missing session_token");
                cJSON_Delete(root);
                continue;
            }

            char validated_user[32];
            if (validate_session(token_item->valuestring, validated_user, sizeof(validated_user)) != 0 ||
                strcmp(validated_user, client->username) != 0) {
                send_error(client->fd, "Invalid or expired session");
                cJSON_Delete(root);
                continue;
            }

            if (strcmp(type, "LOGOUT") == 0) {
                handle_logout(client, token_item->valuestring);
            } else if (strcmp(type, "LIST_PLAYERS") == 0) {
                handle_list_players(client);
            } else if (strcmp(type, "FIND_MATCH") == 0) {
                handle_find_match(client);
            } else if (strcmp(type, "CANCEL_FIND_MATCH") == 0 || strcmp(type, "CANCEL_MATCHMAKING") == 0) {
                handle_cancel_find_match(client);
            } else if (strcmp(type, "CHALLENGE") == 0) {
                handle_challenge(client, root);
            } else if (strcmp(type, "CHALLENGE_REPLY") == 0) {
                handle_challenge_reply(client, root);
            } else if (strcmp(type, "PLACE_SHIP") == 0) {
                handle_place_ship_msg(client, root);
            } else if (strcmp(type, "READY") == 0) {
                handle_ready_msg(client, root);
            } else if (strcmp(type, "FIRE") == 0) {
                handle_fire_msg(client, root);
            } else if (strcmp(type, "SURRENDER") == 0) {
                handle_surrender_msg(client, root);
            } else if (strcmp(type, "DRAW_OFFER") == 0) {
                handle_draw_offer_msg(client, root);
            } else if (strcmp(type, "DRAW_REPLY") == 0) {
                handle_draw_reply_msg(client, root);
            } else if (strcmp(type, "HISTORY") == 0) {
                handle_history_msg(client, root);
            } else if (strcmp(type, "REPLAY") == 0) {
                handle_replay_msg(client, root);
            } else {
                send_error(client->fd, "Unknown message type");
            }
        }

        cJSON_Delete(root);
    }

    handle_client_disconnect(client);
    return NULL;
}
