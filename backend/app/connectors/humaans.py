"""Humaans.io connector — fetches people + equipment for asset enrichment.

Humaans is an HR platform. This connector fetches:
  - People: name, work email, custom fields (GitHub handle, Element handle)
  - Equipment: devices assigned to each person with serial numbers

The data is used to enrich existing assets by matching device serial numbers,
adding the assigned user's name, email, and social handles.

API docs: https://docs.humaans.io
Base URL: https://app.humaans.io/api
Auth: Bearer token (API Access Token from Settings → API Access Tokens)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
import structlog

logger = structlog.get_logger()

BASE_URL = "https://app.humaans.io/api"


@dataclass
class HumaansPerson:
    """A person from Humaans with their equipment."""
    person_id: str
    first_name: str
    last_name: str
    preferred_name: str | None
    email: str  # work email
    job_title: str | None
    department: str | None
    github_handle: str | None = None
    element_handle: str | None = None
    linkedin_handle: str | None = None
    teams: list[str] = field(default_factory=list)
    status: str | None = None
    timezone: str | None = None
    remote_city: str | None = None
    remote_country: str | None = None
    devices: list[HumaansDevice] = field(default_factory=list)


@dataclass
class HumaansDevice:
    """A piece of equipment assigned to a person."""
    equipment_id: str
    name: str
    serial_number: str | None
    equipment_type: str | None
    person_id: str


class HumaansConnector:
    """Connector for Humaans.io HR platform."""

    def __init__(self) -> None:
        self.access_token: str | None = None
        self.client: httpx.AsyncClient | None = None
        # Caches
        self._custom_field_map: dict[str, str] = {}  # field_id → field_name

    async def authenticate(self, credentials: dict, config: dict) -> bool:
        """Validate the API token by fetching /api/people with limit=1."""
        self.access_token = credentials.get("api_token", "")
        if not self.access_token:
            logger.error("humaans_no_token")
            return False

        self.client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=30,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json",
            },
        )

        try:
            resp = await self.client.get("/people", params={"$limit": 1})
            if resp.status_code == 200:
                logger.info("humaans_auth_success")
                return True
            logger.error("humaans_auth_failed", status=resp.status_code)
            return False
        except Exception as e:
            logger.error("humaans_auth_error", error=str(e))
            return False

    async def fetch_people_with_devices(self) -> list[HumaansPerson]:
        """Fetch all people, their custom fields, and their equipment."""
        if not self.client:
            return []

        # Step 1: Fetch custom field definitions to map IDs to names
        await self._load_custom_fields()

        # Step 2: Fetch all people
        people = await self._fetch_all_people()

        # Step 3: Fetch all custom values and attach to people
        await self._enrich_custom_values(people)

        # Step 4: Fetch all equipment and attach to people
        await self._enrich_equipment(people)

        logger.info("humaans_fetch_complete", people=len(people))
        return list(people.values())

    async def _load_custom_fields(self) -> None:
        """Load custom field definitions to map field IDs to names."""
        fields = await self._paginate("/custom-fields")
        for f in fields:
            field_id = f.get("id", "")
            field_name = (f.get("name") or "").strip().lower()
            if field_id and field_name:
                self._custom_field_map[field_id] = field_name
        logger.info("humaans_custom_fields_loaded", count=len(self._custom_field_map))

    async def _fetch_all_people(self) -> dict[str, HumaansPerson]:
        """Fetch all people and return as dict keyed by person ID."""
        raw_people = await self._paginate("/people")
        people: dict[str, HumaansPerson] = {}
        for p in raw_people:
            pid = p.get("id", "")
            if not pid:
                continue

            # Extract teams as a flat list of names
            teams_raw = p.get("teams") or []
            teams = [t["name"] if isinstance(t, dict) else str(t) for t in teams_raw]

            people[pid] = HumaansPerson(
                person_id=pid,
                first_name=p.get("firstName", ""),
                last_name=p.get("lastName", ""),
                preferred_name=p.get("preferredName"),
                email=p.get("email", ""),
                job_title=p.get("jobTitle"),
                department=p.get("department"),
                # Top-level social fields
                github_handle=p.get("github") or None,
                linkedin_handle=p.get("linkedIn") or None,
                # Org & location
                teams=teams,
                status=p.get("status"),
                timezone=p.get("timezone"),
                remote_city=p.get("remoteCity"),
                remote_country=p.get("remoteCountry"),
            )
        logger.info("humaans_people_fetched", count=len(people))
        return people

    async def _enrich_custom_values(self, people: dict[str, HumaansPerson]) -> None:
        """Fetch all custom values and attach GitHub/Element handles to people."""
        # Identify which custom field IDs map to github/element
        github_field_ids = set()
        element_field_ids = set()
        for field_id, name in self._custom_field_map.items():
            if "github" in name:
                github_field_ids.add(field_id)
            if "element" in name or "matrix" in name:
                element_field_ids.add(field_id)

        if not github_field_ids and not element_field_ids:
            logger.info("humaans_no_social_custom_fields")
            return

        values = await self._paginate("/custom-values")
        for cv in values:
            person_id = cv.get("personId", "")
            field_id = cv.get("customFieldId", "")
            value = (cv.get("value") or "").strip()
            if not person_id or not value or person_id not in people:
                continue

            person = people[person_id]
            if field_id in github_field_ids and not person.github_handle:
                person.github_handle = value
            elif field_id in element_field_ids and not person.element_handle:
                person.element_handle = value

        gh_count = sum(1 for p in people.values() if p.github_handle)
        el_count = sum(1 for p in people.values() if p.element_handle)
        logger.info("humaans_custom_values_enriched", github=gh_count, element=el_count)

    async def _enrich_equipment(self, people: dict[str, HumaansPerson]) -> None:
        """Fetch all equipment and attach to their assigned people."""
        equipment = await self._paginate("/equipment")
        attached = 0
        for eq in equipment:
            person_id = eq.get("personId", "")
            eq_id = eq.get("id", "")
            name = eq.get("name") or eq.get("type") or "Unknown device"
            serial = eq.get("serialNumber")

            device = HumaansDevice(
                equipment_id=eq_id,
                name=name,
                serial_number=serial,
                equipment_type=eq.get("type"),
                person_id=person_id,
            )

            if person_id and person_id in people:
                people[person_id].devices.append(device)
                attached += 1

        logger.info("humaans_equipment_enriched", total=len(equipment), attached=attached)

    async def _paginate(self, endpoint: str, limit: int = 200) -> list[dict]:
        """Paginate through a Humaans API endpoint using $limit/$skip."""
        if not self.client:
            return []

        all_items: list[dict] = []
        skip = 0

        while True:
            try:
                resp = await self.client.get(
                    endpoint,
                    params={"$limit": limit, "$skip": skip},
                )
                if resp.status_code != 200:
                    logger.warning("humaans_api_error", endpoint=endpoint,
                                   status=resp.status_code, skip=skip)
                    break

                data = resp.json()
                items = data.get("data", [])
                total = data.get("total", 0)
                all_items.extend(items)

                skip += len(items)
                if skip >= total or not items:
                    break

            except Exception as e:
                logger.error("humaans_paginate_error", endpoint=endpoint, error=str(e))
                break

        return all_items

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()
