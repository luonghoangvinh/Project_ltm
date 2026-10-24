#include "common.h"
#include "network.h"
#include "database.h"
#include "session.h"
#include "matchmaking.h"
#include "game.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void handle_signal(int sig) {
    if (sig == SIGINT || sig == SIGTERM) {
        printf("\n[INFO] Received termination signal (%d). Shutting down server gracefully...\n", sig);
        server_stop();
    }
}

static void print_usage(const char *prog_name) {
    printf("Battleship Server - Network Programming Project\n");
    printf("Usage: %s [options]\n", prog_name);
    printf("Options:\n");
    printf("  --port, -p <port>     Port to listen on (default: %d)\n", PORT_DEFAULT);
    printf("  --db, -d <path>       SQLite database file path (default: battleship.db)\n");
    printf("  --help, -h            Show this help message\n");
}

int main(int argc, char *argv[]) {
    int port = PORT_DEFAULT;
    const char *db_path = "battleship.db";

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--port") == 0 || strcmp(argv[i], "-p") == 0) {
            if (i + 1 < argc) {
                port = atoi(argv[++i]);
                if (port <= 0 || port > 65535) {
                    fprintf(stderr, "[ERROR] Invalid port number: %s\n", argv[i]);
                    return 1;
                }
            } else {
                fprintf(stderr, "[ERROR] Missing port argument\n");
                return 1;
            }
        } else if (strcmp(argv[i], "--db") == 0 || strcmp(argv[i], "-d") == 0) {
            if (i + 1 < argc) {
                db_path = argv[++i];
            } else {
                fprintf(stderr, "[ERROR] Missing database path argument\n");
                return 1;
            }
        } else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            print_usage(argv[0]);
            return 0;
        } else {
            fprintf(stderr, "[WARN] Unknown argument: %s\n", argv[i]);
        }
    }

    /* Ignore SIGPIPE to avoid process crashes on broken sockets */
    signal(SIGPIPE, SIG_IGN);

    /* Setup signal handlers for graceful shutdown */
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = handle_signal;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);

    /* Seed PRNG */
    srand((unsigned int)(time(NULL) ^ getpid()));

    printf("========================================\n");
    printf("       BATTLESHIP SERVER STARTUP        \n");
    printf("========================================\n");
    printf("[INFO] Target Port     : %d\n", port);
    printf("[INFO] Database Path   : %s\n", db_path);

    /* Initialize subsystems */
    if (db_init(db_path) != 0) {
        fprintf(stderr, "[FATAL] Failed to initialize database: %s\n", db_path);
        return 1;
    }
    printf("[INFO] Database initialized successfully.\n");

    session_init();
    matchmaking_init();
    game_manager_init();

    /* Initialize and start server */
    if (server_init(port, db_path) != 0) {
        fprintf(stderr, "[FATAL] Failed to start server on port %d\n", port);
        db_close();
        return 1;
    }

    printf("[INFO] Server is running. Press Ctrl+C to terminate.\n");
    server_run();

    /* Cleanup */
    printf("[INFO] Cleaning up resources...\n");
    game_manager_cleanup();
    matchmaking_cleanup();
    session_cleanup();
    db_close();

    printf("[INFO] Server terminated cleanly. Goodbye.\n");
    return 0;
}
