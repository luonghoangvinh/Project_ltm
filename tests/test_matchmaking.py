"""
Automated tests for Battleship Random Matchmaking:
1. Unit tests for ELO matching criteria and dynamic range expansion.
2. Integration tests communicating with actual C server over TCP sockets.
"""

import json
import os
import socket
import subprocess
import time
import unittest


class TestMatchmakingLogic(unittest.TestCase):
    """Verifies the ELO matching & dynamic range formula used by C server."""

    @staticmethod
    def is_match_allowed(elo1: int, elo2: int, wait_sec: int) -> bool:
        """Mirroring the C server formula: allowed_diff = 100 + (max_wait / 10) * 50."""
        diff = abs(elo1 - elo2)
        allowed_diff = 100 + (wait_sec // 10) * 50
        return diff <= allowed_diff

    def test_equal_elo_immediate_match(self):
        # ELO bằng nhau -> ghép ngay lập tức (wait = 0)
        self.assertTrue(self.is_match_allowed(1200, 1200, 0))

    def test_diff_under_100_immediate_match(self):
        # ELO chênh lệch <= 100 -> ghép ngay (wait = 0)
        self.assertTrue(self.is_match_allowed(1200, 1280, 0))
        self.assertTrue(self.is_match_allowed(1200, 1100, 0))

    def test_diff_over_100_cannot_match_initially(self):
        # ELO chênh lệch > 100 -> ban đầu không được ghép (wait = 0)
        self.assertFalse(self.is_match_allowed(1200, 1301, 0))
        self.assertFalse(self.is_match_allowed(1200, 1350, 5))

    def test_dynamic_elo_expansion_after_wait(self):
        # Sau 10s: allowed = 150
        self.assertTrue(self.is_match_allowed(1200, 1350, 10))
        # Sau 20s: allowed = 200
        self.assertTrue(self.is_match_allowed(1200, 1400, 20))
        self.assertFalse(self.is_match_allowed(1200, 1450, 19))


class TestServerMatchmakingTCP(unittest.TestCase):
    """End-to-End TCP integration tests with the C server."""

    SERVER_PORT = 8898
    server_process = None

    @classmethod
    def setUpClass(cls):
        # Khởi chạy server C trên cổng test 8898
        # Dùng WSL hoặc binary có sẵn
        db_path = "/tmp/test_battleship_mm.db"
        cmd = f"wsl bash -c \"rm -f {db_path}* && cd /mnt/c/Users/vinh/OneDrive/Máy\\ tính/project_ltm/server && ./build/battleship_server --port {cls.SERVER_PORT} --db {db_path}\""
        cls.server_process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)  # Chờ server khởi động

    @classmethod
    def tearDownClass(cls):
        if cls.server_process:
            cls.server_process.terminate()
            subprocess.run("wsl pkill -f battleship_server", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _create_client_connection(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5.0)
        s.connect(("127.0.0.1", self.SERVER_PORT))
        return s

    def _send_msg(self, sock, msg_dict):
        payload = (json.dumps(msg_dict) + "\n").encode("utf-8")
        sock.sendall(payload)

    def setUp(self):
        self._buffers = {}

    def _recv_msg(self, sock, timeout=5.0):
        sock.settimeout(timeout)
        if sock not in self._buffers:
            self._buffers[sock] = ""

        while "\n" not in self._buffers[sock]:
            chunk = sock.recv(4096).decode("utf-8")
            if not chunk:
                raise ConnectionError("Server closed connection")
            self._buffers[sock] += chunk

        line, self._buffers[sock] = self._buffers[sock].split("\n", 1)
        line = line.strip()
        if not line:
            return self._recv_msg(sock, timeout)
        return json.loads(line)

    def _recv_until_type(self, sock, target_type, timeout=5.0):
        start = time.time()
        while time.time() - start < timeout:
            msg = self._recv_msg(sock, timeout=max(0.5, timeout - (time.time() - start)))
            if msg.get("type") == target_type:
                return msg
        raise TimeoutError(f"Timed out waiting for message of type '{target_type}'")

    def test_matchmaking_e2e(self):
        """Kiểm tra toàn bộ luồng: Tìm trận, Trùng lặp, Hủy tìm trận, và Ghép 2 client."""
        # 1. Đăng ký & Đăng nhập Client 1 (Alice)
        s1 = self._create_client_connection()
        username1 = f"alice_{int(time.time())}"
        self._send_msg(s1, {"type": "REGISTER", "username": username1, "password": "password123"})
        resp1_reg = self._recv_msg(s1)
        self.assertEqual(resp1_reg.get("type"), "REGISTER_OK")

        self._send_msg(s1, {"type": "LOGIN", "username": username1, "password": "password123"})
        resp1_login = self._recv_until_type(s1, "LOGIN_OK")
        token1 = resp1_login.get("session_token")
        self.assertTrue(bool(token1))

        # 2. Đăng ký & Đăng nhập Client 2 (Bob)
        s2 = self._create_client_connection()
        username2 = f"bob_{int(time.time())}"
        self._send_msg(s2, {"type": "REGISTER", "username": username2, "password": "password123"})
        resp2_reg = self._recv_msg(s2)
        self.assertEqual(resp2_reg.get("type"), "REGISTER_OK")

        self._send_msg(s2, {"type": "LOGIN", "username": username2, "password": "password123"})
        resp2_login = self._recv_until_type(s2, "LOGIN_OK")
        token2 = resp2_login.get("session_token")
        self.assertTrue(bool(token2))

        # Đọc bỏ PLAYER_UPDATE nếu có
        try:
            while True:
                s1.settimeout(0.3)
                self._recv_msg(s1, timeout=0.3)
        except Exception:
            pass

        try:
            while True:
                s2.settimeout(0.3)
                self._recv_msg(s2, timeout=0.3)
        except Exception:
            pass

        # 3. Client 1 gửi FIND_MATCH
        self._send_msg(s1, {"type": "FIND_MATCH", "session_token": token1})
        res_find1 = self._recv_until_type(s1, "FIND_MATCH_RESPONSE")
        self.assertEqual(res_find1.get("status"), "QUEUED")

        # 4. Client 1 gửi FIND_MATCH lần nữa -> Trả về ALREADY_QUEUED
        self._send_msg(s1, {"type": "FIND_MATCH", "session_token": token1})
        res_find_dup = self._recv_until_type(s1, "FIND_MATCH_RESPONSE")
        self.assertEqual(res_find_dup.get("status"), "ALREADY_QUEUED")

        # 5. Client 1 gửi CANCEL_FIND_MATCH -> Trả về CANCELLED
        self._send_msg(s1, {"type": "CANCEL_FIND_MATCH", "session_token": token1})
        res_cancel = self._recv_until_type(s1, "CANCEL_FIND_MATCH_RESPONSE")
        self.assertEqual(res_cancel.get("status"), "CANCELLED")

        # 6. Ghép trận thực tế:
        # Client 1 tham gia hàng chờ
        self._send_msg(s1, {"type": "FIND_MATCH", "session_token": token1})
        res_find_again = self._recv_until_type(s1, "FIND_MATCH_RESPONSE")
        self.assertEqual(res_find_again.get("status"), "QUEUED")

        # Client 2 tham gia hàng chờ
        self._send_msg(s2, {"type": "FIND_MATCH", "session_token": token2})

        # Cả 2 client phải nhận được MATCH_FOUND từ server C!
        match1 = self._recv_until_type(s1, "MATCH_FOUND", timeout=5.0)
        match2 = self._recv_until_type(s2, "MATCH_FOUND", timeout=5.0)

        # Kiểm tra tính khớp của trận đấu
        self.assertEqual(match1.get("type"), "MATCH_FOUND")
        self.assertEqual(match2.get("type"), "MATCH_FOUND")
        self.assertEqual(match1.get("match_id"), match2.get("match_id"))
        self.assertEqual(match1.get("opponent"), username2)
        self.assertEqual(match2.get("opponent"), username1)
        # Lượt đi phải đối nghịch nhau (một người true, một người false)
        self.assertNotEqual(match1.get("you_go_first"), match2.get("you_go_first"))

        # 7. Kiểm tra người đang trong trận không thể tìm trận tiếp
        self._send_msg(s1, {"type": "FIND_MATCH", "session_token": token1})
        err_msg = self._recv_until_type(s1, "ERROR", timeout=3.0)
        self.assertIn("in a game", err_msg.get("message", "").lower())

        s1.close()
        s2.close()

    def test_disconnect_removes_from_queue(self):
        """Kiểm tra khi client ngắt kết nối, server tự động dọn dẹp khỏi hàng chờ."""
        s = self._create_client_connection()
        uname = f"disco_{int(time.time())}"
        self._send_msg(s, {"type": "REGISTER", "username": uname, "password": "password123"})
        self._recv_msg(s)
        self._send_msg(s, {"type": "LOGIN", "username": uname, "password": "password123"})
        token = self._recv_until_type(s, "LOGIN_OK").get("session_token")

        # Vào hàng chờ
        self._send_msg(s, {"type": "FIND_MATCH", "session_token": token})
        self._recv_until_type(s, "FIND_MATCH_RESPONSE")

        # Ngắt kết nối đột ngột
        s.close()
        time.sleep(0.5)

        # Kết nối lại bằng client khác để kiểm tra xem disco có còn trong queue để ghép nhầm không
        s_other = self._create_client_connection()
        uname_other = f"other_{int(time.time())}"
        self._send_msg(s_other, {"type": "REGISTER", "username": uname_other, "password": "password123"})
        self._recv_msg(s_other)
        self._send_msg(s_other, {"type": "LOGIN", "username": uname_other, "password": "password123"})
        tok_other = self._recv_until_type(s_other, "LOGIN_OK").get("session_token")

        self._send_msg(s_other, {"type": "FIND_MATCH", "session_token": tok_other})
        res = self._recv_until_type(s_other, "FIND_MATCH_RESPONSE")
        self.assertEqual(res.get("status"), "QUEUED")

        # Đợi 1 giây, đảm bảo other không bị ghép với disco (vì disco đã disconnect)
        try:
            self._recv_until_type(s_other, "MATCH_FOUND", timeout=1.0)
            self.fail("Should not match with a disconnected client")
        except TimeoutError:
            pass  # Đúng mong đợi: client disconnected đã bị loại bỏ

        # Hủy tìm trận cho client khác
        self._send_msg(s_other, {"type": "CANCEL_FIND_MATCH", "session_token": tok_other})
        s_other.close()


if __name__ == "__main__":
    unittest.main()
