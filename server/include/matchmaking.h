#ifndef MATCHMAKING_H
#define MATCHMAKING_H

#include "common.h"
#include <stddef.h>

#define CHALLENGE_TIMEOUT_SEC 60

typedef struct PendingChallenge {
    char match_id[64];
    char challenger[32];
    char challenged[32];
    time_t created_at;
    struct PendingChallenge *next;
} PendingChallenge;

void matchmaking_init(void);

/**
 * Challenger sends challenge to target.
 * Creates a pending challenge and sends {type: "CHALLENGE", from: challenger, match_id: match_id} to target.
 * Returns 0 on success, -1 on failure.
 */
int challenge_player(const char *challenger, const char *target, char *out_match_id, size_t match_id_size, char *err_msg, size_t err_size);

/**
 * Challenged user replies to challenge.
 * accept = 1 to accept, 0 to decline.
 * If accepted, creates a Game instance, puts both in PLACING state, sends MATCH_FOUND to both.
 * If declined, sends CHALLENGE_DECLINED to challenger.
 * Returns 0 on success, -1 on failure.
 */
int reply_challenge(const char *replying_user, const char *match_id, int accept, char *err_msg, size_t err_size);

void cancel_challenges_for_user(const char *username);

/* === RANDOM MATCHMAKING QUEUE (TÌM TRẬN NGẪU NHIÊN) === */
typedef struct QueuePlayer {
    char username[32];
    int elo;
    time_t joined_at;
    struct QueuePlayer *next;
} QueuePlayer;

/* Thêm người chơi vào hàng chờ tìm trận */
int matchmaking_queue_add(const char *username);

/* Xóa người chơi khỏi hàng chờ tìm trận */
int matchmaking_queue_remove(const char *username);

/* Kiểm tra người chơi có đang trong hàng chờ tìm trận không */
int matchmaking_is_queued(const char *username);

/* Xử lý ghép cặp người chơi trong hàng chờ */
void matchmaking_process_queue(void);

void matchmaking_cleanup(void);

#endif /* MATCHMAKING_H */
