#include "matchmaking.h"
#include "game.h"
#include "network.h"
#include "protocol.h"
#include "database.h"
#include "cjson/cJSON.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <fcntl.h>
#include <unistd.h>

static PendingChallenge *g_challenges_head = NULL;
static pthread_mutex_t g_challenges_mutex = PTHREAD_MUTEX_INITIALIZER;

static void generate_uuid(char *out_uuid, size_t size) {
    if (size < 37) return;

    unsigned char b[16];
    int fd = open("/dev/urandom", O_RDONLY);
    int ok = 0;
    if (fd >= 0) {
        if (read(fd, b, sizeof(b)) == (ssize_t)sizeof(b)) {
            ok = 1;
        }
        close(fd);
    }
    if (!ok) {
        for (int i = 0; i < 16; i++) {
            b[i] = (unsigned char)(rand() % 256);
        }
    }

    /* Set version to 4 (0100) and variant to RFC 4122 (10xx) */
    b[6] = (b[6] & 0x0F) | 0x40;
    b[8] = (b[8] & 0x3F) | 0x80;

    snprintf(out_uuid, size,
             "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
             b[0], b[1], b[2], b[3],
             b[4], b[5],
             b[6], b[7],
             b[8], b[9],
             b[10], b[11], b[12], b[13], b[14], b[15]);
}

void matchmaking_init(void) {
    pthread_mutex_lock(&g_challenges_mutex);
    g_challenges_head = NULL;
    pthread_mutex_unlock(&g_challenges_mutex);
}

int challenge_player(const char *challenger, const char *target, char *out_match_id, size_t match_id_size, char *err_msg, size_t err_size) {
    if (!challenger || !target) {
        if (err_msg) snprintf(err_msg, err_size, "Invalid challenger or target");
        return -1;
    }

    if (strcmp(challenger, target) == 0) {
        if (err_msg) snprintf(err_msg, err_size, "Cannot challenge yourself");
        return -1;
    }

    ClientInfo *target_client = find_client_by_username(target);
    if (!target_client || !target_client->active) {
        if (err_msg) snprintf(err_msg, err_size, "Player '%s' is not online", target);
        return -1;
    }

    if (target_client->status == STATUS_IN_GAME) {
        if (err_msg) snprintf(err_msg, err_size, "Player '%s' is currently in a game", target);
        return -1;
    }

    char match_id[64];
    generate_uuid(match_id, sizeof(match_id));

    PendingChallenge *pc = (PendingChallenge *)malloc(sizeof(PendingChallenge));
    if (!pc) {
        if (err_msg) snprintf(err_msg, err_size, "Memory allocation error");
        return -1;
    }

    strncpy(pc->match_id, match_id, sizeof(pc->match_id) - 1);
    pc->match_id[sizeof(pc->match_id) - 1] = '\0';
    strncpy(pc->challenger, challenger, sizeof(pc->challenger) - 1);
    pc->challenger[sizeof(pc->challenger) - 1] = '\0';
    strncpy(pc->challenged, target, sizeof(pc->challenged) - 1);
    pc->challenged[sizeof(pc->challenged) - 1] = '\0';
    pc->created_at = time(NULL);

    pthread_mutex_lock(&g_challenges_mutex);
    pc->next = g_challenges_head;
    g_challenges_head = pc;
    pthread_mutex_unlock(&g_challenges_mutex);

    if (out_match_id && match_id_size > 0) {
        strncpy(out_match_id, match_id, match_id_size - 1);
        out_match_id[match_id_size - 1] = '\0';
    }

    /* Send CHALLENGE notice to target player */
    cJSON *notice = cJSON_CreateObject();
    cJSON_AddStringToObject(notice, "type", "CHALLENGE");
    cJSON_AddStringToObject(notice, "from", challenger);
    cJSON_AddStringToObject(notice, "match_id", match_id);
    char *notice_str = cJSON_PrintUnformatted(notice);
    cJSON_Delete(notice);

    if (notice_str) {
        send_message(target_client->fd, notice_str);
        free(notice_str);
    }

    return 0;
}

int reply_challenge(const char *replying_user, const char *match_id, int accept, char *err_msg, size_t err_size) {
    if (!replying_user || !match_id) {
        if (err_msg) snprintf(err_msg, err_size, "Invalid arguments");
        return -1;
    }

    pthread_mutex_lock(&g_challenges_mutex);
    PendingChallenge **curr = &g_challenges_head;
    PendingChallenge *target_challenge = NULL;
    while (*curr) {
        if (strcmp((*curr)->match_id, match_id) == 0) {
            target_challenge = *curr;
            *curr = (*curr)->next;
            break;
        }
        curr = &(*curr)->next;
    }
    pthread_mutex_unlock(&g_challenges_mutex);

    if (!target_challenge) {
        if (err_msg) snprintf(err_msg, err_size, "Challenge not found or already handled");
        return -1;
    }

    if (strcmp(target_challenge->challenged, replying_user) != 0) {
        if (err_msg) snprintf(err_msg, err_size, "You are not the recipient of this challenge");
        free(target_challenge);
        return -1;
    }

    char challenger[32];
    strncpy(challenger, target_challenge->challenger, sizeof(challenger) - 1);
    challenger[sizeof(challenger) - 1] = '\0';
    free(target_challenge);

    ClientInfo *challenger_client = find_client_by_username(challenger);
    ClientInfo *challenged_client = find_client_by_username(replying_user);

    if (!accept) {
        /* Notify challenger of decline */
        if (challenger_client && challenger_client->active) {
            cJSON *decline = cJSON_CreateObject();
            cJSON_AddStringToObject(decline, "type", "CHALLENGE_DECLINED");
            cJSON_AddStringToObject(decline, "match_id", match_id);
            cJSON_AddStringToObject(decline, "opponent", replying_user);
            char *dec_str = cJSON_PrintUnformatted(decline);
            cJSON_Delete(decline);

            if (dec_str) {
                send_message(challenger_client->fd, dec_str);
                free(dec_str);
            }
        }
        return 0;
    }

    /* Accepted: check both clients still active */
    if (!challenger_client || !challenger_client->active) {
        if (err_msg) snprintf(err_msg, err_size, "Challenger is no longer connected");
        return -1;
    }

    if (!challenged_client || !challenged_client->active) {
        if (err_msg) snprintf(err_msg, err_size, "Client connection lost");
        return -1;
    }

    int elo_challenger = 1200;
    int elo_challenged = 1200;
    db_get_user_elo(challenger, &elo_challenger);
    db_get_user_elo(replying_user, &elo_challenged);

    Game *game = create_game(match_id, challenger, challenger_client->fd, elo_challenger,
                             replying_user, challenged_client->fd, elo_challenged);
    if (!game) {
        if (err_msg) snprintf(err_msg, err_size, "Failed to initialize game session");
        return -1;
    }

    set_client_status(challenger, STATUS_IN_GAME);
    set_client_status(replying_user, STATUS_IN_GAME);
    strncpy(challenger_client->current_match_id, match_id, sizeof(challenger_client->current_match_id) - 1);
    strncpy(challenged_client->current_match_id, match_id, sizeof(challenged_client->current_match_id) - 1);

    /* Send MATCH_FOUND to challenger */
    cJSON *mf1 = cJSON_CreateObject();
    cJSON_AddStringToObject(mf1, "type", "MATCH_FOUND");
    cJSON_AddStringToObject(mf1, "match_id", match_id);
    cJSON_AddStringToObject(mf1, "opponent", replying_user);
    cJSON_AddNumberToObject(mf1, "opponent_elo", elo_challenged);
    cJSON_AddBoolToObject(mf1, "you_go_first", (game->current_turn == 1));
    char *str1 = cJSON_PrintUnformatted(mf1);
    cJSON_Delete(mf1);

    /* Send MATCH_FOUND to challenged */
    cJSON *mf2 = cJSON_CreateObject();
    cJSON_AddStringToObject(mf2, "type", "MATCH_FOUND");
    cJSON_AddStringToObject(mf2, "match_id", match_id);
    cJSON_AddStringToObject(mf2, "opponent", challenger);
    cJSON_AddNumberToObject(mf2, "opponent_elo", elo_challenger);
    cJSON_AddBoolToObject(mf2, "you_go_first", (game->current_turn == 2));
    char *str2 = cJSON_PrintUnformatted(mf2);
    cJSON_Delete(mf2);

    if (str1) {
        send_message(challenger_client->fd, str1);
        free(str1);
    }
    if (str2) {
        send_message(challenged_client->fd, str2);
        free(str2);
    }

    broadcast_player_update();
    return 0;
}

void cancel_challenges_for_user(const char *username) {
    if (!username) return;

    pthread_mutex_lock(&g_challenges_mutex);
    PendingChallenge **curr = &g_challenges_head;
    while (*curr) {
        if (strcmp((*curr)->challenger, username) == 0 ||
            strcmp((*curr)->challenged, username) == 0) {
            PendingChallenge *to_free = *curr;
            *curr = (*curr)->next;
            free(to_free);
        } else {
            curr = &(*curr)->next;
        }
    }
    pthread_mutex_unlock(&g_challenges_mutex);
}

void matchmaking_cleanup(void) {
    pthread_mutex_lock(&g_challenges_mutex);
    PendingChallenge *curr = g_challenges_head;
    while (curr) {
        PendingChallenge *next = curr->next;
        free(curr);
        curr = next;
    }
    g_challenges_head = NULL;
    pthread_mutex_unlock(&g_challenges_mutex);
}
