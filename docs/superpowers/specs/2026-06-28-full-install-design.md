# Full Venus OS Installation Design

**Date:** 2026-06-28  
**Scope:** Enhance `dbus-mqtt-meter` repo to orchestrate full Venus OS driver setup

## Goal

A single `setup.sh` run from the developer's local machine (WSL) installs both drivers on a fresh Venus OS SD card, with no interactive prompts.

## Drivers

- **dbus-mqtt-meter** — this repo's driver; bridges Home Assistant MQTT sensors to Venus OS D-Bus grid meter
- **dbus-serialbattery** — mr-manuel's driver; connects JKBMS via `/dev/ttyUSB1`; fetched from GitHub at install time (latest stable)

## Repo Changes

### New: `setup.sh`

Run from local machine. Sequence:

1. SSH into Venus, download and run serialbattery `install.sh --stable` (non-interactive; also installs `overlay-fs` automatically)
2. SCP `config/serialbattery-config.ini` to `/data/apps/dbus-serialbattery/config.ini` — must happen after step 1 so it overwrites the fresh install's default
3. Call `./deploy.sh` — deploys dbus-mqtt-meter (unchanged)

Target host: `root@venus` (hardcoded, matches `deploy.sh`)

### New: `config/serialbattery-config.ini`

Committed to repo. Contains only non-default overrides:

```ini
[DEFAULT]
CVCM_ENABLE = True
```

### Unchanged

- `deploy.sh` — untouched
- `service/run` — MQTT broker IP (`192.168.227.19`) stays hardcoded

## Install Order on Fresh Card

1. Boot Venus OS, connect to network
2. Clone this repo on local machine (or ensure it's up to date)
3. Run `./setup.sh` — installs serialbattery + overlay-fs + dbus-mqtt-meter in one shot
4. Re-pair VRM if needed (auth token not preserved)
