CC ?= gcc
CFLAGS ?= -Wall -Wextra -O2 -std=c99 -D_POSIX_C_SOURCE=200809L -D_DEFAULT_SOURCE -Iinclude -Iinclude/cjson
LDFLAGS ?= -pthread -lsqlite3 -lcrypto -lm

SRC_DIR = src
BUILD_DIR = build
INCLUDE_DIR = include
CJSON_DIR = $(INCLUDE_DIR)/cjson

SRCS = \
    $(SRC_DIR)/main.c \
    $(SRC_DIR)/network/server.c \
    $(SRC_DIR)/network/client_handler.c \
    $(SRC_DIR)/network/protocol.c \
    $(SRC_DIR)/auth/auth.c \
    $(SRC_DIR)/auth/session.c \
    $(SRC_DIR)/matchmaking/matchmaking.c \
    $(SRC_DIR)/game/board.c \
    $(SRC_DIR)/game/ship.c \
    $(SRC_DIR)/game/game.c \
    $(SRC_DIR)/game/replay.c \
    $(SRC_DIR)/database/database.c \
    $(SRC_DIR)/rating/rating.c \
    $(CJSON_DIR)/cJSON.c

OBJS = $(SRCS:%.c=$(BUILD_DIR)/%.o)
TARGET = $(BUILD_DIR)/battleship_server

.PHONY: all clean run deps dirs

all: dirs $(TARGET)

dirs:
	@mkdir -p $(BUILD_DIR)
	@mkdir -p $(BUILD_DIR)/$(SRC_DIR)/network
	@mkdir -p $(BUILD_DIR)/$(SRC_DIR)/auth
	@mkdir -p $(BUILD_DIR)/$(SRC_DIR)/matchmaking
	@mkdir -p $(BUILD_DIR)/$(SRC_DIR)/game
	@mkdir -p $(BUILD_DIR)/$(SRC_DIR)/database
	@mkdir -p $(BUILD_DIR)/$(SRC_DIR)/rating
	@mkdir -p $(BUILD_DIR)/$(CJSON_DIR)

deps:
	@mkdir -p $(CJSON_DIR)
	@if [ ! -f $(CJSON_DIR)/cJSON.h ]; then \
		echo "Downloading cJSON.h..."; \
		curl -sSL https://raw.githubusercontent.com/DaveGamble/cJSON/master/cJSON.h -o $(CJSON_DIR)/cJSON.h; \
	fi
	@if [ ! -f $(CJSON_DIR)/cJSON.c ]; then \
		echo "Downloading cJSON.c..."; \
		curl -sSL https://raw.githubusercontent.com/DaveGamble/cJSON/master/cJSON.c -o $(CJSON_DIR)/cJSON.c; \
	fi

$(TARGET): $(OBJS)
	$(CC) $(OBJS) -o $@ $(LDFLAGS)
	@echo "Build complete: $(TARGET)"

$(BUILD_DIR)/%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -rf $(BUILD_DIR)
	@echo "Clean complete."

run: all
	./$(TARGET) --port 8888 --db battleship.db
