# Mouse Battery Tray

A lightweight Windows system tray application that shows the live battery level of the
**Feinmann F01** (including the Noctua Edition), connected either over 2.4 GHz via the
**Pulsar LINK 2 Dongle** or by cable.

This is a personal fork of [incconutwo/mouse-battery-tray](https://github.com/incconutwo/mouse-battery-tray),
stripped down to a single device and extended with the LINK 2 protocol.

---

## Supported Hardware

| Device | VID | PID | Notes |
| :--- | :--- | :--- | :--- |
| Pulsar LINK 2 Dongle | `0x3710` | `0x5504` | 2.4 GHz |
| Feinmann F01 / Noctua Edition | `0x3710` | `0x7507` | Cabled |

Both expose the same vendor collection and answer the same query, so wired mode reports a
real battery level and charging state rather than a placeholder.

---

## How It Works

The dongle sends no unsolicited telemetry, so the battery is polled every 10 seconds: a
17-byte command is written to vendor usage page `0xff02` (report ID `0x08`, command `0x04`)
and the reply is read back off the same collection.

```
query  08 04 00 00 00 00 00 00 00 00 00 00 00 00 00 00 49
reply  08 04 00 00 00 02 64 00 10 19 00 00 00 00 00 00 ..
                          |  |  \-----/
                          |  |     pack voltage, mV big-endian
                          |  charging flag
                          battery %, in 5% steps
```

Every packet ends with a checksum of `(0x55 - sum(bytes[0..15])) & 0xFF`.

The percentage comes from the firmware's own estimate rather than being derived from the
voltage. A voltage curve was tried and fitted the low 40s well but read 14 points low at
4000 mV, whereas the firmware value tracks Pulsar's own tools to within a few percent and
detects a full charge by charge-taper rather than voltage alone.

The mouse stops answering once it sleeps on idle, which is the default behaviour. A missing
reply therefore means "asleep", not "disconnected", and the last known level is retained.

---

## Features

- **Live battery percentage** drawn directly on the tray icon as a coloured number.
  - Green at 50% and above, orange from 20-49%, red below 20%.
- **Charging bolt icon** that fills in 20 steps: red at or below 5%, green at 100%, and
  progressively filled blue in between.
- **Pack voltage in the tooltip**, shown as current against the highest ever recorded.
- **Automatic light/dark taskbar theming.**
- **Start with Windows toggle**, written to `HKCU` so it needs no admin rights.

---

## Installation

Requires [Python 3.10+](https://www.python.org/).

```powershell
pip install hidapi pystray pillow
```

## Running

```powershell
pythonw battery_tray.pyw   # silent background
python battery_tray.pyw    # with a console, for debugging
```

## Building an Executable

```powershell
pip install pyinstaller
python -m PyInstaller --onefile --noconsole --name MouseBatteryTray --collect-all hid battery_tray.pyw
```

`--collect-all hid` is required. Without it the build succeeds but the executable exits
immediately, because `hidapi` ships a compiled extension the dependency scan misses and
`--noconsole` discards the traceback.

---

## Troubleshooting

- **Icon stays on `??`** — the dongle is not plugged in and the mouse is not cabled.
  `??` means no supported device was found at all.
- **Icon shows `?`** — the device was found but returned no reading. Normally this only
  appears before the first successful poll.
- **Tooltip stops updating** — check that Pulsar's own software is not open and holding the
  device.

---

## Credits

- **[incconutwo](https://github.com/incconutwo)** — original Mouse Battery Tray project.
- **[@len0c](https://github.com/len0c)** — HID protocol groundwork in the upstream project.

Licensed under the MIT License. See [LICENSE](LICENSE).
