from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import InnovaEnergieCoordinator


@dataclass(frozen=True, kw_only=True)
class InnovaEntityDescription(SensorEntityDescription):
    data_key: str = ""


SENSORS: tuple[InnovaEntityDescription, ...] = (
    InnovaEntityDescription(
        key="electricity_supply",
        name="Electricity supply",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:lightning-bolt",
        data_key="electricity_supply_kwh",
        suggested_display_precision=3,
    ),
    InnovaEntityDescription(
        key="electricity_return",
        name="Electricity return",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:lightning-bolt-outline",
        data_key="electricity_return_kwh",
        suggested_display_precision=3,
    ),
    InnovaEntityDescription(
        key="electricity_netted",
        name="Electricity net usage",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:transmission-tower",
        data_key="electricity_netted_kwh",
        suggested_display_precision=3,
    ),
    InnovaEntityDescription(
        key="gas_usage",
        name="Gas usage",
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        icon="mdi:fire",
        data_key="gas_m3",
        suggested_display_precision=3,
    ),
    InnovaEntityDescription(
        key="cost_electricity",
        name="Electricity cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="EUR",
        icon="mdi:currency-eur",
        data_key="cost_electricity_eur",
        suggested_display_precision=2,
    ),
    InnovaEntityDescription(
        key="cost_gas",
        name="Gas cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="EUR",
        icon="mdi:currency-eur",
        data_key="cost_gas_eur",
        suggested_display_precision=2,
    ),
    InnovaEntityDescription(
        key="cost_total",
        name="Total cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="EUR",
        icon="mdi:cash",
        data_key="cost_total_eur",
        suggested_display_precision=2,
    ),
    InnovaEntityDescription(
        key="electricity_last_hour",
        name="Electricity last reading",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:meter-electric",
        data_key="electricity_last_hour_kwh",
        suggested_display_precision=3,
    ),
    InnovaEntityDescription(
        key="gas_last_hour",
        name="Gas last reading",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        icon="mdi:meter-gas",
        data_key="gas_last_hour_m3",
        suggested_display_precision=3,
    ),
    InnovaEntityDescription(
        key="month_electricity",
        name="Electricity this month",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:lightning-bolt",
        data_key="month_electricity_kwh",
        suggested_display_precision=3,
    ),
    InnovaEntityDescription(
        key="month_gas",
        name="Gas this month",
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        icon="mdi:fire",
        data_key="month_gas_m3",
        suggested_display_precision=3,
    ),
    InnovaEntityDescription(
        key="meter_electricity",
        name="Electricity meter position",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:meter-electric",
        data_key="meter_electricity_kwh",
        suggested_display_precision=3,
    ),
    InnovaEntityDescription(
        key="meter_gas",
        name="Gas meter position",
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        icon="mdi:meter-gas",
        data_key="meter_gas_m3",
        suggested_display_precision=3,
    ),
    InnovaEntityDescription(
        key="tariff_electricity_high",
        name="Electricity high tariff",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="EUR/kWh",
        icon="mdi:currency-eur",
        data_key="tariff_electricity_high_eur_kwh",
        suggested_display_precision=5,
    ),
    InnovaEntityDescription(
        key="tariff_electricity_low",
        name="Electricity low tariff",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="EUR/kWh",
        icon="mdi:currency-eur",
        data_key="tariff_electricity_low_eur_kwh",
        suggested_display_precision=5,
    ),
    InnovaEntityDescription(
        key="tariff_gas",
        name="Gas tariff",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="EUR/m³",
        icon="mdi:currency-eur",
        data_key="tariff_gas_eur_m3",
        suggested_display_precision=5,
    ),
    InnovaEntityDescription(
        key="cost_electricity_month",
        name="Electricity cost this month",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="EUR",
        icon="mdi:currency-eur",
        data_key="cost_electricity_month_eur",
        suggested_display_precision=2,
    ),
    InnovaEntityDescription(
        key="cost_gas_month",
        name="Gas cost this month",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="EUR",
        icon="mdi:currency-eur",
        data_key="cost_gas_month_eur",
        suggested_display_precision=2,
    ),
    InnovaEntityDescription(
        key="cost_total_month",
        name="Total cost this month",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="EUR",
        icon="mdi:cash",
        data_key="cost_total_month_eur",
        suggested_display_precision=2,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: InnovaEnergieCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        InnovaEnergieSensor(coordinator, description) for description in SENSORS
    )


class InnovaEnergieSensor(CoordinatorEntity[InnovaEnergieCoordinator], SensorEntity):
    entity_description: InnovaEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: InnovaEnergieCoordinator,
        description: InnovaEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"innovaenergie_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, "innovaenergie")},
            name="Innova Energie",
            manufacturer="Innova Energie",
            model="Energie portal",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> float | None:
        return (self.coordinator.data or {}).get(self.entity_description.data_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return {"data_date": data.get("date")}
