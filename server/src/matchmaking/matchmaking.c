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

/* Hàng chờ tìm trận ngẫu nhiên */
static QueuePlayer *g_queue_head = NULL;
static pthread_mutex_t g_queue_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_t g_mm_thread;
static volatile int g_mm_running = 0;

static void* matchmaking_worker(void *arg) {
    (void)arg;
    while (g_mm_running) {
        sleep(1);
        if (g_mm_running) {
            matchmaking_process_queue();
        }
    }
    return NULL;
}

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

    pthread_mutex_lock(&g_queue_mutex);
    g_queue_head = NULL;
    pthread_mutex_unlock(&g_queue_mutex);

    g_mm_running = 1;
    pthread_create(&g_mm_thread, NULL, matchmaking_worker, NULL);
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

    if (target_client->status == STATUS_MATCHMAKING) {
        if (err_msg) snprintf(err_msg, err_size, "Player '%s' is currently finding a match", target);
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
    matchmaking_queue_remove(challenger);
    matchmaking_queue_remove(replying_user);
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

/* === HÀNG CHỜ TÌM TRẬN NGẪU NHIÊN === */

/* Hàm nội bộ xóa người chơi khỏi hàng chờ (đã giữ lock g_queue_mutex) */
static void queue_remove_internal(const char *username) {
    if (!username) return;
    QueuePlayer **curr = &g_queue_head;
    while (*curr) {
        if (strcmp((*curr)->username, username) == 0) {
            QueuePlayer *temp = *curr;
            *curr = (*curr)->next;
            free(temp);
            return;
        }
        curr = &(*curr)->next;
    }
}

/* Xóa người chơi khỏi hàng chờ */
int matchmaking_queue_remove(const char *username) {
    if (!username) return -1;
    pthread_mutex_lock(&g_queue_mutex);
    queue_remove_internal(username);
    pthread_mutex_unlock(&g_queue_mutex);
    return 0;
}

/* Kiểm tra người chơi có trong hàng chờ không */
int matchmaking_is_queued(const char *username) {
    if (!username) return 0;
    int found = 0;
    pthread_mutex_lock(&g_queue_mutex);
    QueuePlayer *curr = g_queue_head;
    while (curr) {
        if (strcmp(curr->username, username) == 0) {
            found = 1;
            break;
        }
        curr = curr->next;
    }
    pthread_mutex_unlock(&g_queue_mutex);
    return found;
}

/* Thêm người chơi vào hàng chờ tìm trận */
int matchmaking_queue_add(const char *username) {
    if (!username || strlen(username) == 0) return -1;

    pthread_mutex_lock(&g_queue_mutex);
    // Tránh thêm trùng lặp
    QueuePlayer *curr = g_queue_head;
    while (curr) {
        if (strcmp(curr->username, username) == 0) {
            pthread_mutex_unlock(&g_queue_mutex);
            return 1; // Đã có trong hàng chờ
        }
        curr = curr->next;
    }

    int elo = 1200;
    db_get_user_elo(username, &elo);

    QueuePlayer *node = (QueuePlayer *)malloc(sizeof(QueuePlayer));
    if (!node) {
        pthread_mutex_unlock(&g_queue_mutex);
        return -1;
    }

    strncpy(node->username, username, sizeof(node->username) - 1);
    node->username[sizeof(node->username) - 1] = '\0';
    node->elo = elo;
    node->joined_at = time(NULL);
    node->next = NULL;

    // Chèn vào cuối danh sách hàng chờ
    if (!g_queue_head) {
        g_queue_head = node;
    } else {
        QueuePlayer *tail = g_queue_head;
        while (tail->next) {
            tail = tail->next;
        }
        tail->next = node;
    }
    pthread_mutex_unlock(&g_queue_mutex);

    // Kích hoạt ghép trận ngay nếu có đối thủ phù hợp đang chờ sẵn
    matchmaking_process_queue();
    return 0;
}

/* Xử lý ghép cặp người chơi trong hàng chờ */
void matchmaking_process_queue(void) {
    while (1) {
        char matched_user1[32] = {0};
        char matched_user2[32] = {0};
        int elo1 = 1200, elo2 = 1200;
        int found_pair = 0;

        pthread_mutex_lock(&g_queue_mutex);

        // 1. Loại bỏ các client không còn online hoặc đã vào trận
        QueuePlayer **cleanup_ptr = &g_queue_head;
        while (*cleanup_ptr) {
            ClientInfo *c = find_client_by_username((*cleanup_ptr)->username);
            if (!c || !c->active || c->status == STATUS_IN_GAME) {
                QueuePlayer *to_free = *cleanup_ptr;
                *cleanup_ptr = (*cleanup_ptr)->next;
                free(to_free);
            } else {
                cleanup_ptr = &(*cleanup_ptr)->next;
            }
        }

        // 2. Duyệt tìm cặp đấu có ELO gần nhau nhất
        time_t now = time(NULL);
        QueuePlayer *p1 = g_queue_head;
        int best_diff = 999999;

        while (p1 && !found_pair) {
            int wait1 = (int)(now - p1->joined_at);
            if (wait1 < 0) wait1 = 0;

            QueuePlayer *p2 = p1->next;
            QueuePlayer *best_opponent = NULL;

            while (p2) {
                // Không tự ghép với chính mình
                if (strcmp(p1->username, p2->username) != 0) {
                    int diff = abs(p1->elo - p2->elo);
                    int wait2 = (int)(now - p2->joined_at);
                    if (wait2 < 0) wait2 = 0;

                    // Mở rộng khoảng ELO khi chờ lâu: cơ bản 100, mỗi 10s chờ tăng thêm 50 ELO
                    int max_wait = wait1 > wait2 ? wait1 : wait2;
                    int allowed_diff = 100 + (max_wait / 10) * 50;

                    if (diff <= allowed_diff && diff < best_diff) {
                        best_diff = diff;
                        best_opponent = p2;
                    }
                }
                p2 = p2->next;
            }

            if (best_opponent) {
                // Tìm thấy cặp ghép phù hợp
                strncpy(matched_user1, p1->username, sizeof(matched_user1));
                matched_user1[sizeof(matched_user1) - 1] = '\0';
                strncpy(matched_user2, best_opponent->username, sizeof(matched_user2));
                matched_user2[sizeof(matched_user2) - 1] = '\0';
                elo1 = p1->elo;
                elo2 = best_opponent->elo;
                found_pair = 1;

                // Xóa cả 2 người khỏi hàng chờ
                queue_remove_internal(matched_user1);
                queue_remove_internal(matched_user2);
                break;
            }

            p1 = p1->next;
        }

        pthread_mutex_unlock(&g_queue_mutex);

        // Nếu không có cặp nào ghép được thì dừng
        if (!found_pair) {
            break;
        }

        // 3. Tạo trận đấu cho 2 người chơi
        ClientInfo *client1 = find_client_by_username(matched_user1);
        ClientInfo *client2 = find_client_by_username(matched_user2);

        if (!client1 || !client1->active || !client2 || !client2->active) {
            if (client1 && client1->active) set_client_status(matched_user1, STATUS_IN_LOBBY);
            if (client2 && client2->active) set_client_status(matched_user2, STATUS_IN_LOBBY);
            broadcast_player_update();
            continue;
        }

        char match_id[64];
        generate_uuid(match_id, sizeof(match_id));

        Game *game = create_game(match_id, matched_user1, client1->fd, elo1,
                                 matched_user2, client2->fd, elo2);
        if (!game) {
            fprintf(stderr, "[ERROR] Khong the tao game cho matchmaking: %s vs %s\n",
                    matched_user1, matched_user2);
            set_client_status(matched_user1, STATUS_IN_LOBBY);
            set_client_status(matched_user2, STATUS_IN_LOBBY);
            broadcast_player_update();
            continue;
        }

        set_client_status(matched_user1, STATUS_IN_GAME);
        set_client_status(matched_user2, STATUS_IN_GAME);
        strncpy(client1->current_match_id, match_id, sizeof(client1->current_match_id));
        client1->current_match_id[sizeof(client1->current_match_id) - 1] = '\0';
        strncpy(client2->current_match_id, match_id, sizeof(client2->current_match_id));
        client2->current_match_id[sizeof(client2->current_match_id) - 1] = '\0';

        printf("[INFO] Matchmaking ghep tran thanh cong: %s (%d) vs %s (%d)\n",
               matched_user1, elo1, matched_user2, elo2);

        // Gửi thông báo MATCH_FOUND cho người chơi 1
        cJSON *mf1 = cJSON_CreateObject();
        cJSON_AddStringToObject(mf1, "type", "MATCH_FOUND");
        cJSON_AddStringToObject(mf1, "match_id", match_id);
        cJSON_AddStringToObject(mf1, "opponent", matched_user2);
        cJSON_AddNumberToObject(mf1, "opponent_elo", elo2);
        cJSON_AddBoolToObject(mf1, "you_go_first", (game->current_turn == 1));
        char *str1 = cJSON_PrintUnformatted(mf1);
        cJSON_Delete(mf1);

        // Gửi thông báo MATCH_FOUND cho người chơi 2
        cJSON *mf2 = cJSON_CreateObject();
        cJSON_AddStringToObject(mf2, "type", "MATCH_FOUND");
        cJSON_AddStringToObject(mf2, "match_id", match_id);
        cJSON_AddStringToObject(mf2, "opponent", matched_user1);
        cJSON_AddNumberToObject(mf2, "opponent_elo", elo1);
        cJSON_AddBoolToObject(mf2, "you_go_first", (game->current_turn == 2));
        char *str2 = cJSON_PrintUnformatted(mf2);
        cJSON_Delete(mf2);

        if (str1) {
            send_message(client1->fd, str1);
            free(str1);
        }
        if (str2) {
            send_message(client2->fd, str2);
            free(str2);
        }

        broadcast_player_update();
    }
}

void matchmaking_cleanup(void) {
    g_mm_running = 0;
    pthread_join(g_mm_thread, NULL);

    pthread_mutex_lock(&g_challenges_mutex);
    PendingChallenge *curr = g_challenges_head;
    while (curr) {
        PendingChallenge *next = curr->next;
        free(curr);
        curr = next;
    }
    g_challenges_head = NULL;
    pthread_mutex_unlock(&g_challenges_mutex);

    pthread_mutex_lock(&g_queue_mutex);
    QueuePlayer *qcurr = g_queue_head;
    while (qcurr) {
        QueuePlayer *qnext = qcurr->next;
        free(qcurr);
        qcurr = qnext;
    }
    g_queue_head = NULL;
    pthread_mutex_unlock(&g_queue_mutex);
}
