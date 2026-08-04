"""Load official contact fields from GIAS Edubase CSV."""

from __future__ import annotations

import csv
import io
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from school_capture.contact_models import ContactEntry

EDUBASE_BASE = "https://ea-edubase-api-prod.azurewebsites.net/edubase/downloads/public/"
DEFAULT_CACHE = Path(".cache/edubase/edubasealldata.csv")


def ensure_edubase(cache_path: Path = DEFAULT_CACHE) -> Path:
    if cache_path.exists() and cache_path.stat().st_size > 1_000_000:
        return cache_path
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    last_err: Exception | None = None
    for i in range(14):
        d = (date.today() - timedelta(days=i)).strftime("%Y%m%d")
        url = f"{EDUBASE_BASE}edubasealldata{d}.csv"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SchoolDataCrawler/0.1"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                cache_path.write_bytes(resp.read())
            return cache_path
        except Exception as exc:  # noqa: BLE001
            last_err = exc
    raise RuntimeError(f"Could not download Edubase CSV: {last_err}")


def _decode_csv(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise RuntimeError("Could not decode Edubase CSV")


def _head_name(row: dict[str, str]) -> str | None:
    parts = [
        (row.get("HeadTitle") or "").strip(),
        (row.get("HeadFirstName") or "").strip(),
        (row.get("HeadLastName") or "").strip(),
    ]
    name = " ".join(p for p in parts if p)
    return name or None


def _postal_address(row: dict[str, str]) -> tuple[str | None, str | None, str | None]:
    parts = [
        (row.get("Street") or "").strip(),
        (row.get("Locality") or "").strip(),
        (row.get("Address3") or "").strip(),
        (row.get("Town") or "").strip(),
        (row.get("County (name)") or row.get("County") or "").strip(),
    ]
    address = ", ".join(p for p in parts if p)
    town = (row.get("Town") or "").strip() or None
    postcode = (row.get("Postcode") or "").strip() or None
    return address or None, town, postcode


def load_gias_contacts_by_urn(
    urns: set[str] | None = None,
    *,
    cache_path: Path = DEFAULT_CACHE,
) -> dict[str, list[ContactEntry]]:
    path = ensure_edubase(cache_path)
    text = _decode_csv(path.read_bytes())
    reader = csv.DictReader(io.StringIO(text))
    out: dict[str, list[ContactEntry]] = {}
    gias_url_tpl = (
        "https://www.get-information-schools.service.gov.uk/"
        "Establishments/Establishment/Details/{urn}"
    )
    for row in reader:
        urn = str(row.get("URN") or "").strip()
        if not urn or (urns is not None and urn not in urns):
            continue
        source_url = gias_url_tpl.format(urn=urn)
        captured = date.today().isoformat()
        entries: list[ContactEntry] = []

        address, town, postcode = _postal_address(row)
        if address or postcode:
            entries.append(
                ContactEntry(
                    role="office",
                    label="Postal address",
                    address=address,
                    town=town,
                    postcode=postcode,
                    sourceType="gias",
                    sourceUrl=source_url,
                    capturedAt=captured,
                )
            )

        phone = (row.get("TelephoneNum") or "").strip()
        if phone:
            entries.append(
                ContactEntry(
                    role="office",
                    label="Telephone",
                    phone=phone,
                    sourceType="gias",
                    sourceUrl=source_url,
                    capturedAt=captured,
                )
            )

        email = (row.get("SchoolEmail") or row.get("EmailAddress") or "").strip()
        if email and "@" in email:
            entries.append(
                ContactEntry(
                    role="office",
                    label="School email",
                    email=email.lower(),
                    sourceType="gias",
                    sourceUrl=source_url,
                    capturedAt=captured,
                )
            )

        head = _head_name(row)
        if head:
            entries.append(
                ContactEntry(
                    role="headteacher",
                    name=head,
                    label=(row.get("HeadPreferredJobTitle") or "Headteacher").strip(),
                    sourceType="gias",
                    sourceUrl=source_url,
                    capturedAt=captured,
                )
            )

        if entries:
            out[urn] = entries
    return out
