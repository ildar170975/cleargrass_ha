import logging
from collections import defaultdict

import click
import json
from miio.click_common import command, format_output
from miio.device import Device

_LOGGER = logging.getLogger(__name__)

######################################################################

class AirQualityMonitorStatus:
    """Container of air quality monitor status."""

    def __init__(self, data):
        self.data = data

    @property
    def temperature(self) -> float:
        return self.data["temperature"] 

    @property
    def humidity(self) -> float:
        return self.data["humidity"]

    @property
    def co2(self) -> int:
        return self.data["co2"]

    @property
    def tvoc(self) -> int:
        return self.data["tvoc"]

    @property
    def pm25(self) -> float:
        return self.data["pm25"]

    @property
    def battery(self) -> int:
        return self.data["battery"]

    @property
    def battery_state(self) -> str:
        return self.data["battery_state"]

    def __repr__(self) -> str:
        s = "<AirQualityMonitorStatus humidity=%s, " \
            "co2=%s, " \
            "tvoc=%s, " \
            "pm25=%s, " \
            "battery=%s, " \
            "battery_state=%s>" % \
            (self.humidity,
             self.co2,
             self.tvoc,
             self.pm25,
             self.battery,
             self.battery_state,
             )
        return s
        
    def __json__(self):
        return self.data

######################################################################

MODEL_AIRQUALITYMONITOR_S1 = 'cgllc.airmonitor.s1'

AVAILABLE_PROPERTIES_COMMON = ['battery_state', 'co2', 'humidity', 'pm25' , 'temperature', 'tvoc']

AVAILABLE_PROPERTIES = {
    MODEL_AIRQUALITYMONITOR_S1: AVAILABLE_PROPERTIES_COMMON,
}

class AirQualityMonitor(Device):
    """Xiaomi PM2.5 Air Quality Monitor."""
    def __init__(self, ip: str = None, token: str = None, start_id: int = 0,
                 debug: int = 0, lazy_discover: bool = True,
                 model: str = MODEL_AIRQUALITYMONITOR_S1) -> None:
        super().__init__(ip, token, start_id, debug, lazy_discover, model=model)

        if model not in AVAILABLE_PROPERTIES:
            _LOGGER.error("Device model %s unsupported. Falling back to %s.", model, self.model)

        self.device_info = None

    @command(
        default_output=format_output(
            ""
        )
    )
    def status(self) -> AirQualityMonitorStatus:
        """Return device status."""

        properties = AVAILABLE_PROPERTIES[self.model]

        values = self.send(
          "get_prop",
          properties
        )

        properties_count = len(properties)
        values_count = len(values)
        if properties_count != values_count:
            _LOGGER.error(
                "Count (%s) of requested properties does not match the "
                "count (%s) of received values.",
                properties_count, values_count)

        value_battery = self.send(
          "get_value",
          "battery"
        )
        if not isinstance(value_battery, dict):
          value_battery = {"battery": "100"}

        # _LOGGER.error(
        #     "data_1 %s (%s)",
        #     value_battery)
        # _LOGGER.error(
        #     "data_2 %s (%s)",
        #     values)

        return AirQualityMonitorStatus(
            defaultdict(lambda: None, value_battery|values))

######################################################################

"""Support for Xiaomi Mi Air Quality Monitor (PM2.5)."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'clear_grass'
DATA_KEY = 'sensor.clear_grass'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the sensor from config."""
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)

    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    try:
        air_quality_monitor = AirQualityMonitor(host, token)
        device_info = air_quality_monitor.info()
        model = device_info.model
        unique_id = "{}-{}".format(model, device_info.mac_address)
        _LOGGER.info("%s %s %s detected",
                     model,
                     device_info.firmware_version,
                     device_info.hardware_version)
        device = ClearGrassMonitor(
            name, air_quality_monitor, model, unique_id)
    except Exception:
        raise PlatformNotReady

    hass.data[DATA_KEY][host] = device
    async_add_entities([device], update_before_add=True)

######################################################################

ATTR_TEMPERATURE = 'temperature'
ATTR_HUMIDITY = 'humidity'
ATTR_CO2 = 'co2'
ATTR_TVOC = 'tvoc'
ATTR_PM25 = 'pm25'

ATTR_BATTERY_LEVEL = 'battery_level'
ATTR_BATTERY_STATE = 'battery_state'

ATTR_MODEL = 'model'

class ClearGrassMonitor(Entity):
    """Representation of a Xiaomi Air Quality Monitor."""

    def __init__(self, name, device, model, unique_id):
        """Initialize the entity."""
        self._name = name
        self._device = device
        self._model = model
        self._unique_id = unique_id

        self._icon = 'mdi:cloud'
        self._unit_of_measurement = 'AQI'
        self._available = None
        self._state = None
        self._state_attrs = {
            ATTR_TEMPERATURE: None,
            ATTR_HUMIDITY: None,
            ATTR_CO2: None,
            ATTR_TVOC: None,
            #ATTR_PM25: None,
            ATTR_BATTERY_LEVEL: None,
            ATTR_BATTERY_STATE: None,
            ATTR_MODEL: self._model,
        }

    @property
    def should_poll(self):
        """Poll the miio device."""
        return True

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    async def async_update(self):
        """Fetch state from the miio device."""        
        try:
            state = await self.hass.async_add_executor_job(self._device.status)

            self._available = True
            self._state = state.pm25
            self._state_attrs.update({
                ATTR_TEMPERATURE: state.temperature,
                ATTR_HUMIDITY: state.humidity,
                ATTR_CO2: state.co2,
                ATTR_TVOC: state.tvoc,
              #  ATTR_PM25:state.pm25,
                ATTR_BATTERY_LEVEL: state.battery,
                ATTR_BATTERY_STATE: state.battery_state,
            })

        except Exception as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)
