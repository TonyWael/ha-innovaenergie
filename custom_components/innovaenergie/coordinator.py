from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp
from urllib.parse import unquote

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import BASE_URL, CONF_EAN_ELECTRICITY, CONF_EAN_GAS, DOMAIN, SCAN_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15"
)


class InnovaEnergieCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self._username: str = entry.data["username"]
        self._password: str = entry.data["password"]
        self._organization: str | None = entry.data.get("organization")
        self._cluster: str | None = entry.data.get("cluster")
        self._ean_electricity: str | None = entry.data.get(CONF_EAN_ELECTRICITY)
        self._ean_gas: str | None = entry.data.get(CONF_EAN_GAS)
        self._contract_electricity_uuid: str | None = None
        self._contract_gas_uuid: str | None = None
        self._tariff_electricity_period_uuid: str | None = None
        self._tariff_gas_period_uuid: str | None = None
        self._session: aiohttp.ClientSession | None = None
        self._xsrf_token: str | None = None

    # ------------------------------------------------------------------ session

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                cookie_jar=aiohttp.CookieJar(),
                headers={"User-Agent": _UA},
            )
        return self._session

    async def _close_session(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    # ------------------------------------------------------------------ auth

    def _cookie_value(self, name: str) -> str | None:
        if self._session is None:
            return None
        cookies = self._session.cookie_jar.filter_cookies(BASE_URL)
        c = cookies.get(name)
        return unquote(c.value) if c else None

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-XSRF-TOKEN": self._xsrf_token or "",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://mijn.innovaenergie.nl/login",
        }

    def _api_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "X-XSRF-TOKEN": self._xsrf_token or "",
            "X-Organization": self._organization or "",
            "X-Cluster": self._cluster or "",
            "Referer": "https://mijn.innovaenergie.nl/verbruik",
        }

    async def authenticate(self) -> None:
        """Full login flow: csrf → prelogin → login → discover EANs."""
        await self._close_session()
        session = await self._ensure_session()

        # 1. CSRF — sets XSRF-TOKEN + ghSess cookies
        async with session.get(
            f"{BASE_URL}/auth/csrf",
            headers={"Accept": "application/json", "Referer": "https://mijn.innovaenergie.nl/login"},
        ) as resp:
            resp.raise_for_status()
        xsrf = self._cookie_value("XSRF-TOKEN")
        if not xsrf:
            raise UpdateFailed("CSRF endpoint did not return XSRF-TOKEN cookie")
        self._xsrf_token = xsrf

        # 2. Prelogin — email check
        async with session.post(
            f"{BASE_URL}/auth/prelogin",
            json={"username": self._username},
            headers=self._auth_headers(),
        ) as resp:
            if resp.status not in (200, 204):
                body = await resp.text()
                raise ConfigEntryAuthFailed(f"Prelogin failed ({resp.status}): {body}")

        if token := self._cookie_value("XSRF-TOKEN"):
            self._xsrf_token = token

        # 3. Login — returns user.organizations with cluster list
        async with session.post(
            f"{BASE_URL}/auth/login",
            json={"username": self._username, "password": self._password},
            headers=self._auth_headers(),
        ) as resp:
            if resp.status in (401, 422):
                raise ConfigEntryAuthFailed("Invalid credentials")
            if resp.status != 200:
                body = await resp.text()
                raise ConfigEntryAuthFailed(f"Login failed ({resp.status}): {body}")
            payload = await resp.json()

        if token := self._cookie_value("XSRF-TOKEN"):
            self._xsrf_token = token

        if not self._organization or not self._cluster:
            self._pick_org_cluster(payload)

        # 4. Discover EANs + contract UUIDs from contracts
        await self._discover_eans()

    def _pick_org_cluster(self, payload: dict) -> None:
        organizations = (
            (payload.get("user") or {}).get("organizations")
            or payload.get("organizations")
            or []
        )
        if not organizations:
            _LOGGER.warning("No organizations in login response; raw payload keys: %s", list(payload))
            return

        org = organizations[0]
        self._organization = org.get("uuid") or org.get("id")
        clusters = org.get("clusters", [])
        active = next(
            (c for c in clusters if c.get("status") == "ACTIVE"),
            clusters[0] if clusters else None,
        )
        if active:
            self._cluster = active.get("cluster") or active.get("id")

        _LOGGER.debug("Using organization=%s cluster=%s", self._organization, self._cluster)

    async def _discover_eans(self) -> None:
        """Fetch EANs and contract UUIDs from /contracts."""
        try:
            contracts = await self._get("/contracts")
            if not contracts:
                _LOGGER.debug("Could not fetch contracts")
                return

            items = contracts if isinstance(contracts, list) else contracts.get("data", [])
            for item in items:
                segment = (item.get("marketSegment") or "").upper()
                ean = item.get("ean")
                contract_uuid = item.get("uuid") or item.get("id")

                # Active period UUID lives in the nested contracts array
                nested = item.get("contracts") or []
                active = next((c for c in nested if c.get("isActive")), nested[0] if nested else None)
                period_uuid = (active.get("uuid") or active.get("id")) if active else None

                if not ean:
                    continue
                if segment == "ELECTRICITY":
                    if not self._ean_electricity:
                        self._ean_electricity = str(ean)
                        _LOGGER.debug("Discovered electricity EAN: %s", ean)
                    if contract_uuid and not self._contract_electricity_uuid:
                        self._contract_electricity_uuid = str(contract_uuid)
                    if period_uuid and not self._tariff_electricity_period_uuid:
                        self._tariff_electricity_period_uuid = str(period_uuid)
                        _LOGGER.debug("Discovered electricity tariff period: %s", period_uuid)
                elif segment == "GAS":
                    if not self._ean_gas:
                        self._ean_gas = str(ean)
                        _LOGGER.debug("Discovered gas EAN: %s", ean)
                    if contract_uuid and not self._contract_gas_uuid:
                        self._contract_gas_uuid = str(contract_uuid)
                    if period_uuid and not self._tariff_gas_period_uuid:
                        self._tariff_gas_period_uuid = str(period_uuid)
                        _LOGGER.debug("Discovered gas tariff period: %s", period_uuid)

        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Contract discovery failed (non-fatal): %s", err)

    async def _fetch_tariff(self, contract_uuid: str | None, period_uuid: str | None) -> dict:
        """Fetch tariff rates for a contract period."""
        if not contract_uuid or not period_uuid:
            return {}
        try:
            data = await self._get(f"/contracts/tariffs/{contract_uuid}/{period_uuid}")
            return data or {}
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Tariff fetch failed for %s/%s (non-fatal): %s", contract_uuid, period_uuid, err)
        return {}

    # ------------------------------------------------------------------ API

    async def _get(self, path: str) -> dict | list | None:
        session = await self._ensure_session()
        async with session.get(
            f"{BASE_URL}{path}",
            headers=self._api_headers(),
        ) as resp:
            if resp.status in (401, 419):
                return None
            if resp.status == 404:
                return None
            resp.raise_for_status()
            return await resp.json()

    async def _get_with_reauth(self, path: str) -> dict:
        result = await self._get(path)
        if result is None:
            _LOGGER.debug("Session expired, re-authenticating")
            await self.authenticate()
            result = await self._get(path)
            if result is None:
                raise UpdateFailed(f"Failed to fetch {path} after re-authentication")
        return result

    # ------------------------------------------------------------------ coordinator

    async def _async_update_data(self) -> dict[str, Any]:
        if not self._organization or not self._cluster:
            await self.authenticate()

        try:
            # Determine latest date with available data
            date_ranges = await self._get_with_reauth("/dashboard/chartdateranges/v2")
            latest_date: str = (
                date_ranges.get("USAGE", {})
                .get("ELECTRICITY", {})
                .get("DAY", {})
                .get("maxDate", "")
            )
            if not latest_date:
                raise UpdateFailed("Could not determine latest available data date")

            usage = await self._get_with_reauth(
                f"/dashboard/usagechart?frequency=DAY&period={latest_date}"
            )
            cost = await self._get_with_reauth(
                f"/dashboard/costchart?frequency=DAY&period={latest_date}"
            )

            # Current month running totals (no date parameter needed)
            overview = await self._get_with_reauth("/dashboard/usageoverview")

            # Month-to-date costs
            month_period = latest_date[:7]  # "YYYY-MM"
            cost_month = await self._get_with_reauth(
                f"/dashboard/costchart?frequency=MONTH&period={month_period}"
            )

            # Meter readings (actual meter positions — optional, non-fatal if unavailable)
            elec_reading = await self._fetch_meter_reading(self._ean_electricity)
            gas_reading = await self._fetch_meter_reading(self._ean_gas)

            elec_tariff = await self._fetch_tariff(
                self._contract_electricity_uuid, self._tariff_electricity_period_uuid
            )
            gas_tariff = await self._fetch_tariff(
                self._contract_gas_uuid, self._tariff_gas_period_uuid
            )

        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with Innova Energie API: {err}") from err

        _LOGGER.debug("date=%s usagechart=%s", latest_date, usage)
        _LOGGER.debug("costchart=%s cost overview=%s", cost, overview)
        _LOGGER.debug("cost_month=%s", cost_month)
        _LOGGER.debug("elec_reading=%s gas_reading=%s", elec_reading, gas_reading)
        _LOGGER.debug("elec_tariff=%s gas_tariff=%s", elec_tariff, gas_tariff)

        elec_totals = (usage.get("totals") or {}).get("electricity") or {}
        gas_total = (usage.get("totals") or {}).get("gas") or 0
        cost_totals = cost.get("totals") or {}
        cost_month_totals = cost_month.get("totals") or {}
        elec_tariff_rates = elec_tariff.get("withTotalVat") or {}
        gas_tariff_rates = gas_tariff.get("withTotalVat") or {}

        elec_series: list[list] = (usage.get("series") or {}).get("electricity") or []
        gas_series: list[list] = (usage.get("series") or {}).get("gas") or []

        return {
            "date": latest_date,
            # Daily totals from usage chart
            "electricity_supply_kwh": _safe_float(elec_totals.get("supply")),
            "electricity_return_kwh": _safe_float(elec_totals.get("return")),
            "electricity_netted_kwh": _safe_float(elec_totals.get("netted")),
            "gas_m3": _safe_float(gas_total),
            # Daily costs
            "cost_electricity_eur": _safe_float(cost_totals.get("electricity")),
            "cost_gas_eur": _safe_float(cost_totals.get("gas")),
            "cost_total_eur": _safe_float(cost_totals.get("total")),
            # Last hourly reading
            "electricity_last_hour_kwh": _last_nonzero(elec_series),
            "gas_last_hour_m3": _last_nonzero(gas_series),
            # Actual meter positions (cumulative, total_increasing)
            "meter_electricity_kwh": elec_reading,
            "meter_gas_m3": gas_reading,
            # Current month running totals (from usageoverview)
            "month_electricity_kwh": _safe_float(
                (overview.get("electricity") or {}).get("supply")
                or (overview.get("electricity") or {}).get("netted")
            ),
            "month_gas_m3": _safe_float(
                (overview.get("gas") or {}).get("total")
            ),
            # Month-to-date costs (from costchart frequency=MONTH)
            "cost_electricity_month_eur": _safe_float(cost_month_totals.get("electricity")),
            "cost_gas_month_eur": _safe_float(cost_month_totals.get("gas")),
            "cost_total_month_eur": _safe_float(cost_month_totals.get("total")),
            # Current tariff rates incl. VAT + government levies
            "tariff_electricity_high_eur_kwh": _safe_float(elec_tariff_rates.get("tariffHigh")),
            "tariff_electricity_low_eur_kwh": _safe_float(elec_tariff_rates.get("tariffLow")),
            "tariff_gas_eur_m3": _safe_float(gas_tariff_rates.get("tariffGas")),
        }

    async def _fetch_meter_reading(self, ean: str | None) -> float | None:
        """Return the latest meter position for the given EAN, or None."""
        if not ean:
            return None
        try:
            data = await self._get(f"/meterreading/readings?ean={ean}")
            if not data:
                return None
            _LOGGER.debug("Meter reading response for EAN %s: %s", ean, data)
            return _parse_meter_reading(data)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Meter reading fetch failed for EAN %s (non-fatal): %s", ean, err)
            return None


def _safe_float(value: Any) -> float | None:
    try:
        return round(float(value), 4) if value is not None else None
    except (TypeError, ValueError):
        return None


def _last_nonzero(series: list[list]) -> float | None:
    """Return the most recent non-zero value from [[ts, val, est], ...] series."""
    for entry in reversed(series):
        if isinstance(entry, (list, tuple)) and len(entry) >= 2:
            val = entry[1]
            if val is not None and val != 0:
                return round(float(val), 4)
    return None


def _parse_meter_reading(data: Any) -> float | None:
    """Extract the most recent meter position from /meterreading/readings response.

    Response is paginated: {data: [{date, normal, low, returnNormal, returnLow, marketSegment}]}
    GAS:         normal = m³ (low is null)
    ELECTRICITY: normal + low = total kWh (high + low tariff)
    """
    if not data:
        return None

    items = data if isinstance(data, list) else data.get("data") or []
    if not items:
        return None

    first = items[0] if isinstance(items, list) else items
    segment = (first.get("marketSegment") or "").upper()

    if segment == "GAS":
        v = first.get("normal")
        return round(float(v), 4) if v is not None else None

    if segment == "ELECTRICITY":
        normal = float(first.get("normal") or 0)
        low = float(first.get("low") or 0)
        return round(normal + low, 4)

    _LOGGER.debug("Could not parse meter reading from: %s", first)
    return None
