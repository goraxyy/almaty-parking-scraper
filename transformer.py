"""Transforms raw 2GIS API items into clean, structured parking records."""

import re
from datetime import datetime, timezone
from typing import Any

# Keywords used to infer parking type from name / organisation / rubrics.
_MALL_KW = re.compile(
    r"\b(ТРЦ|ТРК|ТД|торг|mall|mega|MEGA|megalopolis|апорт|forum|esentai|dostyk)",
    re.IGNORECASE,
)
_BC_KW = re.compile(r"\b(БЦ|бизнес.?центр|business.?centre|business.?center)", re.IGNORECASE)
_UNDERGROUND_KW = re.compile(r"\b(подземн|underground|многоуровн|multi.?storey)", re.IGNORECASE)
_PAID_KW = re.compile(r"(платн|оплат|pay|paid|тариф)", re.IGNORECASE)
_FREE_KW = re.compile(r"(бесплатн|free|свободн)", re.IGNORECASE)
_TARIFF_RE = re.compile(r"(\d[\d\s]*(?:₸|тг|tenge|руб)[^\n,;]{0,40})", re.IGNORECASE)


def _safe(d: dict, *keys, default=""):
    """Safely traverse nested dict."""
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur if cur is not None else default


def _format_schedule(schedule: dict) -> str:
    """Convert 2GIS schedule object to human-readable string."""
    if not schedule:
        return ""
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
    return "; ".join(parts) if parts else ""


def _extract_contacts(contact_groups: list) -> tuple[str, str]:
    """Return (phone, website) from contact_groups list."""
    phones, websites = [], []
    for group in contact_groups or []:
        for contact in group.get("contacts", []):
            ctype = contact.get("type", "")
            value = contact.get("value", "")
            if ctype == "phone" and value:
                phones.append(value)
            elif ctype in ("website", "url") and value:
                websites.append(value)
    return ", ".join(phones[:2]), websites[0] if websites else ""


def _extract_tariff_and_paid(item: dict) -> tuple[str, str]:
    """Try to extract tariff info and paid/free status from attribute groups."""
    tariff_text = ""
    paid_status = "Unknown"

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

    # Fallback: check name/description
    name_str = item.get("name", "") or ""
    if paid_status == "Unknown":
        if _FREE_KW.search(name_str):
            paid_status = "Бесплатная"
        elif _PAID_KW.search(name_str):
            paid_status = "Платная"

    return tariff_text, paid_status


def _infer_type(item: dict, org_name: str) -> str:
    """Infer parking type from rubrics, name, and parent organisation."""
    name = (item.get("name") or "").lower()
    full_name = (item.get("full_name") or "").lower()
    rubrics = " ".join(
        r.get("name", "") for r in (item.get("rubrics") or [])
    ).lower()
    combined = f"{name} {full_name} {rubrics} {org_name.lower()}"

    if _UNDERGROUND_KW.search(combined):
        return "underground"
    if _MALL_KW.search(combined):
        return "mall"
    if _BC_KW.search(combined):
        return "business_center"
    # Standalone lots near roads/streets tend to be city lots
    address = (item.get("address") or {}).get("name", "").lower()
    if any(kw in address for kw in ("ул.", "пр.", "бул.", "пер.")):
        return "city"
    return "private"


def transform(item: dict) -> dict:
    """Convert one raw 2GIS item into a clean parking record dict."""
    point = item.get("point") or {}
    address_obj = item.get("address") or {}
    schedule = item.get("schedule") or {}
    contacts = item.get("contact_groups") or []
    org = item.get("org") or {}
    org_name = org.get("name") or ""

    tariff, paid = _extract_tariff_and_paid(item)
    phone, website = _extract_contacts(contacts)

    # Build 2GIS URL: prefer API-provided url, else construct from id
    dgis_url = item.get("url") or ""
    if not dgis_url:
        item_id = item.get("id", "")
        dgis_url = f"https://2gis.kz/almaty/search/парковка?id={item_id}"

    # District from address structure
    address_components = address_obj.get("components") or []
    district = ""
    for comp in address_components:
        if comp.get("type") in ("district", "division"):
            district = comp.get("street") or comp.get("name") or ""
            break

    parking_type = _infer_type(item, org_name)

    return {
        "id": str(item.get("id", "")),
        "name": item.get("name") or "",
        "address": address_obj.get("name") or "",
        "lat": point.get("lat") or "",
        "lon": point.get("lon") or "",
        "dgis_url": dgis_url,
        "paid": paid,
        "tariff": tariff,
        "capacity": str(item.get("capacity") or ""),
        "type": parking_type,
        "belongs_to": org_name,
        "hours": _format_schedule(schedule),
        "phone": phone,
        "website": website,
        "district": district,
        "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


HEADERS = [
    "id", "name", "address", "lat", "lon", "dgis_url",
    "paid", "tariff", "capacity", "type", "belongs_to",
    "hours", "phone", "website", "district", "scraped_at",
]
