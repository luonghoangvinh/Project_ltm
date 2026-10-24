#include "session.h"
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>

static Session *g_sessions_head = NULL;
static pthread_mutex_t g_sessions_mutex = PTHREAD_MUTEX_INITIALIZER;

static void generate_random_token(char *token, size_t size) {
    if (size < 33) return;

    unsigned char bytes[16];
    int fd = open("/dev/urandom", O_RDONLY);
    int read_ok = 0;
    if (fd >= 0) {
        if (read(fd, bytes, sizeof(bytes)) == (ssize_t)sizeof(bytes)) {
            read_ok = 1;
        }
        close(fd);
    }

    if (!read_ok) {
        for (size_t i = 0; i < sizeof(bytes); i++) {
            bytes[i] = (unsigned char)(rand() % 256);
        }
    }

    for (int i = 0; i < 16; i++) {
        sprintf(token + (i * 2), "%02x", bytes[i]);
    }
    token[32] = '\0';
}

void session_init(void) {
    pthread_mutex_lock(&g_sessions_mutex);
    g_sessions_head = NULL;
    pthread_mutex_unlock(&g_sessions_mutex);
}

int create_session(const char *username, char *out_token, size_t maxlen) {
    if (!username || !out_token || maxlen < 33) return -1;

    pthread_mutex_lock(&g_sessions_mutex);

    /* Enforce 1 session per user: remove any existing session for this user */
    Session **curr = &g_sessions_head;
    while (*curr) {
        if (strcmp((*curr)->username, username) == 0) {
            Session *to_free = *curr;
            *curr = (*curr)->next;
            free(to_free);
        } else {
            curr = &(*curr)->next;
        }
    }

    Session *new_sess = (Session *)malloc(sizeof(Session));
    if (!new_sess) {
        pthread_mutex_unlock(&g_sessions_mutex);
        return -1;
    }

    generate_random_token(new_sess->token, sizeof(new_sess->token));
    strncpy(new_sess->username, username, sizeof(new_sess->username) - 1);
    new_sess->username[sizeof(new_sess->username) - 1] = '\0';
    new_sess->created_at = time(NULL);
    new_sess->last_activity = new_sess->created_at;

    new_sess->next = g_sessions_head;
    g_sessions_head = new_sess;

    strncpy(out_token, new_sess->token, maxlen - 1);
    out_token[maxlen - 1] = '\0';

    pthread_mutex_unlock(&g_sessions_mutex);
    return 0;
}

int validate_session(const char *token, char *out_username, size_t maxlen) {
    if (!token) return -1;

    pthread_mutex_lock(&g_sessions_mutex);
    Session *curr = g_sessions_head;
    while (curr) {
        if (strcmp(curr->token, token) == 0) {
            curr->last_activity = time(NULL);
            if (out_username && maxlen > 0) {
                strncpy(out_username, curr->username, maxlen - 1);
                out_username[maxlen - 1] = '\0';
            }
            pthread_mutex_unlock(&g_sessions_mutex);
            return 0;
        }
        curr = curr->next;
    }

    pthread_mutex_unlock(&g_sessions_mutex);
    return -1;
}

int destroy_session(const char *token) {
    if (!token) return -1;

    pthread_mutex_lock(&g_sessions_mutex);
    Session **curr = &g_sessions_head;
    while (*curr) {
        if (strcmp((*curr)->token, token) == 0) {
            Session *to_free = *curr;
            *curr = (*curr)->next;
            free(to_free);
            pthread_mutex_unlock(&g_sessions_mutex);
            return 0;
        }
        curr = &(*curr)->next;
    }

    pthread_mutex_unlock(&g_sessions_mutex);
    return -1;
}

int destroy_session_by_username(const char *username) {
    if (!username) return -1;

    pthread_mutex_lock(&g_sessions_mutex);
    Session **curr = &g_sessions_head;
    int count = 0;
    while (*curr) {
        if (strcmp((*curr)->username, username) == 0) {
            Session *to_free = *curr;
            *curr = (*curr)->next;
            free(to_free);
            count++;
        } else {
            curr = &(*curr)->next;
        }
    }

    pthread_mutex_unlock(&g_sessions_mutex);
    return count > 0 ? 0 : -1;
}

const char* get_username_by_token(const char *token) {
    static __thread char thread_user_buf[32];
    if (validate_session(token, thread_user_buf, sizeof(thread_user_buf)) == 0) {
        return thread_user_buf;
    }
    return NULL;
}

void session_cleanup(void) {
    pthread_mutex_lock(&g_sessions_mutex);
    Session *curr = g_sessions_head;
    while (curr) {
        Session *next = curr->next;
        free(curr);
        curr = next;
    }
    g_sessions_head = NULL;
    pthread_mutex_unlock(&g_sessions_mutex);
}
