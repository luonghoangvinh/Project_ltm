#ifndef PROTOCOL_H
#define PROTOCOL_H

#include "common.h"
#include <stddef.h>

typedef struct {
    char data[MSG_MAX * 2];
    size_t len;
} LineBuffer;

void line_buffer_init(LineBuffer *lb);

/**
 * Send a null-terminated JSON string to socket fd.
 * Automatically appends newline '\n' and loops send() until all bytes are sent.
 * Returns 0 on success, -1 on failure/disconnect.
 */
int send_message(int fd, const char *json_str);

/**
 * Read from socket fd into per-client LineBuffer and extract next complete line (delimited by \n).
 * The extracted line in out_buf will be null-terminated without \r or \n.
 * Returns:
 *   1 if a complete message was extracted into out_buf
 *   0 if more data is needed (read again)
 *  -1 on client disconnect or read error
 */
int recv_message(int fd, LineBuffer *lb, char *out_buf, size_t maxlen);

/**
 * Utility to send formatted JSON error message: {"type": "ERROR", "message": msg}
 */
int send_error(int fd, const char *msg);

#endif /* PROTOCOL_H */
