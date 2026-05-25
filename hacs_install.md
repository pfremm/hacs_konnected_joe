# Kamado Joe Grill Monitor — Installation Guide

## Prerequisites

- Home Assistant 2023.6.0 or later
- [HACS](https://hacs.xyz) installed
- A Kamado Joe account (the same login used in the Kamado Joe iOS app)
- Your grill's **Device ID** and **Thing Name** (see below)

---

## Finding Your Device ID and Thing Name

These two values are required during setup and are not displayed in the Kamado Joe app UI. You need to capture them from the app's API traffic once.


Use a proxy tool such as [mitmproxy](https://mitmproxy.org) or [Charles Proxy](https://www.charlesproxy.com) while the Kamado Joe iOS app is open:

1. Configure your phone to route traffic through the proxy
2. Open the Kamado Joe app and let it load your grill
3. Look for a request to:
   ```
   GET https://cas.kamadojoe.com/api/v1/paired-device/{DEVICE_ID}/shadows/current?thing_name={THING_NAME}
   ```
4. Copy both values from that URL

---

## Installation via HACS

### Step 1 — Add this repository to HACS

1. In Home Assistant, go to **HACS → Integrations**
2. Click the three-dot menu (⋮) in the top-right corner
3. Select **Custom repositories**
4. Enter the GitHub URL for this repo and set the category to **Integration**
5. Click **Add**

### Step 2 — Install the integration

1. Search for **Kamado Joe** in HACS → Integrations
2. Click **Download**
3. Restart Home Assistant

---

## Installation without HACS (manual)

1. Copy the `custom_components/kamado_joe/` folder from this repo into your Home Assistant config directory:
   ```
   config/
   └── custom_components/
       └── kamado_joe/       ← copy this entire folder here
           ├── __init__.py
           ├── binary_sensor.py
           ├── config_flow.py
           ├── const.py
           ├── coordinator.py
           ├── manifest.json
           ├── sensor.py
           ├── strings.json
           └── translations/
               └── en.json
   ```
2. Restart Home Assistant

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Kamado Joe**
3. Fill in the form:

   | Field | Description | Example |
   |-------|-------------|---------|
   | Email address | Your Kamado Joe account email | `you@example.com` |
   | Password | Your Kamado Joe account password | |
   | Device ID | Grill MAC address (no colons) | `34ab959a8ec2` |
   | Thing Name | IoT device identifier from API | `451402ba5392ce1796870c5fb8a245f0` |
   | Poll interval | How often to check the grill (seconds) | `30` |

4. Click **Submit** — the integration will verify your credentials and create the device

---

## Entities Created

After setup, Home Assistant creates one device with four entities:

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.kamado_joe_temperature` | Sensor | Current grill temperature (°F or °C). Only available when grill is powered on. |
| `binary_sensor.kamado_joe_power` | Binary Sensor | `ON` when grill is powered on |
| `binary_sensor.kamado_joe_heating` | Binary Sensor | `ON` when one or more heating elements are active |
| `binary_sensor.kamado_joe_power_outage` | Binary Sensor | `ON` when the grill lost power before reaching its target temperature. Stays latched until the grill is powered back on. |

---

## Power Outage Automation Example

This example sends a mobile push notification if the grill loses power mid-cook:

```yaml
alias: Kamado Joe Power Outage Alert
trigger:
  - platform: state
    entity_id: binary_sensor.kamado_joe_power_outage
    to: "on"
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "🔥 Grill Power Outage!"
      message: >
        Your Kamado Joe lost power before reaching its target temperature.
        Last temp: {{ state_attr('sensor.kamado_joe_temperature', 'last_temperature') }}
```

---

## Running the Test Suite

The tests run without a full Home Assistant installation. All dependencies are standard Python packages.

### Install test dependencies

```bash
pip install pytest pytest-asyncio aiohttp
```

### Run tests

From the `hacs_kamadojoe/` directory:

```bash
python3 -m pytest tests/ -v
```

Expected output: **46 passed**.

### What is tested

| File | Coverage |
|------|---------|
| `tests/test_coordinator.py` | API data parsing, power outage state machine, token refresh and error handling |
| `tests/test_binary_sensor.py` | Power, Heating, and Power Outage sensor states and attributes |
| `tests/test_sensor.py` | Temperature sensor values, units (°F/°C), attributes, and device info |

### Note on the HA stubs

Because `homeassistant` requires compiled dependencies that may not build on all Python versions, the test suite includes lightweight stubs under `tests/stubs/homeassistant/`. These mock just enough of the HA framework (entities, coordinators, exceptions) for the integration logic to be imported and exercised without a running HA instance.

