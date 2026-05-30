CAR_TYPE_KAMAZ = "KAMAZ"
CAR_TYPE_NOT_KAMAZ = "NOT_KAMAZ"
CAR_TYPE_UNKNOWN = "UNKNOWN"
INSTANCE_2 = "INSTANCE_2"

RATING_WEIGHTS = {
    "coasting": 0.141,
    "fuel": 0.163,
    "optimal_rpm": 0.141,
    "idle": 0.054,
    "braking": 0.109,
    "anticipation": 0.163,
    "cruise_control": 0.044,
    "overspeed": 0.185,
}

KAMAZ_THRESHOLDS = {
    "fuel": {"direction": "lower_is_better", "score_thresholds": {1: 38, 2: 38, 3: 37, 4: 36, 5: 35, 6: 34, 7: 33, 8: 32, 9: 31, 10: 30}},
    "optimal_rpm": {"direction": "higher_is_better", "score_thresholds": {1: 28, 2: 28, 3: 32, 4: 36, 5: 40, 6: 44, 7: 48, 8: 52, 9: 56, 10: 60}},
    "idle": {"direction": "lower_is_better", "score_thresholds": {1: 65, 2: 65, 3: 60, 4: 55, 5: 50, 6: 45, 7: 40, 8: 35, 9: 30, 10: 25}},
    "braking": {"direction": "lower_is_better", "score_thresholds": {1: 70, 2: 70, 3: 60, 4: 50, 5: 45, 6: 40, 7: 35, 8: 22, 9: 18, 10: 14}},
    "overspeed": {"direction": "lower_is_better", "score_thresholds": {1: 18, 2: 18, 3: 17, 4: 16, 5: 15, 6: 14, 7: 13, 8: 12, 9: 11, 10: 10}},
    "coasting": {"direction": "higher_is_better", "score_thresholds": {1: 10, 2: 10, 3: 14, 4: 17, 5: 20, 6: 23, 7: 26, 8: 29, 9: 32, 10: 35}},
    "anticipation": {"direction": "lower_is_better", "score_thresholds": {1: 20, 2: 20, 3: 18, 4: 16, 5: 14, 6: 12, 7: 10, 8: 8, 9: 6, 10: 4}},
    "cruise_control": {"direction": "lower_is_better", "score_thresholds": {1: 12, 2: 12, 3: 10, 4: 8, 5: 6, 6: 5, 7: 4, 8: 3, 9: 1, 10: 0}},
}

NOT_KAMAZ_THRESHOLDS = {
    "fuel": {"direction": "lower_is_better", "score_thresholds": {1: 35, 2: 35, 3: 34, 4: 32, 5: 30, 6: 29, 7: 28, 8: 27, 9: 26, 10: 25}},
    "optimal_rpm": {"direction": "higher_is_better", "score_thresholds": {1: 28, 2: 28, 3: 32, 4: 36, 5: 40, 6: 44, 7: 48, 8: 52, 9: 56, 10: 60}},
    "idle": {"direction": "lower_is_better", "score_thresholds": {1: 65, 2: 65, 3: 60, 4: 55, 5: 50, 6: 45, 7: 40, 8: 35, 9: 30, 10: 25}},
    "braking": {"direction": "lower_is_better", "score_thresholds": {1: 70, 2: 70, 3: 60, 4: 50, 5: 45, 6: 40, 7: 35, 8: 22, 9: 18, 10: 14}},
    "overspeed": {"direction": "lower_is_better", "score_thresholds": {1: 18, 2: 18, 3: 17, 4: 16, 5: 15, 6: 14, 7: 13, 8: 12, 9: 11, 10: 10}},
    "coasting": {"direction": "higher_is_better", "score_thresholds": {1: 10, 2: 10, 3: 14, 4: 17, 5: 20, 6: 23, 7: 26, 8: 29, 9: 32, 10: 35}},
    "anticipation": {"direction": "lower_is_better", "score_thresholds": {1: 20, 2: 20, 3: 18, 4: 16, 5: 14, 6: 12, 7: 10, 8: 8, 9: 6, 10: 4}},
    "cruise_control": {"direction": "higher_is_better", "score_thresholds": {1: 4, 2: 5, 3: 6, 4: 7, 5: 8, 6: 9, 7: 10, 8: 11, 9: 12, 10: 14}},
}

UNKNOWN_THRESHOLDS = NOT_KAMAZ_THRESHOLDS
RATING_THRESHOLDS = {
    CAR_TYPE_KAMAZ: KAMAZ_THRESHOLDS,
    CAR_TYPE_NOT_KAMAZ: NOT_KAMAZ_THRESHOLDS,
    CAR_TYPE_UNKNOWN: UNKNOWN_THRESHOLDS,
}
