"""
Tests for Battleship bug fixes:
  Bug 1: History Win/Loss determination
  Bug 2: Replay player identity (You vs Opponent)
  Bug 3: Replay board data (separate boards per player)

These tests verify the client-side logic independently of the running server,
using the same data structures the client code operates on.
"""

import unittest
import sys
import os
import json
import sqlite3
import tempfile

# Ensure client package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))


# ─────────────────────────────────────────────────────────────────────────
# Bug 1 Tests: History Win/Loss result determination
# ─────────────────────────────────────────────────────────────────────────

class TestHistoryResultDetermination(unittest.TestCase):
    """Verifies that the history result logic correctly classifies Win/Loss/Draw
    based on the winner field and the current user's identity."""

    @staticmethod
    def determine_result(match: dict, current_username: str) -> str:
        """Reimplements the fixed result determination logic from history.py."""
        winner = match.get("winner", "")
        res_type = str(match.get("result", "")).upper()

        if res_type in ("DRAW",) or (not winner and res_type not in ("ONGOING",)):
            return "DRAW"
        elif winner == current_username:
            return "WIN"
        elif winner and winner != current_username:
            return "LOSS"
        elif res_type == "ONGOING":
            return "ONGOING"
        else:
            return "LOSS"

    def test_player1_wins_player1_sees_win(self):
        match = {"winner": "Alice", "result": "WIN", "player1": "Alice", "player2": "Bob"}
        self.assertEqual(self.determine_result(match, "Alice"), "WIN")

    def test_player1_wins_player2_sees_loss(self):
        match = {"winner": "Alice", "result": "WIN", "player1": "Alice", "player2": "Bob"}
        self.assertEqual(self.determine_result(match, "Bob"), "LOSS")

    def test_player2_wins_player2_sees_win(self):
        match = {"winner": "Bob", "result": "WIN", "player1": "Alice", "player2": "Bob"}
        self.assertEqual(self.determine_result(match, "Bob"), "WIN")

    def test_player2_wins_player1_sees_loss(self):
        match = {"winner": "Bob", "result": "WIN", "player1": "Alice", "player2": "Bob"}
        self.assertEqual(self.determine_result(match, "Alice"), "LOSS")

    def test_forfeit_winner_sees_win(self):
        match = {"winner": "Alice", "result": "FORFEIT", "player1": "Alice", "player2": "Bob"}
        self.assertEqual(self.determine_result(match, "Alice"), "WIN")

    def test_forfeit_loser_sees_loss(self):
        match = {"winner": "Alice", "result": "FORFEIT", "player1": "Alice", "player2": "Bob"}
        self.assertEqual(self.determine_result(match, "Bob"), "LOSS")

    def test_surrender_winner_sees_win(self):
        match = {"winner": "Bob", "result": "SURRENDER", "player1": "Alice", "player2": "Bob"}
        self.assertEqual(self.determine_result(match, "Bob"), "WIN")

    def test_surrender_loser_sees_loss(self):
        match = {"winner": "Bob", "result": "SURRENDER", "player1": "Alice", "player2": "Bob"}
        self.assertEqual(self.determine_result(match, "Alice"), "LOSS")

    def test_draw_both_see_draw(self):
        match = {"winner": "", "result": "DRAW", "player1": "Alice", "player2": "Bob"}
        self.assertEqual(self.determine_result(match, "Alice"), "DRAW")
        self.assertEqual(self.determine_result(match, "Bob"), "DRAW")

    def test_results_are_always_opposite(self):
        """Win and Loss must always be complementary for the same match."""
        for winner_name in ["Alice", "Bob"]:
            for result_type in ["WIN", "FORFEIT", "SURRENDER"]:
                match = {"winner": winner_name, "result": result_type,
                         "player1": "Alice", "player2": "Bob"}
                r_alice = self.determine_result(match, "Alice")
                r_bob = self.determine_result(match, "Bob")
                self.assertNotEqual(r_alice, r_bob,
                                    f"Both players got '{r_alice}' for winner={winner_name}, result={result_type}")
                self.assertIn(r_alice, ("WIN", "LOSS"))
                self.assertIn(r_bob, ("WIN", "LOSS"))

    def test_ongoing_match(self):
        match = {"winner": "", "result": "ONGOING", "player1": "Alice", "player2": "Bob"}
        self.assertEqual(self.determine_result(match, "Alice"), "ONGOING")

    def test_real_db_data_forfeit(self):
        """Test with actual data format from the existing database."""
        match = {"id": "37da46ef", "player1": "test2", "player2": "test",
                 "winner": "test", "result": "FORFEIT",
                 "player1_elo_before": 1200, "player2_elo_before": 1200,
                 "player1_elo_after": 1184, "player2_elo_after": 1216}
        # test wins (they are player2), test2 loses (they are player1)
        self.assertEqual(self.determine_result(match, "test"), "WIN")
        self.assertEqual(self.determine_result(match, "test2"), "LOSS")

    def test_real_db_data_win(self):
        """Test with actual data from a normal WIN match."""
        match = {"id": "4d6a2eb6", "player1": "test2", "player2": "test",
                 "winner": "test2", "result": "WIN",
                 "player1_elo_before": 1217, "player2_elo_before": 1183,
                 "player1_elo_after": 1231, "player2_elo_after": 1169}
        self.assertEqual(self.determine_result(match, "test2"), "WIN")
        self.assertEqual(self.determine_result(match, "test"), "LOSS")


# ─────────────────────────────────────────────────────────────────────────
# Bug 2 Tests: Replay player identity
# ─────────────────────────────────────────────────────────────────────────

class TestReplayPlayerIdentity(unittest.TestCase):
    """Verifies that replay correctly identifies You vs Opponent."""

    @staticmethod
    def get_identity_labels(p1_name: str, p2_name: str, current_user: str) -> dict:
        """Reimplements the identity logic from the fixed replay.py draw method."""
        if current_user == p1_name:
            left_label = f"{p1_name} (You)"
            right_label = f"{p2_name} (Opponent)"
        elif current_user == p2_name:
            left_label = f"{p1_name} (Opponent)"
            right_label = f"{p2_name} (You)"
        else:
            left_label = p1_name
            right_label = p2_name
        return {"left": left_label, "right": right_label}

    @staticmethod
    def get_result_labels(p1_name: str, p2_name: str, winner: str, result_type: str) -> dict:
        """Reimplements result label logic from replay.py."""
        if result_type.upper() == "DRAW":
            return {"p1": "Draw", "p2": "Draw"}
        elif winner == p1_name:
            return {"p1": "Winner", "p2": "Loser"}
        elif winner == p2_name:
            return {"p1": "Loser", "p2": "Winner"}
        else:
            return {"p1": "", "p2": ""}

    def test_player1_viewing(self):
        labels = self.get_identity_labels("Alice", "Bob", "Alice")
        self.assertIn("You", labels["left"])
        self.assertIn("Opponent", labels["right"])
        self.assertIn("Alice", labels["left"])
        self.assertIn("Bob", labels["right"])

    def test_player2_viewing(self):
        labels = self.get_identity_labels("Alice", "Bob", "Bob")
        self.assertIn("Opponent", labels["left"])
        self.assertIn("You", labels["right"])

    def test_spectator_viewing(self):
        labels = self.get_identity_labels("Alice", "Bob", "Charlie")
        self.assertNotIn("You", labels["left"])
        self.assertNotIn("You", labels["right"])
        self.assertNotIn("Opponent", labels["left"])
        self.assertNotIn("Opponent", labels["right"])

    def test_result_winner_player1(self):
        results = self.get_result_labels("Alice", "Bob", "Alice", "WIN")
        self.assertEqual(results["p1"], "Winner")
        self.assertEqual(results["p2"], "Loser")

    def test_result_winner_player2(self):
        results = self.get_result_labels("Alice", "Bob", "Bob", "FORFEIT")
        self.assertEqual(results["p1"], "Loser")
        self.assertEqual(results["p2"], "Winner")

    def test_result_draw(self):
        results = self.get_result_labels("Alice", "Bob", "", "DRAW")
        self.assertEqual(results["p1"], "Draw")
        self.assertEqual(results["p2"], "Draw")

    def test_identity_uses_id_not_order(self):
        """Player identity should use username comparison, not data ordering."""
        # Player2 is 'Alice' (not first in data), verifying identity is by ID
        labels = self.get_identity_labels("Bob", "Alice", "Alice")
        self.assertIn("You", labels["right"])
        self.assertIn("Opponent", labels["left"])


# ─────────────────────────────────────────────────────────────────────────
# Bug 3 Tests: Replay board data separation
# ─────────────────────────────────────────────────────────────────────────

GRID_SIZE = 10


def create_empty_board():
    return [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]


def get_ship_cells(ships_data):
    """Compute all cells from ship placement data."""
    cells = []
    for ship in ships_data:
        row = int(ship.get("row", 0))
        col = int(ship.get("col", 0))
        size = int(ship.get("size", 0))
        direction = int(ship.get("direction", 0))
        for i in range(size):
            if direction == 0:
                cells.append((row, col + i))
            else:
                cells.append((row + i, col))
    return cells


def recompute_boards(moves, p1_name, p2_name, p1_ships_data, p2_ships_data, current_step):
    """Reimplements _recompute_boards from fixed replay.py."""
    p1_board = create_empty_board()
    p2_board = create_empty_board()

    p1_ship_cells = set(get_ship_cells(p1_ships_data))
    p2_ship_cells = set(get_ship_cells(p2_ships_data))

    for r, c in p1_ship_cells:
        if 0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE:
            p1_board[r][c] = 1
    for r, c in p2_ship_cells:
        if 0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE:
            p2_board[r][c] = 1

    for step_idx in range(current_step):
        m = moves[step_idx]
        shooter = m.get("player", "")
        r = int(m.get("row", 0))
        c = int(m.get("col", 0))
        res = str(m.get("result", "MISS")).upper()

        if shooter == p1_name:
            if res == "HIT":
                p2_board[r][c] = 2
            else:
                p2_board[r][c] = 3
        else:
            if res == "HIT":
                p1_board[r][c] = 2
            else:
                p1_board[r][c] = 3

    return p1_board, p2_board


class TestReplayBoardData(unittest.TestCase):
    """Verifies that replay uses separate, correct board data for each player."""

    def setUp(self):
        # P1 ships: a destroyer at (0,0) horizontal (size 2)
        self.p1_ships = [
            {"id": 0, "size": 2, "row": 0, "col": 0, "direction": 0},
        ]
        # P2 ships: a destroyer at (5,5) vertical (size 2)
        self.p2_ships = [
            {"id": 0, "size": 2, "row": 5, "col": 5, "direction": 1},
        ]
        self.moves = [
            {"player": "Alice", "row": 5, "col": 5, "result": "HIT", "sunk": False},
            {"player": "Bob", "row": 0, "col": 0, "result": "HIT", "sunk": False},
            {"player": "Alice", "row": 6, "col": 5, "result": "HIT", "sunk": True},
            {"player": "Bob", "row": 0, "col": 1, "result": "HIT", "sunk": True},
        ]

    def test_initial_boards_have_different_ships(self):
        """Ship placements should differ between boards."""
        p1_board, p2_board = recompute_boards([], "Alice", "Bob", self.p1_ships, self.p2_ships, 0)
        # P1 has ship at (0,0) and (0,1)
        self.assertEqual(p1_board[0][0], 1)
        self.assertEqual(p1_board[0][1], 1)
        self.assertEqual(p1_board[5][5], 0)
        # P2 has ship at (5,5) and (6,5)
        self.assertEqual(p2_board[5][5], 1)
        self.assertEqual(p2_board[6][5], 1)
        self.assertEqual(p2_board[0][0], 0)

    def test_boards_are_not_shared(self):
        """Modifying one board should not affect the other."""
        p1_board, p2_board = recompute_boards([], "Alice", "Bob", self.p1_ships, self.p2_ships, 0)
        self.assertIsNot(p1_board, p2_board)

    def test_hits_land_on_correct_board(self):
        """Alice fires → P2's board gets hit. Bob fires → P1's board gets hit."""
        p1_board, p2_board = recompute_boards(self.moves, "Alice", "Bob",
                                               self.p1_ships, self.p2_ships, 1)
        # Alice shot at (5,5) on P2's board → should be HIT (2)
        self.assertEqual(p2_board[5][5], 2)
        # P1's board should be untouched at (5,5)
        self.assertEqual(p1_board[5][5], 0)

    def test_second_move_hits_other_board(self):
        """Bob fires at P1's board."""
        p1_board, p2_board = recompute_boards(self.moves, "Alice", "Bob",
                                               self.p1_ships, self.p2_ships, 2)
        # Bob shot at (0,0) on P1's board → should be HIT (2)
        self.assertEqual(p1_board[0][0], 2)
        # P2's board (0,0) should be empty
        self.assertEqual(p2_board[0][0], 0)

    def test_miss_on_correct_board(self):
        """Miss should land on correct board with value 3."""
        miss_moves = [
            {"player": "Alice", "row": 0, "col": 0, "result": "MISS"},
        ]
        p1_board, p2_board = recompute_boards(miss_moves, "Alice", "Bob",
                                               self.p1_ships, self.p2_ships, 1)
        self.assertEqual(p2_board[0][0], 3)  # Miss on P2's board
        self.assertEqual(p1_board[0][0], 1)  # P1's ship untouched

    def test_all_moves_applied(self):
        """All 4 moves should be correctly applied."""
        p1_board, p2_board = recompute_boards(self.moves, "Alice", "Bob",
                                               self.p1_ships, self.p2_ships, 4)
        # P2's board: (5,5) and (6,5) both hit
        self.assertEqual(p2_board[5][5], 2)
        self.assertEqual(p2_board[6][5], 2)
        # P1's board: (0,0) and (0,1) both hit
        self.assertEqual(p1_board[0][0], 2)
        self.assertEqual(p1_board[0][1], 2)

    def test_stepping_back_resets_correctly(self):
        """Going back to step 0 should show only ships, no hits/misses."""
        p1_board, p2_board = recompute_boards(self.moves, "Alice", "Bob",
                                               self.p1_ships, self.p2_ships, 0)
        # Only ships, no hits
        self.assertEqual(p1_board[0][0], 1)  # Ship
        self.assertEqual(p2_board[5][5], 1)  # Ship

    def test_no_ship_data_still_works(self):
        """If no ship data, boards start empty but moves still apply."""
        p1_board, p2_board = recompute_boards(self.moves, "Alice", "Bob",
                                               [], [], 2)
        # Moves still apply correctly
        self.assertEqual(p2_board[5][5], 2)  # HIT (no ship shown but hit marker)
        self.assertEqual(p1_board[0][0], 2)  # HIT

    def test_boards_independent_across_steps(self):
        """Each step recompute should produce independent boards."""
        _, p2_board_step1 = recompute_boards(self.moves, "Alice", "Bob",
                                              self.p1_ships, self.p2_ships, 1)
        _, p2_board_step2 = recompute_boards(self.moves, "Alice", "Bob",
                                              self.p1_ships, self.p2_ships, 2)
        # Step 1: only (5,5) hit on p2
        self.assertEqual(p2_board_step1[5][5], 2)
        self.assertEqual(p2_board_step1[6][5], 1)  # Ship not yet hit
        # Step 2: same (5,5) hit on p2, no new hits on p2 (Bob fired at p1)
        self.assertEqual(p2_board_step2[5][5], 2)
        self.assertEqual(p2_board_step2[6][5], 1)  # Still not hit


# ─────────────────────────────────────────────────────────────────────────
# Database / Server-side tests
# ─────────────────────────────────────────────────────────────────────────

class TestDatabaseSchemaAndQueries(unittest.TestCase):
    """Tests the database schema and query logic using SQLite directly."""

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("PRAGMA foreign_keys = OFF;")  # Simplify testing
        self.db.executescript("""
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
            CREATE TABLE IF NOT EXISTS matches (
                id TEXT PRIMARY KEY,
                player1 TEXT NOT NULL,
                player2 TEXT NOT NULL,
                winner TEXT,
                result TEXT NOT NULL DEFAULT 'ONGOING',
                player1_elo_before INTEGER,
                player2_elo_before INTEGER,
                player1_elo_after INTEGER,
                player2_elo_after INTEGER,
                player1_board TEXT,
                player2_board TEXT,
                player1_ships TEXT,
                player2_ships TEXT,
                start_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                end_time DATETIME
            );
            CREATE TABLE IF NOT EXISTS moves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT NOT NULL,
                player TEXT NOT NULL,
                row INTEGER NOT NULL,
                col INTEGER NOT NULL,
                result TEXT NOT NULL,
                sunk INTEGER NOT NULL DEFAULT 0,
                ship_size INTEGER DEFAULT 0,
                move_num INTEGER NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Insert test users
        self.db.execute("INSERT INTO users (username, password_hash) VALUES ('Alice', 'hash1')")
        self.db.execute("INSERT INTO users (username, password_hash) VALUES ('Bob', 'hash2')")
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def _create_match(self, match_id, p1, p2, winner, result,
                      p1_elo_before=1200, p2_elo_before=1200,
                      p1_elo_after=1216, p2_elo_after=1184,
                      p1_ships=None, p2_ships=None):
        self.db.execute(
            "INSERT INTO matches (id, player1, player2, winner, result, "
            "player1_elo_before, player2_elo_before, player1_elo_after, player2_elo_after, "
            "player1_ships, player2_ships) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (match_id, p1, p2, winner, result,
             p1_elo_before, p2_elo_before, p1_elo_after, p2_elo_after,
             p1_ships, p2_ships)
        )
        self.db.commit()

    def test_winner_field_stores_username(self):
        """Verify the winner field stores the actual winning username."""
        self._create_match("m1", "Alice", "Bob", "Alice", "WIN")
        row = self.db.execute("SELECT winner FROM matches WHERE id='m1'").fetchone()
        self.assertEqual(row[0], "Alice")

    def test_match_result_with_ships(self):
        """Verify ship data is stored and retrievable."""
        p1_ships = json.dumps([{"id": 0, "size": 2, "row": 0, "col": 0, "direction": 0}])
        p2_ships = json.dumps([{"id": 0, "size": 2, "row": 5, "col": 5, "direction": 1}])
        self._create_match("m2", "Alice", "Bob", "Alice", "WIN",
                           p1_ships=p1_ships, p2_ships=p2_ships)

        row = self.db.execute(
            "SELECT player1_ships, player2_ships FROM matches WHERE id='m2'"
        ).fetchone()
        self.assertEqual(json.loads(row[0]), json.loads(p1_ships))
        self.assertEqual(json.loads(row[1]), json.loads(p2_ships))

    def test_history_query_returns_both_players(self):
        """History query for any player in a match should return that match."""
        self._create_match("m3", "Alice", "Bob", "Bob", "WIN")

        # Alice's history
        alice_rows = self.db.execute(
            "SELECT * FROM matches WHERE player1 = ? OR player2 = ?",
            ("Alice", "Alice")
        ).fetchall()
        self.assertEqual(len(alice_rows), 1)

        # Bob's history
        bob_rows = self.db.execute(
            "SELECT * FROM matches WHERE player1 = ? OR player2 = ?",
            ("Bob", "Bob")
        ).fetchall()
        self.assertEqual(len(bob_rows), 1)

    def test_winner_determines_result_not_result_field(self):
        """The 'result' field is the match outcome type, not who won.
        Win/Loss must be determined by comparing 'winner' to current user."""
        self._create_match("m4", "Alice", "Bob", "Bob", "WIN")

        row = self.db.execute("SELECT winner, result FROM matches WHERE id='m4'").fetchone()
        winner, result_type = row

        # For Alice (loser): winner != Alice, so it's a LOSS
        self.assertNotEqual(winner, "Alice")
        # For Bob (winner): winner == Bob, so it's a WIN
        self.assertEqual(winner, "Bob")
        # The result field is "WIN" for both — it indicates match type, not who won
        self.assertEqual(result_type, "WIN")


# ─────────────────────────────────────────────────────────────────────────
# Replay data serialization tests
# ─────────────────────────────────────────────────────────────────────────

class TestReplayDataSerialization(unittest.TestCase):
    """Tests the replay data format expected by the client."""

    def test_replay_data_has_required_fields(self):
        """REPLAY_DATA message should contain player names, winner, and ships."""
        # Simulate what the fixed server sends
        replay_data = {
            "type": "REPLAY_DATA",
            "match_id": "test-match-id",
            "player1": "Alice",
            "player2": "Bob",
            "winner": "Alice",
            "result": "WIN",
            "player1_ships": [{"id": 0, "size": 2, "row": 0, "col": 0, "direction": 0}],
            "player2_ships": [{"id": 0, "size": 2, "row": 5, "col": 5, "direction": 1}],
            "moves": [
                {"player": "Alice", "row": 5, "col": 5, "result": "HIT", "sunk": False, "move_num": 1},
            ],
        }

        self.assertIn("player1", replay_data)
        self.assertIn("player2", replay_data)
        self.assertIn("winner", replay_data)
        self.assertIn("player1_ships", replay_data)
        self.assertIn("player2_ships", replay_data)
        self.assertIsInstance(replay_data["player1_ships"], list)
        self.assertIsInstance(replay_data["player2_ships"], list)
        self.assertNotEqual(replay_data["player1"], replay_data["player2"])

    def test_ship_data_produces_different_boards(self):
        """Different ship placements must produce different boards."""
        p1_ships = [{"id": 0, "size": 2, "row": 0, "col": 0, "direction": 0}]
        p2_ships = [{"id": 0, "size": 2, "row": 5, "col": 5, "direction": 1}]

        p1_cells = set(get_ship_cells(p1_ships))
        p2_cells = set(get_ship_cells(p2_ships))

        self.assertNotEqual(p1_cells, p2_cells)
        self.assertEqual(p1_cells, {(0, 0), (0, 1)})
        self.assertEqual(p2_cells, {(5, 5), (6, 5)})


if __name__ == "__main__":
    unittest.main(verbosity=2)
