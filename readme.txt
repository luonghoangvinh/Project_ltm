Cấu trúc file dự kiến(có thể bổ sung)

server/
├── include/
│   ├── common.h
│   ├── protocol.h
│   ├── network.h
│   ├── auth.h
│   ├── session.h
│   ├── matchmaking.h
│   ├── game.h
│   ├── database.h
│   └── rating.h
│
├── src/
│   ├── main.c
│   ├── network/
│   │   ├── server.c
│   │   ├── client_handler.c
│   │   └── protocol.c
│   ├── auth/
│   │   ├── auth.c
│   │   └── session.c
│   ├── matchmaking/
│   │   └── matchmaking.c
│   ├── game/
│   │   ├── board.c
│   │   ├── ship.c
│   │   ├── game.c
│   │   └── replay.c
│   ├── database/
│   │   └── database.c
│   └── rating/
│       └── rating.c
│
├── sql/
│   └── schema.sql
├── config/
│   └── server.example.conf
├── build/
├── Makefile
└── README.md
