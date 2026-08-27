"""Spanish provinces (INE two-digit codes) grouped by autonomous community.

This list is stable reference data and is intentionally code, not a table.
"""

import re
from dataclasses import dataclass

PROVINCE_CODE_PATTERN = re.compile(r"^(0[1-9]|[1-4][0-9]|5[0-2])$")


@dataclass(frozen=True)
class Province:
    code: str
    name: str
    community: str


PROVINCES: tuple[Province, ...] = (
    Province("01", "Álava", "País Vasco"),
    Province("02", "Albacete", "Castilla-La Mancha"),
    Province("03", "Alicante", "Comunidad Valenciana"),
    Province("04", "Almería", "Andalucía"),
    Province("05", "Ávila", "Castilla y León"),
    Province("06", "Badajoz", "Extremadura"),
    Province("07", "Illes Balears", "Illes Balears"),
    Province("08", "Barcelona", "Cataluña"),
    Province("09", "Burgos", "Castilla y León"),
    Province("10", "Cáceres", "Extremadura"),
    Province("11", "Cádiz", "Andalucía"),
    Province("12", "Castellón", "Comunidad Valenciana"),
    Province("13", "Ciudad Real", "Castilla-La Mancha"),
    Province("14", "Córdoba", "Andalucía"),
    Province("15", "A Coruña", "Galicia"),
    Province("16", "Cuenca", "Castilla-La Mancha"),
    Province("17", "Girona", "Cataluña"),
    Province("18", "Granada", "Andalucía"),
    Province("19", "Guadalajara", "Castilla-La Mancha"),
    Province("20", "Gipuzkoa", "País Vasco"),
    Province("21", "Huelva", "Andalucía"),
    Province("22", "Huesca", "Aragón"),
    Province("23", "Jaén", "Andalucía"),
    Province("24", "León", "Castilla y León"),
    Province("25", "Lleida", "Cataluña"),
    Province("26", "La Rioja", "La Rioja"),
    Province("27", "Lugo", "Galicia"),
    Province("28", "Madrid", "Comunidad de Madrid"),
    Province("29", "Málaga", "Andalucía"),
    Province("30", "Murcia", "Región de Murcia"),
    Province("31", "Navarra", "Comunidad Foral de Navarra"),
    Province("32", "Ourense", "Galicia"),
    Province("33", "Asturias", "Principado de Asturias"),
    Province("34", "Palencia", "Castilla y León"),
    Province("35", "Las Palmas", "Canarias"),
    Province("36", "Pontevedra", "Galicia"),
    Province("37", "Salamanca", "Castilla y León"),
    Province("38", "Santa Cruz de Tenerife", "Canarias"),
    Province("39", "Cantabria", "Cantabria"),
    Province("40", "Segovia", "Castilla y León"),
    Province("41", "Sevilla", "Andalucía"),
    Province("42", "Soria", "Castilla y León"),
    Province("43", "Tarragona", "Cataluña"),
    Province("44", "Teruel", "Aragón"),
    Province("45", "Toledo", "Castilla-La Mancha"),
    Province("46", "Valencia", "Comunidad Valenciana"),
    Province("47", "Valladolid", "Castilla y León"),
    Province("48", "Bizkaia", "País Vasco"),
    Province("49", "Zamora", "Castilla y León"),
    Province("50", "Zaragoza", "Aragón"),
    Province("51", "Ceuta", "Ceuta"),
    Province("52", "Melilla", "Melilla"),
)

PROVINCES_BY_CODE: dict[str, Province] = {province.code: province for province in PROVINCES}


def is_valid_province_code(code: str) -> bool:
    return code in PROVINCES_BY_CODE
