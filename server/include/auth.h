#ifndef AUTH_H
#define AUTH_H

#include "common.h"
#include <stddef.h>

/**
 * Compute SHA-256 hash of password.
 * output_hex must have at least 65 bytes (64 hex characters + null terminator).
 */
void hash_password(const char *password, char *output_hex);

/**
 * Validate username: 3-20 characters, alphanumeric and underscore only.
 * Returns 1 if valid, 0 otherwise.
 */
int validate_username(const char *username);

/**
 * Validate password: at least 6 characters.
 * Returns 1 if valid, 0 otherwise.
 */
int validate_password(const char *password);

/**
 * Register a new user in the database.
 * Returns 0 on success, -1 on failure (error written to err_msg).
 */
int register_user(const char *username, const char *password, char *err_msg, size_t err_size);

/**
 * Authenticate user credentials against database.
 * Populates out_elo on success.
 * Returns 0 on success, -1 on failure (error written to err_msg).
 */
int login_user(const char *username, const char *password, int *out_elo, char *err_msg, size_t err_size);

#endif /* AUTH_H */
