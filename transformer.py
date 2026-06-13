"""Transforms raw 2GIS API items into clean, structured parking records."""

import re
from datetime import datetime, timezone
from typing import Any

from district_lookup import lookup_district

_MALL_KW = re.compile(
    r"\b(ТРЦ|ТРК|ТД|торг|mall|mega|MEGA|megalopolis|апорт|forum|esentai|dostyk)",
    re.IGNORECASE,
)
_BC_KW = re.compile(r"\b(БЦ|бизнес.?центр|business.?centre|business.?center)", re.IGNORECASE)
_UNDERGROUND_KW = re.compile(r"\b(подземн|underground|многоуровн|multi.?storey)", re.IGNORECASE)
_PAID_KW = re.compile(r"(платн|оплат|pay|paid|тариф)", re.IGNORECASE)
_FREE_KW = re.compile(r"(бесплатн|free|свободн)", re.IGNORECASE)
_TARIFF_RE = re.compile(r"(\d[\d\s]*(?:₸|тг|tenge|руб)[^\n,;]{0,40})", re.IGNORECASE)

NA = "н/д"

# Address component types in priority order for building a fallback address string.
# 2GIS component types: street, building, district, city, country, etc.
_ADDR_COMPONENT_PRIORITY = [
    "street", "building", "project", "district", "living_area",
]


def _safe(d: dict, *keys, default=""):
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur if cur is not None else default


def _build_address(address_obj: dict) -> str:
    """Return a human-readable address string.

    Priority:
    1. address.name  — pre-formatted by 2GIS (most cases)
    2. Assembled from address.components (street + building number)
    3. н/д
    """
    name = (address_obj.get("name") or "").strip()
    if name:
        return name

    components = address_obj.get("components") or []
    # Build a map of type -> value from components
    comp_map: dict[str, str] = {}
    for comp in components:
        ctype = comp.get("type") or ""
        # Each component has either 'street' or 'name' as the text value
        value = (comp.get("street") or comp.get("name") or "").strip()
        if ctype and value and ctype not in comp_map:
            comp_map[ctype] = value

    # Try street + building first (most useful)
    street = comp_map.get("street", "")
    building = comp_map.get("building", "")
    if street and building:
        return f"{street}, {building}"
    if street:
        return street

    # Fall back to any component in priority order
    for ctype in _ADDR_COMPONENT_PRIORITY:
        if ctype in comp_map:
            return comp_map[ctype]

    return NA


def _format_schedule(schedule: dict) -> str:
    if not schedule:
        return NA
    if schedule.get("is_24x7"):
        return "24/7"
    days_map = {
        "Mon": "Пн", "Tue": "Вт", "Wed": "Ср",
        "Thu": "Чт", "Fri": "Пт", "Sat": "Сб", "Sun": "Вс",
    }
    parts = []
    for eng, rus in days_map.items():
        day = schedule.get(eng)
        if day and day.get("working"):
            working_hours = day.get("working_hours", [])
            if working_hours:
                times = ", ".join(
                    f"{wh.get('from', '')}–{wh.get('to', '')}" for wh in working_hours
                )
                parts.append(f"{rus} {times}")
    return "; ".join(parts) if parts else NA


def _extract_capacity(item: dict) -> str:
    cap = item.get("capacity")
    if not cap:
        return NA
    if isinstance(cap, dict):
        total = cap.get("total") or cap.get("count") or ""
        return str(total) if total else NA
    return str(cap) if str(cap).strip() else NA


def _extract_tariff_and_paid(item: dict) -> tuple[str, str]:
    tariff_text = ""
    paid_status = ""
    for group in item.get("attribute_groups", []) or []:
        for attr in group.get("attributes", []) or []:
            name = (attr.get("name") or "").lower()
            value = str(attr.get("value") or "")
            combined = f"{name} {value}"
            if "тариф" in name or "стоимость" in name or "цена" in name or "price" in name:
                tariff_text = value
            if _PAID_KW.search(combined):
                paid_status = "Платная"
            if _FREE_KW.search(combined):
                paid_status = "Бесплатная"
            tariff_match = _TARIFF_RE.search(combined)
            if tariff_match and not tariff_text:
                tariff_text = tariff_match.group(1).strip()
    name_str = item.get("name", "") or ""
    if not paid_status:
        if _FREE_KW.search(name_str):
            paid_status = "Бесплатная"
        elif _PAID_KW.search(name_str):
            paid_status = "Платная"
    return tariff_text or NA, paid_status or NA


def _infer_type(item: dict, org_name: str) -> str:
    name = (item.get("name") or "").lower()
    full_name = (item.get("full_name") or "").lower()
    rubrics = " ".join(r.get("name", "") for r in (item.get("rubrics") or [])).lower()
    combined = f"{name} {full_name} {rubrics} {org_name.lower()}"
    if _UNDERGROUND_KW.search(combined):
        return "Подземная"
    if _MALL_KW.search(combined):
        return "ТРЦ"
    if _BC_KW.search(combined):
        return "БЦ"
    address = (item.get("address") or {}).get("name", "").lower()
    if any(kw in address for kw in ("ул.", "пр.", "бул.", "пер.")):
        return "Городская"
    return "Частная"


def _build_url(item: dict) -> str:
    dgis_url = item.get("url") or ""
    if dgis_url:
        return dgis_url.replace("2gis.com", "2gis.kz").replace("2gis.ru", "2gis.kz")
    item_id = item.get("id", "")
    if item_id:
        return f"https://2gis.kz/almaty/firm/{item_id}"
    return NA


def transform(item: dict) -> dict:
    point = item.get("point") or {}
    address_obj = item.get("address") or {}
    schedule = item.get("schedule") or {}
    org = item.get("org") or {}
    org_name = org.get("name") or ""

    tariff, paid = _extract_tariff_and_paid(item)
    capacity = _extract_capacity(item)
    dgis_url = _build_url(item)

    lat = point.get("lat") or ""
    lon = point.get("lon") or ""
    coords = f"{lat}, {lon}" if lat and lon else NA

    # District: prefer 2GIS address component, fall back to polygon lookup
    address_components = address_obj.get("components") or []
    district = ""
    for comp in address_components:
        if comp.get("type") in ("district", "division"):
            district = comp.get("street") or comp.get("name") or ""
            break
    if not district and lat and lon:
        try:
            district = lookup_district(float(lat), float(lon))
        except (ValueError, TypeError):
            district = ""
    district = district or NA

    return {
        "id": str(item.get("id", "")),
        "название": item.get("name") or NA,
        "адрес": _build_address(address_obj),
        "координаты": coords,
        "ссылка_2гис": dgis_url,
        "платная": paid,
        "тариф": tariff,
        "мест_всего": capacity,
        "тип": _infer_type(item, org_name),
        "объект": org_name or NA,
        "часы_работы": _format_schedule(schedule),
        "район": district,
        "дата_сбора": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


HEADERS = [
    "id", "название", "адрес", "координаты", "ссылка_2гис",
    "платная", "тариф", "мест_всего", "тип", "объект",
    "часы_работы", "район", "дата_сбора",
]

HEADER_LABELS = [
    "ID", "Название", "Адрес", "Координаты", "Ссылка на 2ГИС",
    "Платная?", "Тариф", "Мест (всего)", "Тип", "Объект / организация",
    "Часы работы", "Район", "Дата сбора",
]
