-- Battleship Game Database Schema
-- SQLite3

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    elo INTEGER NOT NULL DEFAULT 1200,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    draws INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME
);

-- Matches table
CREATE TABLE IF NOT EXISTS matches (
    id TEXT PRIMARY KEY,          -- UUID-like match identifier
    player1 TEXT NOT NULL,
    player2 TEXT NOT NULL,
    winner TEXT,                  -- NULL if draw or unfinished
    result TEXT NOT NULL DEFAULT 'ONGOING',  -- ONGOING, WIN, DRAW, FORFEIT
    player1_elo_before INTEGER,
    player2_elo_before INTEGER,
    player1_elo_after INTEGER,
    player2_elo_after INTEGER,
    player1_board TEXT,
    player2_board TEXT,
    player1_ships TEXT,
    player2_ships TEXT,
    start_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_time DATETIME,
    FOREIGN KEY(player1) REFERENCES users(username),
    FOREIGN KEY(player2) REFERENCES users(username)
);

-- Moves log for replay
CREATE TABLE IF NOT EXISTS moves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL,
    player TEXT NOT NULL,         -- username of who fired
    row INTEGER NOT NULL,
    col INTEGER NOT NULL,
    result TEXT NOT NULL,         -- HIT or MISS
    sunk INTEGER NOT NULL DEFAULT 0,  -- 1 if ship was sunk
    ship_size INTEGER DEFAULT 0,      -- size of sunk ship (0 if not sunk)
    move_num INTEGER NOT NULL,        -- sequence number within match
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(match_id) REFERENCES matches(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_moves_match_id ON moves(match_id);
CREATE INDEX IF NOT EXISTS idx_moves_match_num ON moves(match_id, move_num);
CREATE INDEX IF NOT EXISTS idx_matches_player1 ON matches(player1);
CREATE INDEX IF NOT EXISTS idx_matches_player2 ON matches(player2);
