# Wireless Intrusion Detection System

This repository is a defensive WIDS focused on real captured 802.11 traffic from a monitor-mode adapter. It does not include demo mode, PCAP replay mode, desktop GUI code, or any attack execution automation.

## What it does

- Uses Scapy live sniffing with `store=False`.
- Validates that the selected capture interface is really in monitor mode.
- Detects when `airmon-ng` renamed the adapter and surfaces the real capture interface in the dashboard.
- Uses one detection engine for:
  - Deauthentication flood
  - Disassociation flood
  - Beacon flood
  - Probe request flood
  - Evil Twin suspicion
  - Open network detection
  - ARP spoofing suspicion where the captured traffic allows it
- Persists runtime telemetry to:
  - `data/alerts.csv`
  - `data/alerts.json`
  - `data/traffic_logs.csv`
  - `data/devices.json`
  - `data/status.json`
  - `data/activity_logs.json`

## Recommended two-adapter setup

Use two wireless adapters in the lab:

- Internal adapter: stay in managed mode for Internet access.
  - Example: `wlp3s0`
- External USB adapter: move to monitor mode for capture.
  - Example hardware path: `wlx6c1ff7d85510`

Real lab note:

- `airmon-ng` can rename a long interface name when monitor mode starts.
- Example:
  - original adapter: `wlx6c1ff7d85510`
  - active monitor interface after rename: `wlan0mon`

The WIDS engine now reports the real capture interface so the dashboard matches the actual monitor device.

## Requirements

- Linux lab host
- A monitor-mode capable USB Wi-Fi adapter
- Root privileges or equivalent packet capture capabilities
- `iw`, `iwconfig`, and Scapy available

Install dependencies:

```bash
pip install -r requirements.txt
```

## Prepare the monitor adapter

Exact example for the tested lab:

```bash
sudo airmon-ng start wlx6c1ff7d85510 4
```

That can create `wlan0mon` as the active monitor interface.

## Start live monitoring

Exact example for the tested lab:

```bash
sudo ../venv/bin/python3 -u main.py --interface wlan0mon --channel 4 --reset-session
```

Another example with a target BSSID:

```bash
sudo ../venv/bin/python3 -u main.py --interface wlan0mon --channel 4 --bssid FC:3F:FC:93:7F:B1
```

## Start the dashboard

```bash
python3 web/app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Session behavior

- `--reset-session`
  - Archives the current `data/` folder into `archive/session_TIMESTAMP.tar.gz`
  - Resets alerts, traffic logs, devices, status, and activity logs
- `--reset-logs`
  - Alias for `--reset-session`
- A PID lock file prevents multiple WIDS engines from running at the same time
- `CTRL+C` is the supported stop path
- `CTRL+Z` is intentionally ignored with a warning so you do not leave stopped engine processes behind

## Dashboard views

### Non-Technical View

- Safe / Warning / Critical summary
- Plain-language explanations
- Simple definitions for AP, client, packet, beacon, and deauth
- Recommended next actions

### Technical Analyst View

- Real capture interface and channel
- AP and client inventory
- Alert feed with severity and MITRE mapping
- Traffic logs table
- Filters for severity, attack type, BSSID, ESSID, and channel
- Export links for CSV and JSON artifacts

## Notes on beacon flood tuning

- Default beacon flood threshold is `300` beacons in `10` seconds
- The detector now requires:
  - `beacon_count >= threshold`
  - `unique_ssids >= unique_ssids`
- A single AP sending normal beacon traffic by itself should not trigger a HIGH beacon flood alert
- The dashboard can still show a note that heavy beaconing from one SSID may be normal AP behavior

## Defensive scope

This project is detection-only.

- No deauth transmit automation
- No `aireplay-ng` execution
- No attack orchestration
- Monitoring, logging, and visualization only
