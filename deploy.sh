#!/bin/bash

MODULE=dbus-mqtt-meter
FOLDER=/data/$MODULE
USER_HOST=root@venus
SSH="ssh $USER_HOST"

$SSH mkdir -p $FOLDER/service/log $FOLDER/ext/velib_python

echo "Copy files to $USER_HOST:$FOLDER"
for f in ${MODULE}.py mqtt_gobject_bridge.py service/run kill_me.sh service/log/run ext/velib_python/vedbus.py ext/velib_python/ve_utils.py
do
  scp $f $USER_HOST:$FOLDER/$f
done

echo "Set permissions"
$SSH chmod 0755 $FOLDER/service/run $FOLDER/service/log/run
$SSH chmod 0744 $FOLDER/kill_me.sh

echo "Creating symlinks"
CREATE_LN="ln -sfn $FOLDER/service /service/$MODULE  # $MODULE"
$SSH "touch /data/rc.local && chmod 0755 /data/rc.local"
$SSH "grep -qF '# $MODULE' /data/rc.local || echo '$CREATE_LN' >> /data/rc.local"
$SSH $CREATE_LN

echo "Kill old services"
$SSH $FOLDER/kill_me.sh

echo "Done."