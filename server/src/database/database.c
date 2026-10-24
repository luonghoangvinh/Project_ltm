#include "database.h"
#include <sqlite3.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>

static sqlite3 *g_db = NULL;
static pthread_mutex_t g_db_mutex = PTHREAD_MUTEX_INITIALIZER;

static const char *SCHEMA_SQL =
    "PRAGMA journal_mode = WAL;\n"
    "PRAGMA foreign_keys = ON;\n"
    "\n"
    "CREATE TABLE IF NOT EXISTS users (\n"
    "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "    username TEXT UNIQUE NOT NULL,\n"
    "    password_hash TEXT NOT NULL,\n"
    "    elo INTEGER NOT NULL DEFAULT 1200,\n"
    "    wins INTEGER NOT NULL DEFAULT 0,\n"
    "    losses INTEGER NOT NULL DEFAULT 0,\n"
    "    draws INTEGER NOT NULL DEFAULT 0,\n"
    "    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,\n"
    "    last_login DATETIME\n"
    ");\n"
    "\n"
    "CREATE TABLE IF NOT EXISTS matches (\n"
    "    id TEXT PRIMARY KEY,\n"
    "    player1 TEXT NOT NULL,\n"
    "    player2 TEXT NOT NULL,\n"
    "    winner TEXT,\n"
    "    result TEXT NOT NULL DEFAULT 'ONGOING',\n"
    "    player1_elo_before INTEGER,\n"
    "    player2_elo_before INTEGER,\n"
    "    player1_elo_after INTEGER,\n"
    "    player2_elo_after INTEGER,\n"
    "    start_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,\n"
    "    end_time DATETIME,\n"
    "    FOREIGN KEY(player1) REFERENCES users(username),\n"
    "    FOREIGN KEY(player2) REFERENCES users(username)\n"
    ");\n"
    "\n"
    "CREATE TABLE IF NOT EXISTS moves (\n"
    "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "    match_id TEXT NOT NULL,\n"
    "    player TEXT NOT NULL,\n"
    "    row INTEGER NOT NULL,\n"
    "    col INTEGER NOT NULL,\n"
    "    result TEXT NOT NULL,\n"
    "    sunk INTEGER NOT NULL DEFAULT 0,\n"
    "    ship_size INTEGER DEFAULT 0,\n"
    "    move_num INTEGER NOT NULL,\n"
    "    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,\n"
    "    FOREIGN KEY(match_id) REFERENCES matches(id)\n"
    ");\n"
    "\n"
    "CREATE INDEX IF NOT EXISTS idx_moves_match_id ON moves(match_id);\n"
    "CREATE INDEX IF NOT EXISTS idx_moves_match_num ON moves(match_id, move_num);\n"
    "CREATE INDEX IF NOT EXISTS idx_matches_player1 ON matches(player1);\n"
    "CREATE INDEX IF NOT EXISTS idx_matches_player2 ON matches(player2);\n";

int db_init(const char *db_path) {
    pthread_mutex_lock(&g_db_mutex);

    int rc = sqlite3_open_v2(db_path, &g_db,
                             SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_FULLMUTEX,
                             NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "[DB ERROR] Cannot open database %s: %s\n", db_path, sqlite3_errmsg(g_db));
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    char *errmsg = NULL;
    rc = sqlite3_exec(g_db, SCHEMA_SQL, NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "[DB ERROR] Failed to initialize schema: %s\n", errmsg ? errmsg : "unknown");
        if (errmsg) sqlite3_free(errmsg);
        sqlite3_close(g_db);
        g_db = NULL;
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    pthread_mutex_unlock(&g_db_mutex);
    return 0;
}

void db_close(void) {
    pthread_mutex_lock(&g_db_mutex);
    if (g_db) {
        sqlite3_close(g_db);
        g_db = NULL;
    }
    pthread_mutex_unlock(&g_db_mutex);
}

int db_register_user(const char *username, const char *password_hash) {
    pthread_mutex_lock(&g_db_mutex);
    if (!g_db) {
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    const char *sql = "INSERT INTO users (username, password_hash, elo) VALUES (?, ?, 1200);";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(g_db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    sqlite3_bind_text(stmt, 1, username, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, password_hash, -1, SQLITE_STATIC);

    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    pthread_mutex_unlock(&g_db_mutex);
    return (rc == SQLITE_DONE) ? 0 : -1;
}

int db_check_credentials(const char *username, const char *password_hash, int *out_elo) {
    pthread_mutex_lock(&g_db_mutex);
    if (!g_db) {
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    const char *sql = "SELECT elo, password_hash FROM users WHERE username = ?;";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(g_db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    sqlite3_bind_text(stmt, 1, username, -1, SQLITE_STATIC);

    rc = sqlite3_step(stmt);
    int match = 0;
    if (rc == SQLITE_ROW) {
        int elo = sqlite3_column_int(stmt, 0);
        const char *db_hash = (const char *)sqlite3_column_text(stmt, 1);
        if (db_hash && strcmp(db_hash, password_hash) == 0) {
            match = 1;
            if (out_elo) *out_elo = elo;
        }
    }
    sqlite3_finalize(stmt);

    if (match) {
        const char *upd_sql = "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE username = ?;";
        if (sqlite3_prepare_v2(g_db, upd_sql, -1, &stmt, NULL) == SQLITE_OK) {
            sqlite3_bind_text(stmt, 1, username, -1, SQLITE_STATIC);
            sqlite3_step(stmt);
            sqlite3_finalize(stmt);
        }
    }

    pthread_mutex_unlock(&g_db_mutex);
    return match ? 0 : -1;
}

int db_get_user_elo(const char *username, int *out_elo) {
    pthread_mutex_lock(&g_db_mutex);
    if (!g_db) {
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    const char *sql = "SELECT elo FROM users WHERE username = ?;";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(g_db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    sqlite3_bind_text(stmt, 1, username, -1, SQLITE_STATIC);

    rc = sqlite3_step(stmt);
    int res = -1;
    if (rc == SQLITE_ROW) {
        if (out_elo) *out_elo = sqlite3_column_int(stmt, 0);
        res = 0;
    }
    sqlite3_finalize(stmt);

    pthread_mutex_unlock(&g_db_mutex);
    return res;
}

int db_update_elo(const char *username, int new_elo, int win, int loss, int draw) {
    pthread_mutex_lock(&g_db_mutex);
    if (!g_db) {
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    const char *sql = "UPDATE users SET elo = ?, wins = wins + ?, losses = losses + ?, draws = draws + ? WHERE username = ?;";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(g_db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    sqlite3_bind_int(stmt, 1, new_elo);
    sqlite3_bind_int(stmt, 2, win);
    sqlite3_bind_int(stmt, 3, loss);
    sqlite3_bind_int(stmt, 4, draw);
    sqlite3_bind_text(stmt, 5, username, -1, SQLITE_STATIC);

    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    pthread_mutex_unlock(&g_db_mutex);
    return (rc == SQLITE_DONE) ? 0 : -1;
}

int db_create_match(const char *match_id, const char *player1, const char *player2, int p1_elo, int p2_elo) {
    pthread_mutex_lock(&g_db_mutex);
    if (!g_db) {
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    const char *sql = "INSERT INTO matches (id, player1, player2, player1_elo_before, player2_elo_before, result) VALUES (?, ?, ?, ?, ?, 'ONGOING');";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(g_db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    sqlite3_bind_text(stmt, 1, match_id, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, player1, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 3, player2, -1, SQLITE_STATIC);
    sqlite3_bind_int(stmt, 4, p1_elo);
    sqlite3_bind_int(stmt, 5, p2_elo);

    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    pthread_mutex_unlock(&g_db_mutex);
    return (rc == SQLITE_DONE) ? 0 : -1;
}

int db_save_match_result(const char *match_id, const char *winner, const char *result, int p1_elo_after, int p2_elo_after) {
    pthread_mutex_lock(&g_db_mutex);
    if (!g_db) {
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    const char *sql = "UPDATE matches SET winner = ?, result = ?, player1_elo_after = ?, player2_elo_after = ?, end_time = CURRENT_TIMESTAMP WHERE id = ?;";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(g_db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    if (winner && strlen(winner) > 0) {
        sqlite3_bind_text(stmt, 1, winner, -1, SQLITE_STATIC);
    } else {
        sqlite3_bind_null(stmt, 1);
    }
    sqlite3_bind_text(stmt, 2, result ? result : "FINISHED", -1, SQLITE_STATIC);
    sqlite3_bind_int(stmt, 3, p1_elo_after);
    sqlite3_bind_int(stmt, 4, p2_elo_after);
    sqlite3_bind_text(stmt, 5, match_id, -1, SQLITE_STATIC);

    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    pthread_mutex_unlock(&g_db_mutex);
    return (rc == SQLITE_DONE) ? 0 : -1;
}

int db_log_move(const char *match_id, const char *player, int row, int col, const char *result, int sunk, int ship_size, int move_num) {
    pthread_mutex_lock(&g_db_mutex);
    if (!g_db) {
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    const char *sql = "INSERT INTO moves (match_id, player, row, col, result, sunk, ship_size, move_num) VALUES (?, ?, ?, ?, ?, ?, ?, ?);";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(g_db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    sqlite3_bind_text(stmt, 1, match_id, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, player, -1, SQLITE_STATIC);
    sqlite3_bind_int(stmt, 3, row);
    sqlite3_bind_int(stmt, 4, col);
    sqlite3_bind_text(stmt, 5, result, -1, SQLITE_STATIC);
    sqlite3_bind_int(stmt, 6, sunk);
    sqlite3_bind_int(stmt, 7, ship_size);
    sqlite3_bind_int(stmt, 8, move_num);

    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    pthread_mutex_unlock(&g_db_mutex);
    return (rc == SQLITE_DONE) ? 0 : -1;
}

int db_get_history(const char *username, int limit, MatchRecord **out_records, int *out_count) {
    if (!username || !out_records || !out_count) return -1;
    *out_records = NULL;
    *out_count = 0;

    if (limit <= 0) limit = 10;
    if (limit > 100) limit = 100;

    pthread_mutex_lock(&g_db_mutex);
    if (!g_db) {
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    const char *sql = "SELECT id, player1, player2, COALESCE(winner, ''), result, "
                      "player1_elo_before, player2_elo_before, "
                      "COALESCE(player1_elo_after, 0), COALESCE(player2_elo_after, 0), "
                      "COALESCE(start_time, ''), COALESCE(end_time, '') "
                      "FROM matches WHERE player1 = ? OR player2 = ? "
                      "ORDER BY start_time DESC LIMIT ?;";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(g_db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    sqlite3_bind_text(stmt, 1, username, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, username, -1, SQLITE_STATIC);
    sqlite3_bind_int(stmt, 3, limit);

    MatchRecord *records = (MatchRecord *)malloc(sizeof(MatchRecord) * limit);
    if (!records) {
        sqlite3_finalize(stmt);
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    int count = 0;
    while (sqlite3_step(stmt) == SQLITE_ROW && count < limit) {
        MatchRecord *rec = &records[count];
        memset(rec, 0, sizeof(MatchRecord));

        const char *t = (const char *)sqlite3_column_text(stmt, 0);
        if (t) strncpy(rec->match_id, t, sizeof(rec->match_id) - 1);

        t = (const char *)sqlite3_column_text(stmt, 1);
        if (t) strncpy(rec->player1, t, sizeof(rec->player1) - 1);

        t = (const char *)sqlite3_column_text(stmt, 2);
        if (t) strncpy(rec->player2, t, sizeof(rec->player2) - 1);

        t = (const char *)sqlite3_column_text(stmt, 3);
        if (t) strncpy(rec->winner, t, sizeof(rec->winner) - 1);

        t = (const char *)sqlite3_column_text(stmt, 4);
        if (t) strncpy(rec->result, t, sizeof(rec->result) - 1);

        rec->p1_elo_before = sqlite3_column_int(stmt, 5);
        rec->p2_elo_before = sqlite3_column_int(stmt, 6);
        rec->p1_elo_after = sqlite3_column_int(stmt, 7);
        rec->p2_elo_after = sqlite3_column_int(stmt, 8);

        t = (const char *)sqlite3_column_text(stmt, 9);
        if (t) strncpy(rec->start_time, t, sizeof(rec->start_time) - 1);

        t = (const char *)sqlite3_column_text(stmt, 10);
        if (t) strncpy(rec->end_time, t, sizeof(rec->end_time) - 1);

        count++;
    }

    sqlite3_finalize(stmt);
    pthread_mutex_unlock(&g_db_mutex);

    *out_records = records;
    *out_count = count;
    return 0;
}

void db_free_history(MatchRecord *records) {
    if (records) {
        free(records);
    }
}

int db_get_replay_moves(const char *match_id, MoveRecord **out_moves, int *out_count) {
    if (!match_id || !out_moves || !out_count) return -1;
    *out_moves = NULL;
    *out_count = 0;

    pthread_mutex_lock(&g_db_mutex);
    if (!g_db) {
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    const char *sql = "SELECT id, match_id, player, row, col, result, sunk, ship_size, move_num, created_at "
                      "FROM moves WHERE match_id = ? ORDER BY move_num ASC;";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(g_db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    sqlite3_bind_text(stmt, 1, match_id, -1, SQLITE_STATIC);

    /* Allocate initial capacity */
    int capacity = 100;
    MoveRecord *moves = (MoveRecord *)malloc(sizeof(MoveRecord) * capacity);
    if (!moves) {
        sqlite3_finalize(stmt);
        pthread_mutex_unlock(&g_db_mutex);
        return -1;
    }

    int count = 0;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        if (count >= capacity) {
            capacity *= 2;
            MoveRecord *new_moves = (MoveRecord *)realloc(moves, sizeof(MoveRecord) * capacity);
            if (!new_moves) {
                free(moves);
                sqlite3_finalize(stmt);
                pthread_mutex_unlock(&g_db_mutex);
                return -1;
            }
            moves = new_moves;
        }

        MoveRecord *m = &moves[count];
        memset(m, 0, sizeof(MoveRecord));

        m->id = sqlite3_column_int(stmt, 0);

        const char *t = (const char *)sqlite3_column_text(stmt, 1);
        if (t) strncpy(m->match_id, t, sizeof(m->match_id) - 1);

        t = (const char *)sqlite3_column_text(stmt, 2);
        if (t) strncpy(m->player, t, sizeof(m->player) - 1);

        m->row = sqlite3_column_int(stmt, 3);
        m->col = sqlite3_column_int(stmt, 4);

        t = (const char *)sqlite3_column_text(stmt, 5);
        if (t) strncpy(m->result, t, sizeof(m->result) - 1);

        m->sunk = sqlite3_column_int(stmt, 6);
        m->ship_size = sqlite3_column_int(stmt, 7);
        m->move_num = sqlite3_column_int(stmt, 8);

        t = (const char *)sqlite3_column_text(stmt, 9);
        if (t) strncpy(m->created_at, t, sizeof(m->created_at) - 1);

        count++;
    }

    sqlite3_finalize(stmt);
    pthread_mutex_unlock(&g_db_mutex);

    *out_moves = moves;
    *out_count = count;
    return 0;
}

void db_free_replay(MoveRecord *moves) {
    if (moves) {
        free(moves);
    }
}
