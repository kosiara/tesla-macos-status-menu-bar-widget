"""Tesla Fleet API service layer wrapping python-tesla-fleet-api."""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import quote

import aiohttp
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from teslabar.config import load_config, save_config
from tesla_fleet_api.tesla.fleet import TeslaFleetApi
from tesla_fleet_api.tesla.vehicle.fleet import VehicleFleet
from tesla_fleet_api.tesla.vehicle.signed import VehicleSigned
from tesla_fleet_api.exceptions import TeslaFleetError, VehicleOffline

logger = logging.getLogger(__name__)


class VehicleState(Enum):
    UNKNOWN = "unknown"
    ONLINE = "online"
    ASLEEP = "asleep"
    OFFLINE = "offline"
    WAKING = "waking"
    ERROR = "error"
    AUTH_EXPIRED = "auth_expired"


@dataclass
class VehicleData:
    state: VehicleState = VehicleState.UNKNOWN
    battery_level: int = 0
    charge_limit: int = 80
    charging_state: str = "Disconnected"
    is_locked: bool = True
    sentry_mode: bool = False
    climate_on: bool = False
    inside_temp: float | None = None
    outside_temp: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    error_message: str = ""
    last_updated: float = 0.0


@dataclass
class ScheduleEntry:
    id: int = 0
    name: str = ""
    days_of_week: int = 0
    enabled: bool = True
    latitude: float = 0.0
    longitude: float = 0.0
    time_minutes: int = 0  # minutes after midnight
    one_time: bool = False

    @property
    def time_str(self) -> str:
        h, m = divmod(self.time_minutes, 60)
        return f"{h:02d}:{m:02d}"

    @property
    def days_list(self) -> list[str]:
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return [days[i] for i in range(7) if self.days_of_week & (1 << i)]


class TeslaService:
    def __init__(self) -> None:
        self._api: TeslaFleetApi | None = None
        self._vehicle: VehicleSigned | VehicleFleet | None = None
        self._session: aiohttp.ClientSession | None = None
        self._vin: str | None = None
        self._access_token: str = ""
        self._refresh_token: str = ""
        self._token_expiry: float = 0.0
        self._client_id: str = ""
        self._client_secret: str = ""
        self._region: str = "eu"  # default, will be auto-detected
        self.vehicle_data = VehicleData()
        self._command_status: str = ""
        self.partner_registered: bool = False
        self._reauth_callback = None
        self._load_saved_location()

    @property
    def command_status(self) -> str:
        return self._command_status

    @property
    def is_authenticated(self) -> bool:
        return bool(self._access_token)

    @property
    def token_expired(self) -> bool:
        return time.time() >= self._token_expiry if self._token_expiry else True

    def configure(
        self,
        client_id: str,
        client_secret: str,
        access_token: str = "",
        refresh_token: str = "",
        token_expiry: float = 0.0,
        region: str = "eu",
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_expiry = token_expiry
        self._region = region

    async def register_partner(self, domain: str = "") -> bool:
        """One-time partner registration. Uses a separate session to avoid overwriting user token."""
        if not domain:
            logger.warning(
                "No GitHub Pages domain configured — partner domain registration skipped.\n"
                "  To fix this:\n"
                "  1. Open Settings in TeslaBar\n"
                "  2. Generate a Virtual Key pair (if not done)\n"
                "  3. Create a GitHub repo with Pages enabled\n"
                "  4. Host your public key at: https://<your-domain>/.well-known/appspecific/com.tesla.3p.public-key.pem\n"
                "  5. Enter your GitHub Pages domain (e.g. username.github.io) in Settings\n"
                "  6. Restart the app"
            )
            return False

        # Strip any path — Tesla only accepts the hostname
        clean_domain = domain.split("/")[0]

        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: Get partner token via client credentials
                token_resp = await session.post(
                    "https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "audience": f"https://fleet-api.prd.{self._region}.vn.cloud.tesla.com",
                        "scope": "openid",
                    },
                )
                token_data = await token_resp.json()
                if "access_token" not in token_data:
                    logger.error("Partner login failed: %s", token_data)
                    return False
                partner_token = token_data["access_token"]
                logger.info("Partner login successful")

                # Step 2: Register domain with partner token
                server = f"https://fleet-api.prd.{self._region}.vn.cloud.tesla.com"
                reg_resp = await session.post(
                    f"{server}/api/1/partner_accounts",
                    headers={
                        "Authorization": f"Bearer {partner_token}",
                        "Content-Type": "application/json",
                    },
                    json={"domain": clean_domain},
                )
                reg_data = await reg_resp.json()
                if reg_resp.ok:
                    logger.info("Partner domain registered: %s", reg_data)
                    self.partner_registered = True
                    return True
                else:
                    logger.error(
                        "Partner domain registration failed (HTTP %s): %s\n"
                        "  Domain used: %s\n"
                        "  Tesla requires the public key at:\n"
                        "  https://%s/.well-known/appspecific/com.tesla.3p.public-key.pem",
                        reg_resp.status, reg_data, clean_domain, clean_domain,
                    )
                    return False
        except Exception as e:
            logger.error("Partner registration failed: %s", e)
            return False

    def get_tokens(self) -> dict:
        return {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "token_expiry": self._token_expiry,
        }

    def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        scopes = [
            "openid",
            "offline_access",
            "vehicle_device_data",
            "vehicle_cmds",
            "vehicle_charging_cmds",
            "vehicle_location",
        ]
        audience = f"https://fleet-api.prd.{self._region}.vn.cloud.tesla.com"
        logger.info(f"Getting oauth url for scopes {quote(' '.join(scopes), safe='')} audience={audience}")
        return (
            f"https://auth.tesla.com/oauth2/v3/authorize"
            f"?client_id={quote(self._client_id, safe='')}"
            f"&redirect_uri={quote(redirect_uri, safe='')}"
            f"&response_type=code"
            f"&scope={quote(' '.join(scopes), safe='')}"
            f"&state={quote(state, safe='')}"
            f"&audience={quote(audience, safe='')}"
            f"&prompt=consent"
            f"&prompt_missing_scopes=true"
        )

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://auth.tesla.com/oauth2/v3/token",
                json={
                    "grant_type": "authorization_code",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "audience": f"https://fleet-api.prd.{self._region}.vn.cloud.tesla.com",
                    "scope": "openid offline_access vehicle_device_data vehicle_cmds vehicle_charging_cmds vehicle_location",
                },
            ) as resp:
                data = await resp.json()
                logger.info("Token exchange response keys: %s", list(data.keys()))
                logger.info("Token exchange granted scope: %s", data.get("scope", "(not in response)"))
                if "access_token" not in data:
                    raise RuntimeError(f"Token exchange failed: {data}")
                self._access_token = data["access_token"]
                self._refresh_token = data.get("refresh_token", "")
                expires_in = data.get("expires_in", 28800)
                self._token_expiry = time.time() + expires_in
                granted_scopes = data.get("scope", "")
                if granted_scopes:
                    logger.info("OAuth token granted scopes: %s", granted_scopes)
                else:
                    # Decode scopes from JWT payload
                    try:
                        import base64, json as _json
                        payload = self._access_token.split(".")[1]
                        payload += "=" * (-len(payload) % 4)
                        claims = _json.loads(base64.urlsafe_b64decode(payload))
                        jwt_scopes = claims.get("scp", claims.get("scope", "N/A"))
                        logger.info("OAuth token scopes (from JWT): %s", jwt_scopes)
                    except Exception:
                        logger.info("OAuth token scopes: not available")
                # Reset API so it picks up new token
                self._api = None
                self._vehicle = None
                return data

    async def refresh_access_token(self) -> bool:
        if not self._refresh_token:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://auth.tesla.com/oauth2/v3/token",
                    json={
                        "grant_type": "refresh_token",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "refresh_token": self._refresh_token,
                    },
                ) as resp:
                    data = await resp.json()
                    if "access_token" not in data:
                        logger.error("Token refresh failed: %s", data)
                        return False
                    self._access_token = data["access_token"]
                    if "refresh_token" in data:
                        self._refresh_token = data["refresh_token"]
                    expires_in = data.get("expires_in", 28800)
                    self._token_expiry = time.time() + expires_in
                    # Reset API so it picks up new token
                    self._api = None
                    self._vehicle = None
                    return True
        except Exception as e:
            logger.error("Token refresh error: %s", e)
            return False

    def _load_private_key(self) -> None:
        """Load the EC private key for signed vehicle commands."""
        from teslabar.crypto.virtual_key import get_private_key_pem
        pem = get_private_key_pem()
        if pem and self._api:
            try:
                key = load_pem_private_key(pem.encode(), password=None)
                self._api.private_key = key
                logger.info("Private key loaded for signed commands")
            except Exception as e:
                logger.warning("Failed to load private key: %s", e)
        else:
            logger.warning("No private key found — vehicle commands will not work")

    async def _ensure_api(self) -> TeslaFleetApi:
        if self.token_expired and self._refresh_token:
            success = await self.refresh_access_token()
            if not success:
                self.vehicle_data.state = VehicleState.AUTH_EXPIRED
                raise RuntimeError("Authentication expired. Please re-authenticate.")

        if self._api is None:
            if self._session is not None:
                await self._session.close()
            self._session = aiohttp.ClientSession()
            self._api = TeslaFleetApi(
                session=self._session,
                access_token=self._access_token,
                region=self._region,
            )
            # Load private key for signed commands
            self._load_private_key()
            logger.info("API initialized with region=%s, server=%s", self._region, self._api.server)

        return self._api

    async def _ensure_vehicle(self) -> VehicleSigned | VehicleFleet:
        if self._vehicle is not None:
            return self._vehicle
        api = await self._ensure_api()
        if not self._vin:
            await self.discover_vehicle()
        if self._vin:
            if api.has_private_key:
                self._vehicle = api.vehicles.createSigned(self._vin)
                logger.info("Using signed vehicle commands")
            else:
                self._vehicle = api.vehicles.createFleet(self._vin)
                logger.warning("Using unsigned vehicle commands (no private key)")
        if self._vehicle is None:
            raise RuntimeError("No vehicle available")
        return self._vehicle

    async def discover_vehicle(self) -> bool:
        try:
            api = await self._ensure_api()
            # Use products endpoint to find vehicles
            resp = await api.products()
            vehicles = [
                p for p in resp.get("response", [])
                if "vin" in p
            ]
            if not vehicles:
                self.vehicle_data.state = VehicleState.ERROR
                self.vehicle_data.error_message = "No vehicles found on account"
                return False
            v = vehicles[0]
            self._vin = v.get("vin")
            if api.has_private_key:
                self._vehicle = api.vehicles.createSigned(self._vin)
            else:
                self._vehicle = api.vehicles.createFleet(self._vin)
            logger.info("Discovered vehicle: %s", self._vin)
            return True
        except Exception as e:
            err_name = type(e).__name__
            if "PreconditionFailed" in err_name:
                msg = (
                    "Partner domain not registered. "
                    "Open Settings → set GitHub Pages domain → "
                    "host your public key at https://<domain>/"
                    ".well-known/appspecific/com.tesla.3p.public-key.pem → restart app."
                )
                logger.error("Vehicle discovery failed: %s — %s", e, msg)
                self.vehicle_data.state = VehicleState.ERROR
                self.vehicle_data.error_message = msg
            else:
                logger.error("Vehicle discovery failed: %s", e)
                self.vehicle_data.state = VehicleState.ERROR
                self.vehicle_data.error_message = str(e)
            return False

    async def _wake_if_needed(self) -> bool:
        if self.vehicle_data.state in (VehicleState.ASLEEP, VehicleState.OFFLINE):
            self.vehicle_data.state = VehicleState.WAKING
            self._command_status = "Waking vehicle..."
            try:
                vehicle = await self._ensure_vehicle()
                await vehicle.wake_up()
                for _ in range(30):
                    await asyncio.sleep(2)
                    resp = await vehicle.vehicle()
                    state = resp.get("response", {}).get("state", "")
                    if state == "online":
                        self.vehicle_data.state = VehicleState.ONLINE
                        return True
                self.vehicle_data.state = VehicleState.ERROR
                self.vehicle_data.error_message = "Vehicle did not wake up"
                return False
            except Exception as e:
                logger.error("Wake failed: %s", e)
                self.vehicle_data.state = VehicleState.ERROR
                self.vehicle_data.error_message = str(e)
                return False
        return True

    def _update_location(self, data: dict) -> None:
        """Update vehicle location from drive_state if available, persisting to config."""
        drive = data.get("drive_state", {})
        lat = drive.get("latitude")
        lon = drive.get("longitude")
        if lat is not None and lon is not None:
            self.vehicle_data.latitude = lat
            self.vehicle_data.longitude = lon
            cfg = load_config()
            cfg["vehicle_latitude"] = lat
            cfg["vehicle_longitude"] = lon
            save_config(cfg)
            logger.info("Vehicle location updated and saved: %.6f, %.6f", lat, lon)

    def _load_saved_location(self) -> None:
        """Load last known vehicle location from config."""
        cfg = load_config()
        lat = cfg.get("vehicle_latitude")
        lon = cfg.get("vehicle_longitude")
        if lat is not None and lon is not None:
            self.vehicle_data.latitude = lat
            self.vehicle_data.longitude = lon
            logger.info("Loaded saved vehicle location: %.6f, %.6f", lat, lon)

    async def fetch_vehicle_data(self) -> VehicleData:
        try:
            vehicle = await self._ensure_vehicle()

            try:
                resp = await vehicle.vehicle_data(
                    endpoints=[
                        "charge_state",
                        "climate_state",
                        "vehicle_state",
                        "drive_state",
                    ],
                )
            except VehicleOffline:
                self.vehicle_data.state = VehicleState.ASLEEP
                logger.info("Vehicle is asleep/offline, attempting wake...")
                awake = await self._wake_if_needed()
                if not awake:
                    return self.vehicle_data
                # Retry after wake
                resp = await vehicle.vehicle_data(
                    endpoints=[
                        "charge_state",
                        "climate_state",
                        "vehicle_state",
                        "drive_state",
                    ],
                )

            data = resp.get("response", {})
            state_str = data.get("state", "unknown")

            if state_str == "asleep":
                self.vehicle_data.state = VehicleState.ASLEEP
                self._update_location(data)
                return self.vehicle_data
            if state_str == "offline":
                self.vehicle_data.state = VehicleState.OFFLINE
                self._update_location(data)
                return self.vehicle_data

            charge = data.get("charge_state", {})
            climate = data.get("climate_state", {})
            vstate = data.get("vehicle_state", {})
            drive = data.get("drive_state", {})

            self.vehicle_data = VehicleData(
                state=VehicleState.ONLINE,
                battery_level=charge.get("battery_level", 0),
                charge_limit=charge.get("charge_limit_soc", 80),
                charging_state=charge.get("charging_state", "Disconnected"),
                is_locked=vstate.get("locked", True),
                sentry_mode=vstate.get("sentry_mode", False),
                climate_on=climate.get("is_climate_on", False),
                inside_temp=climate.get("inside_temp"),
                outside_temp=climate.get("outside_temp"),
                latitude=drive.get("latitude"),
                longitude=drive.get("longitude"),
                last_updated=time.time(),
            )
            self._command_status = ""
            return self.vehicle_data

        except RuntimeError:
            raise
        except BaseException as e:
            logger.error("Fetch vehicle data error: %s", e)
            self.vehicle_data.state = VehicleState.ERROR
            self.vehicle_data.error_message = str(e)
            return self.vehicle_data

    async def _send_command(self, command: str, **kwargs: Any) -> bool:
        try:
            self._command_status = f"Executing: {command}..."
            vehicle = await self._ensure_vehicle()

            if not await self._wake_if_needed():
                self._command_status = "Failed: vehicle not reachable"
                return False

            cmd_func = getattr(vehicle, command, None)
            if cmd_func is None:
                self._command_status = f"Unknown command: {command}"
                return False

            if kwargs:
                await cmd_func(**kwargs)
            else:
                await cmd_func()

            self._command_status = f"Success: {command}"
            return True
        except BaseException as e:
            logger.error("Command %s failed: %s", command, e)
            self._command_status = f"Failed: {e}"
            self.vehicle_data.state = VehicleState.ERROR
            self.vehicle_data.error_message = str(e)
            return False

    async def start_charge(self) -> bool:
        return await self._send_command("charge_start")

    async def stop_charge(self) -> bool:
        return await self._send_command("charge_stop")

    async def set_charge_limit(self, percent: int) -> bool:
        return await self._send_command("set_charge_limit", percent=percent)

    async def climate_on(self) -> bool:
        return await self._send_command("auto_conditioning_start")

    async def climate_off(self) -> bool:
        return await self._send_command("auto_conditioning_stop")

    async def lock(self) -> bool:
        return await self._send_command("door_lock")

    async def unlock(self) -> bool:
        return await self._send_command("door_unlock")

    async def get_charge_schedules(self) -> list[ScheduleEntry]:
        try:
            vehicle = await self._ensure_vehicle()
            resp = await vehicle.vehicle_data(
                endpoints=["charge_schedule_data"]
            )
            data = resp.get("response", {})
            logger.info("Charge schedule data: %s", data.get("charge_schedule_data"))
            schedules_raw = (
                data.get("charge_schedule_data", {})
                .get("charge_schedules", [])
            )
            entries = []
            for s in schedules_raw:
                entries.append(
                    ScheduleEntry(
                        id=s.get("id", 0),
                        name=s.get("name", ""),
                        days_of_week=s.get("days_of_week", 0),
                        enabled=s.get("enabled", True),
                        latitude=s.get("latitude", 0.0),
                        longitude=s.get("longitude", 0.0),
                        time_minutes=s.get("start_time", 0),
                    )
                )
            return entries
        except BaseException as e:
            logger.error("Failed to get charge schedules: %s", e)
            return []

    async def remove_charge_schedule(self, schedule_id: int) -> bool:
        return await self._send_command("remove_charge_schedule", id=schedule_id)

    async def get_precondition_schedules(self) -> list[ScheduleEntry]:
        try:
            vehicle = await self._ensure_vehicle()
            resp = await vehicle.vehicle_data(
                endpoints=["preconditioning_schedule_data"]
            )
            data = resp.get("response", {})
            logger.info("Precondition schedule data: %s", data.get("preconditioning_schedule_data"))
            schedules_raw = (
                data.get("preconditioning_schedule_data", {})
                .get("precondition_schedules", [])
            )
            entries = []
            for s in schedules_raw:
                entries.append(
                    ScheduleEntry(
                        id=s.get("id", 0),
                        name=s.get("name", ""),
                        days_of_week=s.get("days_of_week", 0),
                        enabled=s.get("enabled", True),
                        latitude=s.get("latitude", 0.0),
                        longitude=s.get("longitude", 0.0),
                        time_minutes=s.get("precondition_time", 0),
                        one_time=s.get("one_time", False),
                    )
                )
            return entries
        except BaseException as e:
            logger.error("Failed to get precondition schedules: %s", e)
            return []

    async def _get_location(self) -> tuple[float, float]:
        """Get location: saved/vehicle first, then IP geolocation fallback."""
        lat = self.vehicle_data.latitude
        lon = self.vehicle_data.longitude
        if lat and lon:
            logger.info("Using vehicle/saved location: %.6f, %.6f", lat, lon)
            return lat, lon
        # Fallback: IP-based geolocation
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://ipinfo.io/json", timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    data = await resp.json()
                    loc = data.get("loc", "")
                    if "," in loc:
                        ip_lat, ip_lon = loc.split(",")
                        lat, lon = float(ip_lat), float(ip_lon)
                        logger.info("Using IP geolocation fallback: %.6f, %.6f", lat, lon)
                        return lat, lon
        except Exception as e:
            logger.warning("IP geolocation failed: %s", e)
        logger.warning("No location available, using 0.0, 0.0")
        return 0.0, 0.0

    async def add_precondition_schedule(
        self, days_of_week: int, time_minutes: int, one_time: bool = False
    ) -> bool:
        lat, lon = await self._get_location()
        schedule_id = int(time.time())
        logger.info("Adding precondition schedule id=%d at location: %.6f, %.6f", schedule_id, lat, lon)
        return await self._send_command(
            "add_precondition_schedule",
            id=schedule_id,
            days_of_week=days_of_week,
            enabled=True,
            lat=lat,
            lon=lon,
            precondition_time=time_minutes,
            one_time=one_time,
        )

    async def toggle_precondition_schedule(self, entry: "ScheduleEntry", enabled: bool) -> bool:
        return await self._send_command(
            "add_precondition_schedule",
            id=entry.id,
            days_of_week=entry.days_of_week,
            enabled=enabled,
            lat=entry.latitude,
            lon=entry.longitude,
            precondition_time=entry.time_minutes,
            one_time=entry.one_time,
        )

    async def nearby_charging_sites(self, radius: int = 200, count: int = 50) -> list[dict]:
        """Return nearby superchargers within radius (km)."""
        try:
            vehicle = await self._ensure_vehicle()
            resp = await vehicle.nearby_charging_sites(count=count, radius=radius, detail=True)
            logger.info("Nearby charging sites response: %s", resp)
            sites = resp.get("response", {}).get("superchargers", [])
            return sites
        except BaseException as e:
            logger.error("Failed to get nearby charging sites: %s", e)
            return []

    async def remove_precondition_schedule(self, schedule_id: int) -> bool:
        return await self._send_command(
            "remove_precondition_schedule", id=schedule_id
        )

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None
            self._api = None
            self._vehicle = None
