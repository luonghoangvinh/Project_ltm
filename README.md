# Battleship Online 1v1 — TCP Client/Server (C & Python/Pygame)

Đồ án môn Lập trình mạng: Game đối kháng Battleship trực tuyến 2 người chơi qua mạng TCP Socket với mô hình Client-Server.

- **Server:** Ngôn ngữ C (POSIX TCP Sockets, đa luồng pthreads, SQLite3, bảo mật mật khẩu SHA-256).
- **Client:** Python 3 + Pygame (Giao diện 1280x720, non-blocking network thread, hỗ trợ cả Windows & Linux).
- **Giao thức:** TCP stream với thông điệp JSON kết thúc bằng dấu xuống dòng (`\n`).

---

## 1. Yêu cầu môi trường (Prerequisites)

### A. Đối với Server (chạy trên Linux / Ubuntu 22.04 / WSL):
- GCC compiler, GNU Make
- Thư viện phát triển SQLite3 và OpenSSL (`libsqlite3-dev`, `libssl-dev`)

### B. Đối với Client (chạy trên Windows hoặc Ubuntu):
- Python 3.8 trở lên
- Thư viện Pygame (`pygame>=2.0.0`)

---

## 2. Hướng dẫn cài đặt sau khi `git clone`

### Bước 1: Clone repository về máy
```bash
git clone <URL_REPO_CUA_BAN>
cd project_ltm
```

---

### Bước 2: Build & Chạy Server C (Trên Ubuntu / WSL)

1. **Cài đặt các gói phụ thuộc (chỉ cần chạy 1 lần):**
   ```bash
   sudo apt-get update
   sudo apt-get install -y gcc make libsqlite3-dev libssl-dev
   ```

2. **Biên dịch Server:**
   *(Thư viện cJSON và SQLite headers đã được đính kèm sẵn trong repo, chỉ cần chạy `make`):*
   ```bash
   cd server
   make
   ```
   *File thực thi sẽ được tạo tại: `server/build/battleship_server`.*

3. **Khởi chạy Server:**
   ```bash
   ./build/battleship_server --port 8888
   ```
   Server sẽ lắng nghe kết nối tại cổng TCP `8888` (mặc định) và tự khởi tạo database `battleship.db`.

---

### Bước 3: Cài đặt & Chạy Client (Python / Pygame)

#### Cách A: Chạy trên Windows (Khuyên dùng để có giao diện mượt nhất)
1. Mở **PowerShell** hoặc **Command Prompt** tại thư mục `project_ltm`.
2. Cài đặt thư viện:
   ```powershell
   pip install pygame
   ```
3. Chạy Client:
   - Nếu Server chạy cùng máy (hoặc qua WSL):
     ```powershell
     python run_client.py
     ```
   - Nếu kết nối tới máy chủ từ xa qua mạng LAN/Internet:
     ```powershell
     python run_client.py --host <IP_CUA_SERVER> --port 8888
     ```

#### Cách B: Chạy trên Ubuntu / WSLg (Linux)
1. Mở Terminal tại thư mục `project_ltm`.
2. Cài đặt thư viện:
   ```bash
   sudo apt-get install -y python3-pygame
   # hoặc: pip3 install pygame --break-system-packages
   ```
3. Chạy Client:
   ```bash
   python3 run_client.py --host 127.0.0.1 --port 8888
   ```

---

## 3. Kịch bản chơi thử 2 người (1-1)

Để bắt đầu một trận đấu, cần mở **2 cửa sổ Client**:

1. **Cửa sổ Client 1:**
   - Bấm **Register** $\rightarrow$ Tạo tài khoản người chơi 1 (ví dụ: `player1` / `123456`).
   - Đăng nhập vào phòng chờ (**Lobby**).

2. **Cửa sổ Client 2:**
   - Bấm **Register** $\rightarrow$ Tạo tài khoản người chơi 2 (ví dụ: `player2` / `123456`).
   - Đăng nhập vào phòng chờ (**Lobby**).

3. **Thách đấu (Challenge):**
   - Tại màn hình Lobby, người chơi 1 sẽ nhìn thấy người chơi 2 với nút xanh **`[ Challenge ]`**.
   - Bấm **Challenge** $\rightarrow$ Màn hình người chơi 2 sẽ hiện popup xác nhận.
   - Người chơi 2 bấm **`[ Accept ]`**.

4. **Đặt tàu (Fleet Deployment):**
   - Cả hai được chuyển vào màn hình đặt 5 tàu (kích thước 2, 3, 3, 4, 5).
   - Chọn tàu bên phải $\rightarrow$ Click lên bàn cờ để đặt.
   - Nhấn phím **`R`** để xoay tàu (Ngang / Dọc).
   - Hoặc bấm nút **`Randomize`** để xếp nhanh hợp lệ.
   - Khi đã đặt đủ 5 tàu $\rightarrow$ Bấm **`[ READY FOR BATTLE ]`**.

5. **Chiến đấu (Game Arena):**
   - Bàn cờ bên trái: Hạm đội của bạn (hiển thị vị trí tàu, đạn địch trúng/trượt).
   - Bàn cờ bên phải: Radar đối thủ (chỉ hiển thị đạn đã bắn trúng/trượt, không lộ vị trí tàu bí mật).
   - Khi tới lượt (**YOUR TURN**) $\rightarrow$ Click vào ô trên bàn cờ bên phải để khai hỏa.
   - Khi đánh chìm toàn bộ hạm đội đối phương $\rightarrow$ Kết thúc trận, hệ thống tự động cập nhật điểm **ELO** và lưu lại lịch sử di chuyển vào Database.

6. **Tính năng mở rộng:**
   - Xin hòa (**Offer Draw**) & Đầu hàng (**Surrender**).
   - Xem lịch sử các trận đấu đã chơi (**Match History**).
   - Phát lại từng lượt bắn của ván đấu cũ (**Move Replay**).

---

## 4. Chơi qua mạng LAN giữa 2 máy khác nhau

1. **Trên Máy Server (Ubuntu):**
   - Lấy địa chỉ IP mạng LAN: `ip a` (ví dụ: `192.168.1.50`).
   - Mở port firewall (nếu có bật UFW):
     ```bash
     sudo ufw allow 8888/tcp
     ```
   - Chạy server:
     ```bash
     cd server && ./build/battleship_server --port 8888
     ```

2. **Trên Máy Client 1 & Client 2:**
   - Kết nối trực tiếp tới IP của máy server:
     ```bash
     python run_client.py --host 192.168.1.50 --port 8888
     ```

---

## 5. Cấu trúc mã nguồn

```
project_ltm/
├── run_client.py                  # Entrypoint launcher cho Client
├── README.md                      # Hướng dẫn build và chạy chi tiết
├── server/                        # Server viết bằng C
│   ├── Makefile                   # Script biên dịch GCC
│   ├── sql/schema.sql             # Schema SQLite (users, matches, moves)
│   ├── include/                   # Header files (.h)
│   │   ├── common.h, protocol.h, network.h, auth.h, session.h,
│   │   ├── matchmaking.h, game.h, database.h, rating.h
│   │   ├── cjson/cJSON.h          # Thư viện cJSON được bundle sẵn
│   │   └── sqlite3.h              # Header SQLite được bundle sẵn
│   └── src/                       # Mã nguồn thực thi (.c)
│       ├── main.c                 # Khởi động server, xử lý signal shutdown
│       ├── network/               # Sockets TCP, stream buffer tách dòng '\n'
│       ├── auth/                  # Đăng ký, đăng nhập, băm mật khẩu SHA-256
│       ├── matchmaking/           # Quản lý lời mời thách đấu (UUID match_id)
│       ├── game/                  # Bàn cờ 10x10, đặt tàu, lượt bắn, replay
│       ├── database/              # Truy vấn SQLite (Prepared statements)
│       └── rating/                # Công thức tính điểm ELO (K=32)
└── client/                        # Client viết bằng Python/Pygame
    ├── config.py                  # Cấu hình IP/Port, màu sắc, hạm đội
    ├── network.py                 # Thread-safe TCP client, luồng nhận ngầm
    ├── game_state.py              # Quản lý trạng thái bàn cờ, phiên làm việc
    ├── main.py                    # Vòng lặp render Pygame 60 FPS
    └── screens/                   # Các màn hình tương tác
        ├── base_screen.py         # UI base: Text, Button, Dialog, Grid
        ├── login.py, register.py  # Đăng nhập, Đăng ký
        ├── lobby.py               # Sảnh danh sách người chơi, thách đấu
        ├── place_ships.py         # Đặt tàu xoay ngang/dọc, kiểm tra va chạm
        ├── game.py                # Màn hình chiến đấu 2 bàn cờ, nhật ký đạn
        ├── result.py              # Màn hình kết quả thắng/thua, biến động ELO
        └── history.py, replay.py  # Xem lịch sử trận và phát lại ván đấu
```
