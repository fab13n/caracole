import re
from typing import Tuple

from openlocationcode import openlocationcode as olc
from unidecode import unidecode

from .models import Ville

NON_LETTER = re.compile("[^a-z]+")


def to_code_area(plus_code: str) -> olc.CodeArea:
    """
    Convert a Google-style code (short OLC + space + city name) into an `openlocationcode.CodeArea`.
    Raise a `ValueError` if the city name is unknown or ambiguous. Attempts are made to be
    forgetful about approximate city names.
    """
    if olc.isValid(plus_code) and olc.isFull(plus_code):
        return olc.decode(plus_code)
    short, city_name = plus_code.split(maxsplit=1)
    if olc.isValid(plus_code):
        raise ValueError('Code invalide')
    simple_name = NON_LETTER.sub(" ", unidecode(city_name.lower()))
    try:
        city: Ville = Ville.objects.get(nom_simple__contains=simple_name)
    except Ville.DoesNotExist:
        raise ValueError("Ville inconnue")
    except Ville.MultipleObjectsReturned:
        raise ValueError("Ville ambigue")
    long = olc.recoverNearest(short, city.latitude_deg, city.longitude_deg)
    return olc.decode(long)


def to_lat_lon(plus_code: str) -> Tuple[float, float]:
    """
    Convert a Google-style code (short OLC + space + city name) into a latitude + longitude pair.
    Raise a `ValueError` if the city name is unknown or ambiguous. Attempts are made to be
    forgetful about approximate city names.
    """
    area = to_code_area(plus_code)
    return area.latitudeCenter, area.longitudeCenter
