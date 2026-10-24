"""
Thread-safe TCP socket client for newline-delimited JSON messaging.
"""

import json
import queue
import socket
import threading
from typing import Any, Callable, Dict, List, Optional

from client.config import SERVER_HOST, SERVER_PORT


class NetworkClient:
    """Manages the TCP socket connection to the Battleship server.

    Incoming messages are read in a background daemon thread and placed into a
    thread-safe queue. Outgoing messages are sent from the main thread protected
    by a lock.
    """

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        self.host: str = host or SERVER_HOST
        self.port: int = port or SERVER_PORT
        self.socket: Optional[socket.socket] = None
        self.connected: bool = False

        self._in_queue: queue.Queue = queue.Queue()
        self._send_lock: threading.Lock = threading.Lock()
        self._recv_thread: Optional[threading.Thread] = None
        self._running: bool = False
        self.on_disconnect: Optional[Callable[[], None]] = None

    def connect(self) -> bool:
        """Establishes connection to the server and starts the receive thread.

        Returns True on success, False otherwise.
        """
        if self.connected:
            return True

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((self.host, self.port))
            self.socket.settimeout(None)  # Blocking mode with background thread
            self.connected = True
            self._running = True
            self.start_recv_thread()
            return True
        except Exception as e:
            self.connected = False
            if self.socket:
                try:
                    self.socket.close()
                except Exception:
                    pass
                self.socket = None
            return False

    def disconnect(self) -> None:
        """Closes the socket connection and stops the background thread."""
        self._running = False
        self.connected = False
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

        if self.on_disconnect:
            try:
                self.on_disconnect()
            except Exception:
                pass

    def send(self, msg_dict: Dict[str, Any]) -> bool:
        """Encodes dictionary as JSON string ending with '\\n' and sends it over TCP.

        Thread-safe using a lock. Returns True on success, False on error.
        """
        if not self.connected or not self.socket:
            return False

        try:
            payload = json.dumps(msg_dict) + "\n"
            data = payload.encode("utf-8")
            with self._send_lock:
                self.socket.sendall(data)
            return True
        except Exception:
            self._handle_disconnect()
            return False

    def start_recv_thread(self) -> None:
        """Starts the background receive thread as a daemon."""
        self._recv_thread = threading.Thread(
            target=self._recv_thread_func,
            name="NetworkRecvThread",
            daemon=True,
        )
        self._recv_thread.start()

    def _recv_thread_func(self) -> None:
        """Background thread worker that reads from the socket, extracts

        newline-delimited JSON chunks, and enqueues parsed dictionaries.
        """
        buffer = ""
        while self._running and self.connected and self.socket:
            try:
                data = self.socket.recv(4096)
                if not data:
                    # Connection cleanly closed by server
                    break
                buffer += data.decode("utf-8", errors="replace")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        parsed = json.loads(line)
                        if isinstance(parsed, dict):
                            self._in_queue.put(parsed)
                    except json.JSONDecodeError:
                        # Skip malformed line
                        pass
            except Exception:
                break

        if self._running:
            self._handle_disconnect()

    def _handle_disconnect(self) -> None:
        """Internal cleanup when socket breaks."""
        was_connected = self.connected
        self.connected = False
        self._running = False
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

        if was_connected:
            self._in_queue.put({"type": "DISCONNECTED"})
            if self.on_disconnect:
                try:
                    self.on_disconnect()
                except Exception:
                    pass

    def get_messages(self) -> List[Dict[str, Any]]:
        """Drains all available messages from the queue and returns them as a list."""
        messages: List[Dict[str, Any]] = []
        while not self._in_queue.empty():
            try:
                msg = self._in_queue.get_nowait()
                messages.append(msg)
                self._in_queue.task_done()
            except queue.Empty:
                break
        return messages
