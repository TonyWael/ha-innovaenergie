from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from urllib.parse import unquote

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_CLUSTER,
    CONF_ORGANIZATION,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)
from .coordinator import InnovaEnergieCoordinator

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class InnovaEnergieConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                org, cluster = await self._try_login(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during login")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_ORGANIZATION: org,
                        CONF_CLUSTER: cluster,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def _try_login(self, username: str, password: str) -> tuple[str, str]:
        """Return (organization_uuid, cluster_id) on success."""
        session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar())
        try:
            from .coordinator import BASE_URL, _UA

            # 1. CSRF
            async with session.get(
                f"{BASE_URL}/auth/csrf",
                headers={
                    "Accept": "application/json",
                    "User-Agent": _UA,
                    "Referer": "https://mijn.innovaenergie.nl/login",
                },
            ) as resp:
                _LOGGER.debug("CSRF status=%s", resp.status)
                if resp.status not in (200, 204):
                    _LOGGER.error("CSRF failed status=%s", resp.status)
                    raise CannotConnect
                cookies = session.cookie_jar.filter_cookies(BASE_URL)
                xsrf = (cookies.get("XSRF-TOKEN") or {})
                xsrf_value = unquote(xsrf.value) if hasattr(xsrf, "value") else None
                if not xsrf_value:
                    _LOGGER.error("CSRF did not return XSRF-TOKEN cookie")
                    raise CannotConnect

            base_headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-XSRF-TOKEN": xsrf_value,
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": _UA,
                "Referer": "https://mijn.innovaenergie.nl/login",
            }

            # 2. Prelogin
            async with session.post(
                f"{BASE_URL}/auth/prelogin",
                json={"username": username},
                headers=base_headers,
            ) as resp:
                if resp.status not in (200, 204):
                    body = await resp.text()
                    _LOGGER.error("Prelogin failed status=%s body=%s", resp.status, body)
                    raise InvalidAuth

            # Refresh XSRF after prelogin
            cookies = session.cookie_jar.filter_cookies(BASE_URL)
            new_xsrf = cookies.get("XSRF-TOKEN")
            if new_xsrf:
                base_headers["X-XSRF-TOKEN"] = unquote(new_xsrf.value)

            # 3. Login
            async with session.post(
                f"{BASE_URL}/auth/login",
                json={"username": username, "password": password},
                headers=base_headers,
            ) as resp:
                if resp.status in (401, 422):
                    body = await resp.text()
                    _LOGGER.error("Login failed status=%s body=%s", resp.status, body)
                    raise InvalidAuth
                if resp.status != 200:
                    body = await resp.text()
                    _LOGGER.error("Login unexpected status=%s body=%s", resp.status, body)
                    raise CannotConnect
                payload = await resp.json()

            # Extract org/cluster from login response
            organizations = (
                (payload.get("user") or {}).get("organizations")
                or payload.get("organizations")
                or []
            )

            # Fall back to /auth/user if login response had no organizations
            if not organizations:
                cookies = session.cookie_jar.filter_cookies(BASE_URL)
                xsrf = cookies.get("XSRF-TOKEN")
                async with session.get(
                    f"{BASE_URL}/auth/user",
                    headers={
                        "Accept": "application/json",
                        "X-XSRF-TOKEN": xsrf.value if xsrf else "",
                        "User-Agent": _UA,
                    },
                ) as resp:
                    if resp.status == 200:
                        user_data = await resp.json()
                        organizations = user_data.get("organizations", [])

            if not organizations:
                raise CannotConnect

            org = organizations[0]
            org_uuid = org.get("uuid") or org.get("id", "")
            clusters = org.get("clusters", [])
            active = next(
                (c for c in clusters if c.get("status") == "ACTIVE"),
                clusters[0] if clusters else None,
            )
            if not active:
                raise CannotConnect

            cluster_id = active.get("cluster") or active.get("id", "")
            return org_uuid, cluster_id

        except (aiohttp.ClientError, TimeoutError) as err:
            raise CannotConnect from err
        finally:
            await session.close()


class CannotConnect(HomeAssistantError):
    pass


class InvalidAuth(HomeAssistantError):
    pass
