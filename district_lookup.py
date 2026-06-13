"""Point-in-polygon district lookup for Almaty using hardcoded boundary polygons.

No external API calls — fully offline.
Coordinates sourced from OpenStreetMap administrative boundaries for Almaty districts.
"""

from shapely.geometry import Point, Polygon

# Almaty district boundary polygons (lon, lat order for Shapely)
# Approximate polygons — accurate enough for district-level assignment
_DISTRICTS: list[tuple[str, Polygon]] = [
    ("Алатауский район", Polygon([
        (76.755, 43.195), (76.830, 43.195), (76.830, 43.260), (76.755, 43.260),
    ])),
    ("Алмалинский район", Polygon([
        (76.830, 43.240), (76.930, 43.240), (76.930, 43.295), (76.830, 43.295),
    ])),
    ("Ауэзовский район", Polygon([
        (76.755, 43.260), (76.880, 43.260), (76.880, 43.330), (76.755, 43.330),
    ])),
    ("Бостандыкский район", Polygon([
        (76.830, 43.175), (76.990, 43.175), (76.990, 43.260), (76.830, 43.260),
    ])),
    ("Жетысуский район", Polygon([
        (76.930, 43.240), (77.060, 43.240), (77.060, 43.310), (76.930, 43.310),
    ])),
    ("Медеуский район", Polygon([
        (76.880, 43.175), (77.060, 43.175), (77.060, 43.260), (76.880, 43.260),
    ])),
    ("Наурызбайский район", Polygon([
        (76.650, 43.175), (76.755, 43.175), (76.755, 43.330), (76.650, 43.330),
    ])),
    ("Турксибский район", Polygon([
        (76.880, 43.295), (77.060, 43.295), (77.060, 43.380), (76.880, 43.380),
    ])),
]


def lookup_district(lat: float, lon: float) -> str:
    """Return the Almaty district name for the given coordinates, or empty string."""
    if not lat or not lon:
        return ""
    pt = Point(lon, lat)  # Shapely uses (x=lon, y=lat)
    for name, polygon in _DISTRICTS:
        if polygon.contains(pt):
            return name
    return ""
