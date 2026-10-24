#include "protocol.h"
#include "cjson/cJSON.h"
#include <sys/types.h>
#include <sys/socket.h>
#include <unistd.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>

#ifndef MSG_NOSIGNAL
#define MSG_NOSIGNAL 0
#endif

void line_buffer_init(LineBuffer *lb) {
    if (!lb) return;
    lb->len = 0;
    lb->data[0] = '\0';
}

int send_message(int fd, const char *json_str) {
    if (fd < 0 || !json_str) return -1;

    size_t json_len = strlen(json_str);
    size_t total_len = json_len + 1; /* for '\n' */

    char stack_buf[4096];
    char *packet = stack_buf;
    int allocated = 0;

    if (total_len + 1 > sizeof(stack_buf)) {
        packet = (char *)malloc(total_len + 1);
        if (!packet) return -1;
        allocated = 1;
    }

    memcpy(packet, json_str, json_len);
    packet[json_len] = '\n';
    packet[total_len] = '\0';

    size_t sent = 0;
    while (sent < total_len) {
        ssize_t n = send(fd, packet + sent, total_len - sent, MSG_NOSIGNAL);
        if (n < 0) {
            if (errno == EINTR) continue;
            if (allocated) free(packet);
            return -1;
        }
        if (n == 0) {
            if (allocated) free(packet);
            return -1;
        }
        sent += (size_t)n;
    }

    if (allocated) {
        free(packet);
    }
    return 0;
}

int recv_message(int fd, LineBuffer *lb, char *out_buf, size_t maxlen) {
    if (fd < 0 || !lb || !out_buf || maxlen == 0) return -1;

    while (1) {
        /* Check if we already have a complete newline-terminated line in buffer */
        char *nl = memchr(lb->data, '\n', lb->len);
        if (nl != NULL) {
            size_t line_len = (size_t)(nl - lb->data);

            /* Check if line exceeds maxlen or MSG_MAX */
            if (line_len >= MSG_MAX || line_len >= maxlen) {
                /* Reject oversized message: drop this line */
                size_t consumed = line_len + 1;
                memmove(lb->data, lb->data + consumed, lb->len - consumed);
                lb->len -= consumed;
                lb->data[lb->len] = '\0';
                continue;
            }

            size_t copy_len = line_len;
            if (copy_len > 0 && lb->data[copy_len - 1] == '\r') {
                copy_len--;
            }

            memcpy(out_buf, lb->data, copy_len);
            out_buf[copy_len] = '\0';

            /* Shift remaining bytes in buffer */
            size_t consumed = line_len + 1;
            memmove(lb->data, lb->data + consumed, lb->len - consumed);
            lb->len -= consumed;
            lb->data[lb->len] = '\0';

            return 0; /* Successfully retrieved a message */
        }

        /* Check buffer overflow */
        if (lb->len >= sizeof(lb->data) - 1) {
            /* Line is too long and no newline found, flush buffer to prevent overflow */
            lb->len = 0;
            lb->data[0] = '\0';
            return -1;
        }

        /* Read more data from socket */
        ssize_t n = recv(fd, lb->data + lb->len, sizeof(lb->data) - 1 - lb->len, 0);
        if (n < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        if (n == 0) {
            /* Client disconnected */
            return -1;
        }

        lb->len += (size_t)n;
        lb->data[lb->len] = '\0';
    }
}

int send_error(int fd, const char *msg) {
    if (fd < 0 || !msg) return -1;
    cJSON *err_obj = cJSON_CreateObject();
    if (!err_obj) return -1;
    cJSON_AddStringToObject(err_obj, "type", "ERROR");
    cJSON_AddStringToObject(err_obj, "message", msg);
    char *s = cJSON_PrintUnformatted(err_obj);
    cJSON_Delete(err_obj);
    if (!s) return -1;
    int rc = send_message(fd, s);
    free(s);
    return rc;
}
