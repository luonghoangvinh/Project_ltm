#ifndef SESSION_H
#define SESSION_H

#include "common.h"
#include <stddef.h>

typedef struct Session {
    char token[64];
    char username[USERNAME_MAX_LEN + 1];
    time_t created_at;
    time_t last_activity;
    struct Session *next;
} Session;

void session_init(void);
int create_session(const char *username, char *out_token, size_t maxlen);
int validate_session(const char *token, char *out_username, size_t maxlen);
int destroy_session(const char *token);
int destroy_session_by_username(const char *username);
const char* get_username_by_token(const char *token);
void session_cleanup(void);

#endif /* SESSION_H */
