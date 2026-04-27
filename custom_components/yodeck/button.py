"""Button platform for YoDeck."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import YoDeckDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YoDeck button based on a config entry."""
    coordinator: YoDeckDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([YoDeckRefreshButton(coordinator)])


class YoDeckRefreshButton(CoordinatorEntity[YoDeckDataUpdateCoordinator], ButtonEntity):
    """Representation of a YoDeck refresh button."""

    def __init__(self, coordinator: YoDeckDataUpdateCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_refresh"
        self._attr_name = "YoDeck Refresh"
        self._attr_icon = "mdi:refresh"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_request_refresh()
