#ifndef RATING_H
#define RATING_H

#define ELO_K_FACTOR 32
#define ELO_MINIMUM 100
#define ELO_DEFAULT 1200

/**
 * Calculate ELO change for two players given score of player A.
 * score_a: 1.0 for player A win, 0.0 for player B win (A loss), 0.5 for draw.
 * Outputs delta_a and delta_b (the integer changes to add to each player's ELO).
 */
void calc_elo_change(int elo_a, int elo_b, double score_a, int *delta_a, int *delta_b);

/**
 * Apply delta to current ELO, ensuring result does not drop below ELO_MINIMUM (100).
 */
int update_elo_value(int current_elo, int delta);

#endif /* RATING_H */
