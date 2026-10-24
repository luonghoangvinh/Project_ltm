#include "auth.h"
#include "database.h"
#include <openssl/sha.h>
#include <ctype.h>
#include <stdio.h>
#include <string.h>

void hash_password(const char *password, char *output_hex) {
    if (!password || !output_hex) return;

    unsigned char hash[SHA256_DIGEST_LENGTH];
    SHA256((const unsigned char *)password, strlen(password), hash);

    for (int i = 0; i < SHA256_DIGEST_LENGTH; i++) {
        sprintf(output_hex + (i * 2), "%02x", hash[i]);
    }
    output_hex[SHA256_DIGEST_LENGTH * 2] = '\0';
}

int validate_username(const char *username) {
    if (!username) return 0;
    size_t len = strlen(username);
    if (len < USERNAME_MIN_LEN || len > USERNAME_MAX_LEN) {
        return 0;
    }
    for (size_t i = 0; i < len; i++) {
        char c = username[i];
        if (!isalnum((unsigned char)c) && c != '_') {
            return 0;
        }
    }
    return 1;
}

int validate_password(const char *password) {
    if (!password) return 0;
    size_t len = strlen(password);
    return len >= PASSWORD_MIN_LEN;
}

int register_user(const char *username, const char *password, char *err_msg, size_t err_size) {
    if (!validate_username(username)) {
        if (err_msg) {
            snprintf(err_msg, err_size, "Username must be 3-20 alphanumeric characters or underscores");
        }
        return -1;
    }

    if (!validate_password(password)) {
        if (err_msg) {
            snprintf(err_msg, err_size, "Password must be at least 6 characters");
        }
        return -1;
    }

    char hash[65];
    hash_password(password, hash);

    int rc = db_register_user(username, hash);
    if (rc != 0) {
        if (err_msg) {
            snprintf(err_msg, err_size, "Username already exists or database error");
        }
        return -1;
    }

    return 0;
}

int login_user(const char *username, const char *password, int *out_elo, char *err_msg, size_t err_size) {
    if (!username || !password || strlen(username) == 0 || strlen(password) == 0) {
        if (err_msg) {
            snprintf(err_msg, err_size, "Username and password required");
        }
        return -1;
    }

    char hash[65];
    hash_password(password, hash);

    int elo = 1200;
    int rc = db_check_credentials(username, hash, &elo);
    if (rc != 0) {
        if (err_msg) {
            snprintf(err_msg, err_size, "Invalid username or password");
        }
        return -1;
    }

    if (out_elo) {
        *out_elo = elo;
    }
    return 0;
}
