from pravah import constants as C


def test_weights_sum_to_one():
    assert abs(sum(C.DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9


def test_officer_tiers():
    assert C.officers_for(98) == 3
    assert C.officers_for(70) == 2
    assert C.officers_for(10) == 1


def test_evening_window_is_3pm_to_9pm():
    assert C.EVENING_HOURS == (15, 16, 17, 18, 19, 20, 21)
