# Local control of a Wipro Smart Plug (Tuya-based) with Python

Control and read energy data from a Wipro smart plug over your local network, using [TinyTuya](https://github.com/jasonacox/tinytuya). Works from a laptop or a Raspberry Pi; nothing here is platform-specific.

Wipro smart plugs are rebranded Tuya devices, and the Wipro Next Smart Home app is a Tuya white-label app. Cloud access is needed **once**, to fetch the plug's local key. After that, everything runs locally.

## Files

| File | Purpose |
|------|---------|
| `plug.py` | Module and command-line tool: on/off/toggle, status, energy, countdown, CSV logging, raw datapoints |
| `read_plug.py` | Minimal script that prints the plug's current state |
| `devices.json` | Created by the wizard; holds device ID, local key, IP (**keep private**) |

## Requirements

- Python 3.7+
- `pip install tinytuya`
- Computer and plug on the **same Wi-Fi network** (same subnet). The plug itself needs 2.4 GHz Wi-Fi; the computer can be on 5 GHz if the router bridges both bands.
- Turn off VPNs while testing, and avoid "guest" networks or AP isolation.

## Step 1: Pair the plug

The Wipro Next Smart Home app **does not work** for this: its account can't be linked to a Tuya developer project. Use the **Smart Life** app instead.

1. Install **Smart Life** and create an account, choosing India as your region.
2. Factory reset the plug (hold its button until the light blinks rapidly).
3. In Smart Life, Add Device → Socket (Wi-Fi), and complete pairing (2.4 GHz Wi-Fi only).

Pairing in Smart Life removes the plug from the Wipro app, and any Alexa/Google Home links will need redoing through the Smart Life skill.

## Step 2: Create a free Tuya developer project

You don't need an API key beforehand. You create one here.

1. Sign up at [iot.tuya.com](https://iot.tuya.com) (separate from your app login).
2. Go to **Cloud → Development → Create Cloud Project**.
   - Industry: Smart Home
   - Development method: Smart Home
   - Data center: **India** (a wrong data center means no devices appear)
3. Make sure the **IoT Core** API is subscribed (Service API tab). It's free, though the trial may need renewing.
4. On the project's **Overview** tab, copy the **Access ID/Client ID** and **Access Secret/Client Secret**.

## Step 3: Link your app account

1. In the project, open **Devices → Link App Account → Add App Account**.
2. A QR code appears. Open the scanner in **Smart Life** (**Me → scan icon**, not your phone camera) and scan it quickly. The code expires within a minute or two.
3. Confirm the login in the app. Your plug should appear in the device list.
4. Copy any one **Device ID** from the list.

## Step 4: Get the local key and IP address

```bash
python -m tinytuya wizard
```

Enter the Access ID, Access Secret, and Device ID when asked, and choose the India region. This writes `devices.json` containing each device's **local key**.

Then find the plug's IP address and protocol version:

```bash
python -m tinytuya scan
```

Give the plug a DHCP reservation or static IP in your router so its address doesn't change. Alternatively, rerun `scan` when it does.

### What is the local key?

A 16-character secret unique to each device. The plug uses it to encrypt local traffic, and it ignores commands that don't use it. Tuya generates it when the plug is paired, and it's stored in Tuya's cloud, which is why Step 2 is needed. **It changes if you re-pair the plug**, so fetch it after pairing is finished. Treat it like a password.

## Step 5: Use the scripts

Keep `devices.json` in the same folder as the scripts.

### Quick state check

Edit the constants at the top of `read_plug.py`, then:

```bash
python read_plug.py
```

### Command line

```bash
python plug.py status          # ON or OFF
python plug.py on
python plug.py off
python plug.py toggle
python plug.py energy          # watts, volts, amps as JSON
python plug.py countdown 600   # flip state after 600 s (0 cancels)
python plug.py countdown       # show remaining time
python plug.py log power.csv 10  # log every 10 s until Ctrl+C
python plug.py raw             # all raw datapoints
```

### As a module

```python
from plug import *

d = load_device()            # or load_device("My Plug")
turn_on(d)
print(get_energy(d))         # {'timestamp': ..., 'on': True, 'watts': 42.3, ...}
set_countdown(d, 300)
log_energy(d, "power.csv", interval=10, duration=3600)
set_dps(d, 40, "relay")      # any model-specific datapoint
```

If you don't use `devices.json`, create a device directly:

```python
d = connect("DEVICE_ID", "192.168.1.50", "LOCAL_KEY", version=3.3)
```

## Function reference

Every function in `plug.py`, in one snippet:

```python
from plug import *

# --- Connect -----------------------------------------------------------
d = load_device()                       # first device in devices.json
d = load_device("My Plug")              # by device name or ID
d = load_device("My Plug", config_path="devices.json", version=3.4)
d = connect("DEVICE_ID", "192.168.1.50", "LOCAL_KEY", version=3.3)  # without devices.json

# --- Read state --------------------------------------------------------
status = get_status(d)                  # full raw response; raises ConnectionError on failure
dps    = get_dps(d)                     # just the datapoints dict, e.g. {'1': True, '19': 423, ...}
on     = is_on(d)                       # True / False

# --- Control -----------------------------------------------------------
turn_on(d)
turn_off(d)
new_state = toggle(d)                   # flips the state and returns it (True = on)

# --- Countdown timer ---------------------------------------------------
set_countdown(d, 600)                   # flip state after 600 seconds
set_countdown(d, 0)                     # cancel the countdown
remaining = get_countdown(d)            # seconds left, or None if unsupported

# --- Energy monitoring -------------------------------------------------
energy = get_energy(d)                  # {'timestamp', 'on', 'watts', 'volts', 'amps'}
log_energy(d)                           # append to power_log.csv every 10 s until Ctrl+C
log_energy(d, "power.csv", interval=5, duration=3600)   # custom file, 5 s interval, stop after 1 hour

# --- Anything model-specific -------------------------------------------
set_dps(d, 40, "relay")                 # set any datapoint by ID (check `python plug.py raw`)
```

Command-line equivalents are listed under "Command line" above. `main()` simply maps those commands onto these functions.

## Datapoints (DPS)

Tuya devices expose features as numbered datapoints. These defaults in `plug.py` are common but **not universal**:

| DPS | Meaning | Scaling |
|-----|---------|---------|
| 1 | On/off | boolean |
| 9 | Countdown timer | seconds |
| 18 | Current | mA (÷1000 for A) |
| 19 | Power | 0.1 W (÷10 for W) |
| 20 | Voltage | 0.1 V (÷10 for V) |

Run `python plug.py raw` once. Plug in a load such as a lamp and see which values change, then edit the constants at the top of `plug.py` if needed. Models without energy monitoring won't report 18, 19, or 20.

## Scheduling

Tuya stores recurring schedules in the cloud in a model-specific format, so this project doesn't set them. Instead, call the script from your OS scheduler (cron on Linux/Pi, Task Scheduler on Windows):

```
# cron: on at 7:00, off at 22:00
0 7 * * *  cd /path/to/folder && python plug.py on
0 22 * * * cd /path/to/folder && python plug.py off
```

## Troubleshooting

| Problem | Likely cause and fix |
|---------|----------------------|
| QR code "expired" after scanning | You're probably using the Wipro Next app, which doesn't support this login (confirmed to fail). Re-pair the plug in Smart Life and scan with that app. Also scan quickly, since the code expires within a minute or two. |
| No devices in the Tuya console | Wrong data center (must be India), or the app account isn't linked. |
| "Permission deny" API errors | IoT Core isn't subscribed or its trial expired. Renew it (free) and rerun the wizard. |
| `scan` finds nothing | VPN on, guest network or AP isolation, firewall blocking UDP ports 6666/6667/7000, or the computer is on a different subnet. |
| Decode errors or "Err 914" | Wrong local key or protocol version. Re-pair → rerun the wizard, and use the version shown by `scan` (3.3, 3.4, or 3.5). |
| Plug shows offline in the app while the script runs | The plug accepts one local connection at a time. Poll no faster than every 5 s and close other connections. |
| Energy values missing or look wrong | Your model may not monitor energy, or uses different DPS IDs. Check `python plug.py raw`. |
| IP stopped working | The router gave the plug a new address. Rerun `python -m tinytuya scan`, or set `"ip": "Auto"` for slower auto-discovery. |

## Security notes

- `devices.json` contains local keys and your Tuya credentials may be stored in `tinytuya.json`. Don't commit them to Git or share them publicly. Add both to `.gitignore`.
- Anyone on your network who has a device's local key can control that device.

## Alternatives

- **Home Assistant**: the built-in Tuya integration (cloud) or the Tuya Local add-on (local) for dashboards and automations. Community reports suggest LocalTuya can be hard to connect on Wipro plugs, while Tuya Local has worked.
- **Tuya Cloud API**: remote control via TinyTuya's `Cloud` class; slower and rate-limited.
- **Tasmota**: fully local firmware, but many newer Tuya plugs can't be flashed without opening the device, and Wipro plugs are reported to be hard to open.
