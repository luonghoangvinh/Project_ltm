#include "game.h"
#include "database.h"
#include "cjson/cJSON.h"
#include <stdlib.h>
#include <string.h>

char* get_replay_json(const char *match_id) {
    if (!match_id) return NULL;

    MoveRecord *moves = NULL;
    int count = 0;
    if (db_get_replay_moves(match_id, &moves, &count) != 0) {
        return NULL;
    }

    /* Fetch match metadata for player names, winner, and ship data */
    MatchRecord match_rec;
    int has_match = (db_get_match_by_id(match_id, &match_rec) == 0);

    cJSON *root = cJSON_CreateObject();
    if (!root) {
        db_free_replay(moves);
        return NULL;
    }

    cJSON_AddStringToObject(root, "type", "REPLAY_DATA");
    cJSON_AddStringToObject(root, "match_id", match_id);

    /* Add match metadata */
    if (has_match) {
        cJSON_AddStringToObject(root, "player1", match_rec.player1);
        cJSON_AddStringToObject(root, "player2", match_rec.player2);
        cJSON_AddStringToObject(root, "winner", match_rec.winner);
        cJSON_AddStringToObject(root, "result", match_rec.result);

        /* Add ship placement data as raw JSON strings (they are already JSON arrays) */
        if (strlen(match_rec.player1_ships) > 0) {
            cJSON *p1_ships = cJSON_Parse(match_rec.player1_ships);
            if (p1_ships) {
                cJSON_AddItemToObject(root, "player1_ships", p1_ships);
            }
        }
        if (strlen(match_rec.player2_ships) > 0) {
            cJSON *p2_ships = cJSON_Parse(match_rec.player2_ships);
            if (p2_ships) {
                cJSON_AddItemToObject(root, "player2_ships", p2_ships);
            }
        }
    }

    cJSON *arr = cJSON_CreateArray();
    if (arr) {
        for (int i = 0; i < count; i++) {
            cJSON *move_obj = cJSON_CreateObject();
            if (move_obj) {
                cJSON_AddNumberToObject(move_obj, "id", moves[i].id);
                cJSON_AddStringToObject(move_obj, "match_id", moves[i].match_id);
                cJSON_AddStringToObject(move_obj, "player", moves[i].player);
                cJSON_AddNumberToObject(move_obj, "row", moves[i].row);
                cJSON_AddNumberToObject(move_obj, "col", moves[i].col);
                cJSON_AddStringToObject(move_obj, "result", moves[i].result);
                cJSON_AddBoolToObject(move_obj, "sunk", moves[i].sunk ? 1 : 0);
                cJSON_AddNumberToObject(move_obj, "ship_size", moves[i].ship_size);
                cJSON_AddNumberToObject(move_obj, "move_num", moves[i].move_num);
                cJSON_AddStringToObject(move_obj, "created_at", moves[i].created_at);
                cJSON_AddItemToArray(arr, move_obj);
            }
        }
        cJSON_AddItemToObject(root, "moves", arr);
    }

    char *json_str = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    db_free_replay(moves);

    return json_str;
}
