#ifndef COMMON_H
#define COMMON_H

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <time.h>
#include <pthread.h>
#include <unistd.h>
#include <errno.h>

#define MAX_CLIENTS 100
#define BOARD_SIZE 10
#define MSG_MAX 65536
#define PORT_DEFAULT 8888
#define NUM_SHIPS 5

#define USERNAME_MIN_LEN 3
#define USERNAME_MAX_LEN 20
#define PASSWORD_MIN_LEN 6
#define SESSION_TOKEN_LEN 32
#define MATCH_ID_LEN 36

/* Ship sizes array: {2, 3, 3, 4, 5} */
extern const int DEFAULT_SHIP_SIZES[NUM_SHIPS];

/* Ship names */
extern const char *SHIP_NAMES[NUM_SHIPS];

/* Game states */
typedef enum {
    GAME_STATE_WAITING = 0,
    GAME_STATE_PLACING,
    GAME_STATE_PLAYING,
    GAME_STATE_FINISHED
} GameState;

/* Client lobby statuses */
typedef enum {
    STATUS_OFFLINE = 0,
    STATUS_ONLINE,
    STATUS_IN_LOBBY,
    STATUS_IN_GAME
} ClientStatus;

/* Cell types */
typedef enum {
    CELL_EMPTY = 0,
    CELL_SHIP,
    CELL_HIT,
    CELL_MISS
} CellType;

/* Placement directions */
typedef enum {
    DIR_HORIZONTAL = 0,
    DIR_VERTICAL = 1
} Direction;

#endif /* COMMON_H */
