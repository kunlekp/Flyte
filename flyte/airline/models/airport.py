"""Airports and the directory used to resolve city names to coordinates."""

from ..utils import haversine_km


class Airport:
    def __init__(self, code, city, name, lat, lon):
        self.code = code
        self.city = city
        self.name = name
        self.lat = lat
        self.lon = lon

    def distance_to(self, other):
        return haversine_km(self.lat, self.lon, other.lat, other.lon)

    def to_dict(self):
        return {
            "code": self.code,
            "city": self.city,
            "name": self.name,
            "lat": self.lat,
            "lon": self.lon,
        }

    def __repr__(self):
        return f"Airport({self.code}, {self.city})"


class AirportDirectory:
    """Registry of known airports. Lookup works by IATA code or city name."""

    DEFAULT_AIRPORTS = [
        ("LOS", "Lagos", "Murtala Muhammed International", 6.5774, 3.3212),
        ("ABV", "Abuja", "Nnamdi Azikiwe International", 9.0068, 7.2632),
        ("PHC", "Port Harcourt", "Port Harcourt International", 5.0155, 6.9496),
        ("KAN", "Kano", "Mallam Aminu Kano International", 12.0476, 8.5246),
        ("ENU", "Enugu", "Akanu Ibiam International", 6.4743, 7.5620),
        ("CBQ", "Calabar", "Margaret Ekpo International", 4.9760, 8.3472),
        ("QOW", "Owerri", "Sam Mbakwe Airport", 5.4271, 7.2060),
        ("BNI", "Benin", "Benin Airport", 6.3170, 5.5995),
        ("ILR", "Ilorin", "Ilorin International", 8.4402, 4.4939),
        ("SKO", "Sokoto", "Sadiq Abubakar III International", 12.9163, 5.2072),
        ("MIU", "Maiduguri", "Maiduguri International", 11.8553, 13.0809),
        ("KAD", "Kaduna", "Kaduna International", 10.6960, 7.3201),
        ("JOS", "Jos", "Yakubu Gowon Airport", 9.6398, 8.8691),
        ("QUO", "Uyo", "Victor Attah International", 4.8725, 8.0930),
        ("ACC", "Accra", "Kotoka International", 5.6052, -0.1668),
    ]

    def __init__(self, airports=None):
        self._by_code = {}
        self._by_city = {}
        for row in airports or self.DEFAULT_AIRPORTS:
            self.add(Airport(*row))

    def add(self, airport):
        self._by_code[airport.code.upper()] = airport
        self._by_city[airport.city.casefold()] = airport

    def find(self, text):
        """Return the Airport for 'LOS', 'Lagos' or 'Lagos (LOS)', else None."""
        if not text:
            return None
        key = str(text).strip()
        if "(" in key and key.endswith(")"):
            key = key[key.rindex("(") + 1:-1]
        return self._by_code.get(key.upper()) or self._by_city.get(key.casefold())

    def distance_km(self, origin, destination):
        a, b = self.find(origin), self.find(destination)
        if not a or not b:
            return None
        return a.distance_to(b)

    def all(self):
        return sorted(self._by_code.values(), key=lambda a: a.city)

    def cities(self):
        return [a.city for a in self.all()]


# One shared directory is enough – airports rarely change.
AIRPORTS = AirportDirectory()
