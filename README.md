# WaveSentinel: Real-Time 802.11 Wireless Intrusion Detection Dashboard

Repository name: `wavesentinel-wids`

WaveSentinel is a defensive-only wireless intrusion detection system for authorized lab environments. It captures live 802.11 traffic from a monitor-mode adapter, detects suspicious wireless behavior, logs runtime evidence, and presents both a simple view and an analyst view in a Flask dashboard.

## Defensive-Only Scope

- Detection, logging, visualization, and documentation only
- No attack automation
- No deauthentication execution
- No packet injection or offensive orchestration

## Requirements

- Kali Linux or another Linux lab host
- Python 3.10 or newer
- Monitor-mode capable wireless adapter
- Root privileges or equivalent packet capture capability
- `iw`, `iwconfig`, and `airmon-ng`
- Python packages from `requirements.txt`

Install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Known Working Lab Setup

- Project path example: `/home/kali/Desktop/wavesentinel-wids`
- Wireless adapter: `wlan0` using `rtw89_8851bu`
- Monitor interface: `wlan0mon`
- Working channel: `4`
- Lab AP: `G10D_Lab_Env-2.4GHz`
- Lab BSSID: `FC:3F:FC:93:7F:B1`

## Monitor-Mode Setup

```bash
sudo airmon-ng start wlan0
sudo iw dev wlan0mon set channel 4
```

`airmon-ng` may rename long adapter names to `wlan0mon`. Always confirm the actual monitor interface before starting the engine.

## Run WaveSentinel

Start the engine:

```bash
sudo ./venv/bin/python3 -u main.py --interface wlan0mon --channel 4 --reset-session
```

Start the dashboard:

```bash
python3 web/app.py
```

Open `http://127.0.0.1:5000`.

## Session Behavior

- `--reset-session`
  Archives the current `data/` directory to `archive/session_TIMESTAMP.tar.gz`, then resets runtime files to a clean live session.
- `--reset-logs`
  Alias for `--reset-session`.
- Session lock
  WaveSentinel uses `runtime/wavesentinel_engine.lock` as the source of truth for engine ownership. Stale lock files are removed automatically.

## Dashboard Views

### Simple View

- Overall status: Safe / Warning / Critical
- Plain-language findings such as:
  - `Monitoring is running.`
  - `No deauthentication attack detected.`
  - `Open Wi-Fi network detected nearby.`
  - `Beacon activity may be normal if it comes from one network.`
- Short explanations for packet, AP, client, beacon, and deauth
- `What should I do?` recommendations

### Analyst View

- Raw AP inventory
- Raw client inventory
- Alert feed
- Traffic logs
- BSSID, ESSID, channel, security, RSSI, and frame counts
- Filters for severity, attack type, BSSID, ESSID, and channel

## Detection Defaults

- Beacon Flood default threshold: `300` beacons in `10` seconds
- Beacon Flood also requires the configured minimum number of unique SSIDs
- Heavy beaconing from one SSID is treated as normal or informational, not a HIGH Beacon Flood by itself

## Troubleshooting

### Stale PID or false session lock

If WaveSentinel says another engine is running, it now checks only the PID stored in `runtime/wavesentinel_engine.lock`. If the PID is stale, the lock is removed automatically and startup continues.

### Do not use CTRL+Z

Use `CTRL+C` to stop WaveSentinel safely.

If you press `CTRL+Z`, WaveSentinel prints:

```text
Do not use CTRL+Z. Use CTRL+C to stop WaveSentinel safely.
```

The engine then shuts down cleanly and updates `data/status.json` to:

- `running=false`
- `state="Stopped"`
- `message="Monitoring stopped safely."`

### Wrong interface name

If `wlan0mon` does not exist, check whether `airmon-ng` created a different monitor interface name. Long adapter names are often renamed to `wlan0mon`.

### Monitor mode not enabled

WaveSentinel validates that the selected interface exists and is in monitor mode before capture starts. If it is still in managed mode, fix the monitor-mode setup and re-run the engine.

### No packets captured

If no packets are captured after 15 seconds, `data/status.json` is updated with:

```text
No packets captured. Check monitor mode, channel, adapter driver, or interface name.
```

Check:

- monitor mode
- channel lock
- adapter driver
- interface name after `airmon-ng`

### Beacon false positives

Normal AP beaconing around 80-100 beacons per 10 seconds should not trigger a HIGH Beacon Flood by default. If you only see one SSID, treat that as normal beacon activity unless other evidence suggests abuse.

## Runtime Outputs

WaveSentinel writes live runtime data to:

- `data/alerts.csv`
- `data/alerts.json`
- `data/traffic_logs.csv`
- `data/devices.json`
- `data/status.json`
- `data/activity_logs.json`

## Contributor Notes

- Public contribution rules are in `CONTRIBUTING.md`
- Maintainer details and project contributor scope are in `CONTRIBUTOR.md`
- Developer workflow notes are in `DEVELOPMENT.md`
