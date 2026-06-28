#!/bin/bash
set -e

USER_HOST=root@venus

echo "=== Install dbus-serialbattery (latest stable) ==="
ssh $USER_HOST "wget -O /tmp/install-serialbattery.sh \
  https://raw.githubusercontent.com/mr-manuel/venus-os_dbus-serialbattery/master/install.sh \
  && bash /tmp/install-serialbattery.sh --stable"

echo "=== Deploy serialbattery config ==="
scp config/serialbattery-config.ini $USER_HOST:/data/apps/dbus-serialbattery/config.ini

echo "=== Deploy dbus-mqtt-meter ==="
bash ./deploy.sh

echo "=== Done ==="
