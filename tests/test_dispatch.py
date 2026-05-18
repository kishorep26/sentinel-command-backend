import math
import pytest
from app.services.dispatch import haversine, INCIDENT_TYPE_MAP


def test_haversine_same_point():
    assert haversine(40.7128, -74.006, 40.7128, -74.006) == pytest.approx(0.0, abs=1e-6)


def test_haversine_known_distance():
    # NYC to LA ≈ 3940 km
    dist = haversine(40.7128, -74.006, 34.0522, -118.2437)
    assert 3900 < dist < 4000


def test_incident_type_map_coverage():
    assert INCIDENT_TYPE_MAP["fire"] == "fire"
    assert INCIDENT_TYPE_MAP["medical"] == "medical"
    assert INCIDENT_TYPE_MAP["accident"] == "police"
    assert INCIDENT_TYPE_MAP["robbery"] == "police"


def test_keyword_classify_fire():
    from app.services.ai import keyword_classify
    assert keyword_classify("massive blaze engulfing the warehouse") == "fire"


def test_keyword_classify_medical():
    from app.services.ai import keyword_classify
    assert keyword_classify("patient collapsed and is unconscious") == "medical"


def test_keyword_classify_accident():
    from app.services.ai import keyword_classify
    assert keyword_classify("car crash on highway 101") == "accident"


def test_keyword_classify_default():
    from app.services.ai import keyword_classify
    assert keyword_classify("suspicious person in the park") == "police"
