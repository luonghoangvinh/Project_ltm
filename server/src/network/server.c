#include "network.h"
#include "protocol.h"
#include "database.h"
#include "cjson/cJSON.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <signal.h>

ServerContext g_server;

int server_init(int port, const char *db_path) {
    memset(&g_server, 0, sizeof(ServerContext));
    g_server.port = port;
    g_server.running = 1;
    strncpy(g_server.db_path, db_path ? db_path : "battleship.db", sizeof(g_server.db_path) - 1);

    pthread_mutex_init(&g_server.clients_mutex, NULL);

    for (int i = 0; i < MAX_CLIENTS; i++) {
        g_server.clients[i].fd = -1;
        g_server.clients[i].active = 0;
        g_server.clients[i].status = STATUS_OFFLINE;
        g_server.clients[i].username[0] = '\0';
        g_server.clients[i].session_token[0] = '\0';
        g_server.clients[i].current_match_id[0] = '\0';
    }

    g_server.server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (g_server.server_fd < 0) {
        perror("[ERROR] socket creation failed");
        return -1;
    }

    int opt = 1;
    if (setsockopt(g_server.server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0) {
        perror("[WARN] setsockopt SO_REUSEADDR failed");
    }

    struct sockaddr_in serv_addr;
    memset(&serv_addr, 0, sizeof(serv_addr));
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_addr.s_addr = htonl(INADDR_ANY);
    serv_addr.sin_port = htons(port);

    if (bind(g_server.server_fd, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) < 0) {
        perror("[ERROR] socket bind failed");
        close(g_server.server_fd);
        g_server.server_fd = -1;
        return -1;
    }

    if (listen(g_server.server_fd, 50) < 0) {
        perror("[ERROR] socket listen failed");
        close(g_server.server_fd);
        g_server.server_fd = -1;
        return -1;
    }

    printf("[INFO] Battleship server listening on port %d...\n", port);
    return 0;
}

int server_run(void) {
    while (g_server.running) {
        struct sockaddr_in cli_addr;
        socklen_t addr_len = sizeof(cli_addr);
        int client_fd = accept(g_server.server_fd, (struct sockaddr *)&cli_addr, &addr_len);

        if (client_fd < 0) {
            if (!g_server.running) break;
            if (errno == EINTR) continue;
            perror("[WARN] accept failed");
            continue;
        }

        pthread_mutex_lock(&g_server.clients_mutex);

        /* Find an empty slot */
        int slot = -1;
        for (int i = 0; i < MAX_CLIENTS; i++) {
            if (!g_server.clients[i].active) {
                slot = i;
                break;
            }
        }

        if (slot == -1) {
            pthread_mutex_unlock(&g_server.clients_mutex);
            printf("[WARN] Server full (maximum %d clients reached)\n", MAX_CLIENTS);
            send_error(client_fd, "Server is currently at maximum capacity");
            close(client_fd);
            continue;
        }

        ClientInfo *c = &g_server.clients[slot];
        c->fd = client_fd;
        inet_ntop(AF_INET, &cli_addr.sin_addr, c->ip, sizeof(c->ip));
        c->port = ntohs(cli_addr.sin_port);
        c->active = 1;
        c->status = STATUS_ONLINE;
        c->username[0] = '\0';
        c->session_token[0] = '\0';
        c->current_match_id[0] = '\0';

        pthread_attr_t attr;
        pthread_attr_init(&attr);
        pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_DETACHED);

        if (pthread_create(&c->thread, &attr, client_thread_handler, c) != 0) {
            perror("[ERROR] Failed to create client thread");
            c->active = 0;
            c->fd = -1;
            close(client_fd);
        } else {
            printf("[INFO] New client connected from %s:%d (slot=%d, fd=%d)\n",
                   c->ip, c->port, slot, client_fd);
        }

        pthread_attr_destroy(&attr);
        pthread_mutex_unlock(&g_server.clients_mutex);
    }

    return 0;
}

void broadcast_to_all(const char *json_str) {
    if (!json_str) return;

    pthread_mutex_lock(&g_server.clients_mutex);
    for (int i = 0; i < MAX_CLIENTS; i++) {
        if (g_server.clients[i].active && g_server.clients[i].fd > 0) {
            send_message(g_server.clients[i].fd, json_str);
        }
    }
    pthread_mutex_unlock(&g_server.clients_mutex);
}

void broadcast_player_update(void) {
    cJSON *resp = cJSON_CreateObject();
    if (!resp) return;

    cJSON_AddStringToObject(resp, "type", "PLAYER_UPDATE");
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

            cJSON_AddStringToObject(p, "status", st);
            cJSON_AddItemToArray(arr, p);
        }
    }

    cJSON_AddItemToObject(resp, "players", arr);
    char *s = cJSON_PrintUnformatted(resp);
    cJSON_Delete(resp);

    if (s) {
        for (int i = 0; i < MAX_CLIENTS; i++) {
            if (g_server.clients[i].active && g_server.clients[i].fd > 0 &&
                strlen(g_server.clients[i].username) > 0) {
                send_message(g_server.clients[i].fd, s);
            }
        }
        free(s);
    }
    pthread_mutex_unlock(&g_server.clients_mutex);
}

ClientInfo* find_client_by_username(const char *username) {
    if (!username) return NULL;

    pthread_mutex_lock(&g_server.clients_mutex);
    for (int i = 0; i < MAX_CLIENTS; i++) {
        if (g_server.clients[i].active && strcmp(g_server.clients[i].username, username) == 0) {
            pthread_mutex_unlock(&g_server.clients_mutex);
            return &g_server.clients[i];
        }
    }
    pthread_mutex_unlock(&g_server.clients_mutex);
    return NULL;
}

ClientInfo* find_client_by_fd(int fd) {
    pthread_mutex_lock(&g_server.clients_mutex);
    for (int i = 0; i < MAX_CLIENTS; i++) {
        if (g_server.clients[i].active && g_server.clients[i].fd == fd) {
            pthread_mutex_unlock(&g_server.clients_mutex);
            return &g_server.clients[i];
        }
    }
    pthread_mutex_unlock(&g_server.clients_mutex);
    return NULL;
}

ClientInfo* find_client_by_token(const char *token) {
    if (!token) return NULL;

    pthread_mutex_lock(&g_server.clients_mutex);
    for (int i = 0; i < MAX_CLIENTS; i++) {
        if (g_server.clients[i].active && strcmp(g_server.clients[i].session_token, token) == 0) {
            pthread_mutex_unlock(&g_server.clients_mutex);
            return &g_server.clients[i];
        }
    }
    pthread_mutex_unlock(&g_server.clients_mutex);
    return NULL;
}

void set_client_status(const char *username, int status) {
    if (!username) return;

    pthread_mutex_lock(&g_server.clients_mutex);
    for (int i = 0; i < MAX_CLIENTS; i++) {
        if (g_server.clients[i].active && strcmp(g_server.clients[i].username, username) == 0) {
            g_server.clients[i].status = status;
            break;
        }
    }
    pthread_mutex_unlock(&g_server.clients_mutex);
}

void server_stop(void) {
    g_server.running = 0;

    if (g_server.server_fd >= 0) {
        close(g_server.server_fd);
        g_server.server_fd = -1;
    }

    pthread_mutex_lock(&g_server.clients_mutex);
    for (int i = 0; i < MAX_CLIENTS; i++) {
        if (g_server.clients[i].active && g_server.clients[i].fd >= 0) {
            close(g_server.clients[i].fd);
            g_server.clients[i].active = 0;
            g_server.clients[i].fd = -1;
        }
    }
    pthread_mutex_unlock(&g_server.clients_mutex);

    pthread_mutex_destroy(&g_server.clients_mutex);
    printf("[INFO] Server stopped.\n");
}
