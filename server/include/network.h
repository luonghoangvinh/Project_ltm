#ifndef NETWORK_H
#define NETWORK_H

#include "common.h"
#include "protocol.h"
#include <netinet/in.h>
#include <arpa/inet.h>

typedef struct {
    int fd;
    char ip[INET_ADDRSTRLEN];
    int port;
    pthread_t thread;
    int active;
    char session_token[64];
    char username[32];
    int status;
    char current_match_id[64];
    LineBuffer line_buf;
} ClientInfo;

typedef struct {
    int server_fd;
    int port;
    volatile int running;
    char db_path[256];
    ClientInfo clients[MAX_CLIENTS];
    pthread_mutex_t clients_mutex;
} ServerContext;

extern ServerContext g_server;

int server_init(int port, const char *db_path);
int server_run(void);
void server_stop(void);

void broadcast_player_update(void);
void broadcast_to_all(const char *json_str);

ClientInfo* find_client_by_username(const char *username);
ClientInfo* find_client_by_fd(int fd);
ClientInfo* find_client_by_token(const char *token);
void set_client_status(const char *username, int status);

void* client_thread_handler(void *arg);

#endif /* NETWORK_H */
