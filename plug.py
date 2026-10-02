"""Control and monitor a Tuya-based smart plug (e.g. Wipro) over the local network.

Setup:
    pip install tinytuya
    python -m tinytuya wizard     # creates devices.json with IDs and local keys
    python -m tinytuya scan       # finds IP addresses and protocol versions

Use as a module:
    from plug import *
    d = load_device("My Plug")
    turn_on(d)
    print(get_energy(d))

Or from the command line:
    python plug.py status
    python plug.py on | off | toggle
    python plug.py energy
    python plug.py countdown 600       # switch state flips after 600 s (0 cancels)
    python plug.py log power.csv 10    # log energy every 10 s until Ctrl+C
    python plug.py raw                 # dump all raw datapoints

NOTE: DPS numbers below are the common Tuya defaults. They vary by model, so
run `python plug.py raw` once and adjust the constants if values look wrong.
"""
import csv
import json
import sys
import time
from datetime import datetime

import tinytuya

# --- Datapoint (DPS) IDs and scaling: adjust to match your model ------------
DPS_SWITCH = "1"      # on/off
DPS_COUNTDOWN = "9"   # countdown timer in seconds (0 = off)
DPS_CURRENT = "18"    # milliamps
DPS_POWER = "19"      # 0.1 W units
DPS_VOLTAGE = "20"    # 0.1 V units


# --- Connection --------------------------------------------------------------
def load_device(name=None, config_path="devices.json", version=None):
    """Create a device from devices.json. Uses the first device if name is None.

    `name` matches the device name or ID. Falls back to IP "Auto" if the scan
    hasn't recorded an address.
    """
    with open(config_path) as f:
        devices = json.load(f)
    if not devices:
        raise ValueError("devices.json is empty; run `python -m tinytuya wizard`.")
    info = devices[0]
    if name:
        matches = [x for x in devices if name in (x.get("name"), x.get("id"))]
        if not matches:
            raise ValueError(f"No device named or with ID {name!r} in {config_path}")
        info = matches[0]
    d = tinytuya.OutletDevice(
        info["id"],
        info.get("ip") or "Auto",
        info["key"],
        version=version or float(info.get("ver") or 3.3),
    )
    d.set_socketTimeout(5)
    return d


def connect(device_id, ip, local_key, version=3.3):
    """Create a device directly from credentials instead of devices.json."""
    d = tinytuya.OutletDevice(device_id, ip, local_key, version=version)
    d.set_socketTimeout(5)
    return d


# --- State -------------------------------------------------------------------
def get_status(d):
    """Return the raw status dict, raising on errors."""
    data = d.status()
    if "Error" in data:
        raise ConnectionError(f"Plug error: {data}")
    return data


def get_dps(d):
    """Return just the datapoints dict."""
    return get_status(d).get("dps", {})


def is_on(d):
    return bool(get_dps(d).get(DPS_SWITCH))


# --- Control -----------------------------------------------------------------
def turn_on(d):
    return d.turn_on()


def turn_off(d):
    return d.turn_off()


def toggle(d):
    """Flip the current state and return the new state (True = on)."""
    new_state = not is_on(d)
    d.set_status(new_state, switch=int(DPS_SWITCH))
    return new_state


def set_countdown(d, seconds):
    """Flip the plug's state after `seconds`. Pass 0 to cancel."""
    return d.set_value(DPS_COUNTDOWN, int(seconds))


def get_countdown(d):
    """Seconds remaining on the countdown, or None if the plug doesn't report one."""
    value = get_dps(d).get(DPS_COUNTDOWN)
    return None if value is None else int(value)


def set_dps(d, dps_id, value):
    """Set any datapoint directly, for model-specific features
    (e.g. indicator light, child lock, power-on behaviour)."""
    return d.set_value(str(dps_id), value)


# --- Energy monitoring -------------------------------------------------------
def get_energy(d):
    """Return a dict with watts, volts and amps (None for anything unsupported)."""
    dps = get_dps(d)

    def scaled(key, divisor):
        return dps[key] / divisor if key in dps else None

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "on": bool(dps.get(DPS_SWITCH)),
        "watts": scaled(DPS_POWER, 10),
        "volts": scaled(DPS_VOLTAGE, 10),
        "amps": scaled(DPS_CURRENT, 1000),
    }


def log_energy(d, path="power_log.csv", interval=10, duration=None):
    """Append energy readings to a CSV every `interval` seconds.

    Runs until `duration` seconds have passed, or until Ctrl+C if None.
    Keep interval >= 5 s: the plug allows one local connection at a time.
    """
    fields = ["timestamp", "on", "watts", "volts", "amps"]
    start = time.time()
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if f.tell() == 0:
            writer.writeheader()
        try:
            while duration is None or time.time() - start < duration:
                try:
                    row = get_energy(d)
                    writer.writerow(row)
                    f.flush()
                    print(row)
                except ConnectionError as e:
                    print("Skipped a reading:", e)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopped logging.")


# --- Command line ------------------------------------------------------------
def main(argv):
    if not argv:
        print(__doc__)
        return
    cmd, args = argv[0], argv[1:]
    d = load_device()

    if cmd == "status":
        print("ON" if is_on(d) else "OFF")
    elif cmd == "on":
        turn_on(d)
        print("Turned on")
    elif cmd == "off":
        turn_off(d)
        print("Turned off")
    elif cmd == "toggle":
        print("Now ON" if toggle(d) else "Now OFF")
    elif cmd == "energy":
        print(json.dumps(get_energy(d), indent=2))
    elif cmd == "countdown":
        if args:
            set_countdown(d, args[0])
            print(f"Countdown set to {args[0]} s")
        else:
            print("Countdown remaining:", get_countdown(d))
    elif cmd == "log":
        log_energy(d, args[0] if args else "power_log.csv",
                   float(args[1]) if len(args) > 1 else 10)
    elif cmd == "raw":
        print(json.dumps(get_status(d), indent=2))
    else:
        print(f"Unknown command {cmd!r}\n{__doc__}")


if __name__ == "__main__":
    main(sys.argv[1:])
