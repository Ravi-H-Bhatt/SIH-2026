"""
Geographic reference data for the operations map.

Maps ISO 3166-1 alpha-3 (and common alpha-2) country codes to approximate
country centroids. These are deliberately coarse: a passport's issuing country
is not an address, so the UI labels these markers "country of issue" rather
than implying a precise residence geocode.
"""

from typing import Dict, Optional, Tuple

# ISO-3 -> (latitude, longitude) country centroid
COUNTRY_CENTROIDS: Dict[str, Tuple[float, float]] = {
    "AFG": (33.9391, 67.7100),
    "ARE": (23.4241, 53.8478),
    "ARG": (-38.4161, -63.6167),
    "AUS": (-25.2744, 133.7751),
    "AUT": (47.5162, 14.5501),
    "BGD": (23.6850, 90.3563),
    "BEL": (50.5039, 4.4699),
    "BRA": (-14.2350, -51.9253),
    "BTN": (27.5142, 90.4336),
    "CAN": (56.1304, -106.3468),
    "CHE": (46.8182, 8.2275),
    "CHN": (35.8617, 104.1954),
    "DEU": (51.1657, 10.4515),
    "DNK": (56.2639, 9.5018),
    "EGY": (26.8206, 30.8025),
    "ESP": (40.4637, -3.7492),
    "FRA": (46.2276, 2.2137),
    "GBR": (55.3781, -3.4360),
    "IDN": (-0.7893, 113.9213),
    "IND": (20.5937, 78.9629),
    "IRN": (32.4279, 53.6880),
    "IRQ": (33.2232, 43.6793),
    "ITA": (41.8719, 12.5674),
    "JPN": (36.2048, 138.2529),
    "KEN": (-0.0236, 37.9062),
    "KOR": (35.9078, 127.7669),
    "LKA": (7.8731, 80.7718),
    "MMR": (21.9162, 95.9560),
    "MYS": (4.2105, 101.9758),
    "NGA": (9.0820, 8.6753),
    "NLD": (52.1326, 5.2913),
    "NPL": (28.3949, 84.1240),
    "NZL": (-40.9006, 174.8860),
    "PAK": (30.3753, 69.3451),
    "PHL": (12.8797, 121.7740),
    "POL": (51.9194, 19.1451),
    "QAT": (25.3548, 51.1839),
    "RUS": (61.5240, 105.3188),
    "SAU": (23.8859, 45.0792),
    "SGP": (1.3521, 103.8198),
    "SWE": (60.1282, 18.6435),
    "THA": (15.8700, 100.9925),
    "TUR": (38.9637, 35.2433),
    "UKR": (48.3794, 31.1656),
    "USA": (37.0902, -95.7129),
    "VNM": (14.0583, 108.2772),
    "ZAF": (-30.5595, 22.9375),
}

# Common alpha-2 codes seen on non-ICAO documents
ALPHA2_TO_ALPHA3: Dict[str, str] = {
    "AE": "ARE", "AT": "AUT", "AU": "AUS", "BD": "BGD", "BE": "BEL", "BR": "BRA",
    "CA": "CAN", "CH": "CHE", "CN": "CHN", "DE": "DEU", "DK": "DNK", "EG": "EGY",
    "ES": "ESP", "FR": "FRA", "GB": "GBR", "ID": "IDN", "IN": "IND", "IR": "IRN",
    "IT": "ITA", "JP": "JPN", "KE": "KEN", "KR": "KOR", "LK": "LKA", "MY": "MYS",
    "NG": "NGA", "NL": "NLD", "NP": "NPL", "NZ": "NZL", "PH": "PHL", "PK": "PAK",
    "PL": "POL", "QA": "QAT", "RU": "RUS", "SA": "SAU", "SE": "SWE", "SG": "SGP",
    "TH": "THA", "TR": "TUR", "UA": "UKR", "UK": "GBR", "US": "USA", "VN": "VNM",
    "ZA": "ZAF",
}

COUNTRY_NAMES: Dict[str, str] = {
    "ARE": "United Arab Emirates", "AUS": "Australia", "BGD": "Bangladesh",
    "CAN": "Canada", "CHN": "China", "DEU": "Germany", "FRA": "France",
    "GBR": "United Kingdom", "IDN": "Indonesia", "IND": "India", "IRN": "Iran",
    "ITA": "Italy", "JPN": "Japan", "LKA": "Sri Lanka", "MMR": "Myanmar",
    "MYS": "Malaysia", "NPL": "Nepal", "PAK": "Pakistan", "PHL": "Philippines",
    "RUS": "Russia", "SAU": "Saudi Arabia", "SGP": "Singapore", "THA": "Thailand",
    "USA": "United States", "VNM": "Vietnam", "ZAF": "South Africa",
}


# Nationality adjectives as printed in the visual inspection zone. Passports
# state nationality in words ("INDIAN", "BRITISH CITIZEN"), not as ISO codes, so
# resolving the code from the document requires this mapping.
#
# Without it the OCR layer defaulted nationality and issuing_country to "IND"
# for every non-MRZ document, which meant a US or Thai passport read via the
# visual path was recorded as Indian — and then geolocated to India on the
# operations map.
NATIONALITY_TO_ALPHA3: Dict[str, str] = {
    "AFGHAN": "AFG", "EMIRATI": "ARE", "ARGENTINE": "ARG", "ARGENTINIAN": "ARG",
    "AUSTRALIAN": "AUS", "AUSTRIAN": "AUT", "BANGLADESHI": "BGD",
    "BELGIAN": "BEL", "BRAZILIAN": "BRA", "BHUTANESE": "BTN",
    "CANADIAN": "CAN", "SWISS": "CHE", "CHINESE": "CHN", "GERMAN": "DEU",
    "DANISH": "DNK", "EGYPTIAN": "EGY", "SPANISH": "ESP", "FRENCH": "FRA",
    "BRITISH": "GBR", "BRITISH CITIZEN": "GBR", "INDONESIAN": "IDN",
    "INDIAN": "IND", "IRANIAN": "IRN", "IRAQI": "IRQ", "ITALIAN": "ITA",
    "JAPANESE": "JPN", "KENYAN": "KEN", "KOREAN": "KOR",
    "SRI LANKAN": "LKA", "SRILANKAN": "LKA", "BURMESE": "MMR",
    "MYANMAR": "MMR", "MALAYSIAN": "MYS", "NIGERIAN": "NGA", "DUTCH": "NLD",
    "NETHERLANDS": "NLD", "NEPALESE": "NPL", "NEPALI": "NPL",
    "NEW ZEALANDER": "NZL", "PAKISTANI": "PAK", "FILIPINO": "PHL",
    "PHILIPPINE": "PHL", "POLISH": "POL", "QATARI": "QAT", "RUSSIAN": "RUS",
    "SAUDI": "SAU", "SAUDI ARABIAN": "SAU", "SINGAPOREAN": "SGP",
    "SWEDISH": "SWE", "THAI": "THA", "TURKISH": "TUR", "UKRAINIAN": "UKR",
    "AMERICAN": "USA", "VIETNAMESE": "VNM", "SOUTH AFRICAN": "ZAF",
}

# Country name -> ISO-3, inverted from COUNTRY_NAMES plus common variants.
NAME_TO_ALPHA3: Dict[str, str] = {name.upper(): code for code, name in COUNTRY_NAMES.items()}
NAME_TO_ALPHA3.update({
    "REPUBLIC OF INDIA": "IND",
    "BHARAT": "IND",
    "UNITED STATES OF AMERICA": "USA",
    "GREAT BRITAIN": "GBR",
    "UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND": "GBR",
    "KOREA": "KOR",
    "REPUBLIC OF KOREA": "KOR",
    "UAE": "ARE",
    "KINGDOM OF SAUDI ARABIA": "SAU",
    "RUSSIAN FEDERATION": "RUS",
    "SOCIALIST REPUBLIC OF VIET NAM": "VNM",
    "VIET NAM": "VNM",
})


class GeoReference:
    def normalize(self, code: Optional[str]) -> Optional[str]:
        if not code:
            return None
        clean = str(code).strip().upper().replace("<", "")
        if len(clean) == 2:
            clean = ALPHA2_TO_ALPHA3.get(clean, clean)
        return clean if clean in COUNTRY_CENTROIDS else None

    def resolve_from_text(self, text: Optional[str]) -> Optional[str]:
        """
        Best-effort ISO-3 country code from free document text.

        Tries, in order: an explicit alpha-3 code, a nationality adjective, then
        a country name. Returns None when nothing matches — the caller must
        treat that as "unknown", never as a default country.
        """
        if not text:
            return None

        upper = str(text).upper()

        # Explicit alpha-3 already present and known.
        direct = self.normalize(text.strip())
        if direct:
            return direct

        # Longest match first so "SOUTH AFRICAN" wins over "AFRICAN" fragments
        # and "SAUDI ARABIAN" over "SAUDI".
        for adjective in sorted(NATIONALITY_TO_ALPHA3, key=len, reverse=True):
            if adjective in upper:
                return NATIONALITY_TO_ALPHA3[adjective]

        for name in sorted(NAME_TO_ALPHA3, key=len, reverse=True):
            if name in upper:
                return NAME_TO_ALPHA3[name]

        return None

    def coordinates_for_country(self, code: Optional[str]) -> Optional[Tuple[float, float]]:
        """Returns the country centroid, or None for an unknown/unreadable code."""
        iso3 = self.normalize(code)
        return COUNTRY_CENTROIDS.get(iso3) if iso3 else None

    def country_name(self, code: Optional[str]) -> Optional[str]:
        iso3 = self.normalize(code)
        if not iso3:
            return None
        return COUNTRY_NAMES.get(iso3, iso3)


geo_reference = GeoReference()
