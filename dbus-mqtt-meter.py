#!/usr/bin/python3 -u
# -*- coding: utf-8 -*-
import argparse
import logging
import os
import sys
import re

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from collections import OrderedDict
from gi.repository import GLib

from vedbus import VeDbusService

from mqtt_gobject_bridge import MqttGObjectBridge

VERSION = "0.1"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)


# We define these classes to avoid connection sharing to dbus. This is to allow
# more than one service to be held by a single python process.
class SystemBus(dbus.bus.BusConnection):
    def __new__(cls):
        return dbus.bus.BusConnection.__new__(cls, dbus.bus.BusConnection.TYPE_SYSTEM)


class SessionBus(dbus.bus.BusConnection):
    def __new__(cls):
        return dbus.bus.BusConnection.__new__(cls, dbus.bus.BusConnection.TYPE_SESSION)


def dbusconnection():
    return SessionBus() if "DBUS_SESSION_BUS_ADDRESS" in os.environ else SystemBus()


class Meter(object):
    """Represent a meter object on dbus."""

    data_map = {
        "hass/sensor/zahlerstand_bezug": "/Ac/Energy/Forward",
        "hass/sensor/zahlerstand_einspeisung": "/Ac/Energy/Reverse",
        "hass/sensor/netz_i1": "/Ac/L1/Current",
        "hass/sensor/netz_u1": "/Ac/L1/Voltage",
        "hass/sensor/netz_i2": "/Ac/L2/Current",
        "hass/sensor/netz_u2": "/Ac/L2/Voltage",
        "hass/sensor/netz_i3": "/Ac/L3/Current",
        "hass/sensor/netz_u3": "/Ac/L3/Voltage",
    }

    def __init__(self, host, base, instance):
        self.instance = instance
        self.service = service = VeDbusService(
            "{}.mqtt_{:02d}".format(base, instance), bus=dbusconnection()
        )
        self.data = {}
        self.data["hass/sensor/netz_bezug"] = 0.0
        self.data["hass/sensor/netz_einspeisung"] = 0.0

        # Add objects required by ve-api
        service.add_path("/Management/ProcessName", __file__)
        service.add_path("/Management/ProcessVersion", VERSION)
        service.add_path("/Management/Connection", host)
        service.add_path("/DeviceInstance", instance)
        service.add_path("/ProductId", 0xFFFF)
        service.add_path("/ProductName", "MQTT meter")
        service.add_path("/FirmwareVersion", None)
        service.add_path("/Serial", None)
        service.add_path("/Connected", 1)

        _kwh = lambda p, v: (f"{v:.0f}kWh")
        _a = lambda p, v: (f"{v:.1f}A")
        _w = lambda p, v: (f"{v:.0f}W")
        _v = lambda p, v: (f"{v:.1f}V")

        service.add_path("/Ac/Energy/Forward", None, gettextcallback=_kwh)
        service.add_path("/Ac/Energy/Reverse", None, gettextcallback=_kwh)
        service.add_path("/Ac/L1/Current", None, gettextcallback=_a)
        # service.add_path("/Ac/L1/Energy/Forward", None, gettextcallback=_kwh)
        # service.add_path("/Ac/L1/Energy/Reverse", None, gettextcallback=_kwh)
        service.add_path("/Ac/L1/Power", None, gettextcallback=_w)
        service.add_path("/Ac/L1/Voltage", None, gettextcallback=_v)
        service.add_path("/Ac/L2/Current", None, gettextcallback=_a)
        # service.add_path("/Ac/L2/Energy/Forward", None, gettextcallback=_kwh)
        # service.add_path("/Ac/L2/Energy/Reverse", None, gettextcallback=_kwh)
        service.add_path("/Ac/L2/Power", None, gettextcallback=_w)
        service.add_path("/Ac/L2/Voltage", None, gettextcallback=_v)
        service.add_path("/Ac/L3/Current", None, gettextcallback=_a)
        # service.add_path("/Ac/L3/Energy/Forward", None, gettextcallback=_kwh)
        # service.add_path("/Ac/L3/Energy/Reverse", None, gettextcallback=_kwh)
        service.add_path("/Ac/L3/Power", None, gettextcallback=_w)
        service.add_path("/Ac/L3/Voltage", None, gettextcallback=_v)
        service.add_path("/Ac/Power", None, gettextcallback=_w)

    def set_path(self, path, value):
        if self.service[path] != value:
            self.service[path] = value

    def update(self, topic, payload):
        try:
            sensor = topic[:-6]
            value = float(payload.decode())
            self.data[sensor] = value

            if sensor in self.data_map:
                self.set_path(self.data_map[sensor], value)

            total_power = 1000.0 * (
                self.data["hass/sensor/netz_bezug"]
                - self.data["hass/sensor/netz_einspeisung"]
            )
            self.set_path("/Ac/Power", total_power)

            match = re.search(r"\d", sensor)
            if match:  # means this is a per phase value
                factor = total_power / (
                    self.data[f"hass/sensor/netz_i1"]
                    * self.data[f"hass/sensor/netz_u1"]
                    + self.data[f"hass/sensor/netz_i2"]
                    * self.data[f"hass/sensor/netz_u2"]
                    + self.data[f"hass/sensor/netz_i3"]
                    * self.data[f"hass/sensor/netz_u3"]
                )

                phase_no = match.group(0)

                phase_power = (
                    factor
                    * self.data[f"hass/sensor/netz_i{phase_no}"]
                    * self.data[f"hass/sensor/netz_u{phase_no}"]
                )

                self.set_path(f"/Ac/L{phase_no}/Power", phase_power)

        except KeyError as e:
            logger.warning(
                "KeyError Exception raised. This is normal in the beginning, when not all values have been recieved yet",
                exc_info=e,
            )

        except ValueError as e:
            if payload.decode() == "unavailable":
                logger.warning(
                    "Unavailable entity found for %s. Skipping.",
                    sensor,
                )
                return

            raise e

    def __repr__(self):
        return self.__class__.__name__ + "(" + str(self.cts) + ")"

    def __del__(self):
        self.service.__del__()


class Bridge(MqttGObjectBridge):
    def __init__(self, host, meter, *args, **kwargs):
        super(Bridge, self).__init__(host, *args, **kwargs)
        self.host = host
        self.meter = meter

    def _on_message(self, client, userdata, msg):
        self.meter.update(msg.topic, msg.payload)

    def _on_connect(self, client, userdata, di, rc):
        sensor_list = list(self.meter.data_map.keys()) + [
            "hass/sensor/netz_bezug",
            "hass/sensor/netz_einspeisung",
        ]

        for topic in sensor_list:
            self._client.subscribe(f"{topic}/state", 0)


def main():
    parser = argparse.ArgumentParser(description=sys.argv[0])
    parser.add_argument(
        "--servicebase",
        help="Base service name on dbus, default is com.victronenergy",
        default="com.victronenergy.grid",
    )
    parser.add_argument("host", help="MQTT Host")
    args = parser.parse_args()

    DBusGMainLoop(set_as_default=True)

    # Create Meter instance
    meter = Meter(args.host, args.servicebase, 40)

    # MQTT connection
    bridge = Bridge(args.host, meter)

    mainloop = GLib.MainLoop()
    mainloop.run()


if __name__ == "__main__":
    main()
