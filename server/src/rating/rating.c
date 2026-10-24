#include "rating.h"
#include <math.h>

void calc_elo_change(int elo_a, int elo_b, double score_a, int *delta_a, int *delta_b) {
    double expected_a = 1.0 / (1.0 + pow(10.0, (double)(elo_b - elo_a) / 400.0));
    double score_b = 1.0 - score_a;
    double expected_b = 1.0 - expected_a;

    int d_a = (int)round((double)ELO_K_FACTOR * (score_a - expected_a));
    int d_b = (int)round((double)ELO_K_FACTOR * (score_b - expected_b));

    if (delta_a) *delta_a = d_a;
    if (delta_b) *delta_b = d_b;
}

int update_elo_value(int current_elo, int delta) {
    int new_elo = current_elo + delta;
    if (new_elo < ELO_MINIMUM) {
        new_elo = ELO_MINIMUM;
    }
    return new_elo;
}
