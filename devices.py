import time
import hid
from typing import Optional, Tuple, List

# =============================================================================
# Pulsar LINK 2 Protocol (16-byte Output/Input reports on usage page 0xff02)
#
# The dongle never sends unsolicited telemetry, so it must be polled: write the
# 17-byte query, then read the reply off the same collection.
# Packet layout, captured from Pulsar's own configuration software:
#   query [0x08, cmd, 0x00 * 14, checksum]
#   reply [0x08, cmd, 0, 0, 0, status, fw_est, charging, mV_hi, mV_lo, 0 * 6, csum]
#
# Byte 6 is the firmware's own battery estimate, quantised to 5% steps, and
# tracks the vendor tools to within 3% for most of the range. It reaches 100 by
# charge-taper detection rather than voltage alone, flipping 95 -> 100 while the
# pack voltage was falling from 4176 to 4154 mV. Note it then decays back to 95
# as the pack settles post-charge, where the vendor tools latch at 100.
# A voltage-derived level was tried instead and read 14 points low at 4000 mV.
#
# The mouse stops answering once it sleeps on idle, so a missing reply means
# "asleep", not "disconnected" -- callers should keep the previous reading.
#
# Cabled, the mouse enumerates on its own PID with the same vendor collections
# and answers the same query, so wired mode reports a real level plus charging.
# =============================================================================
PULSAR_VID = 0x3710
PULSAR_USAGE_PAGE = 0xff02
PULSAR_REPORT_ID = 0x08
PULSAR_CMD_BATTERY = 0x04

PULSAR_DEVICES = {
    0x5504: "Pulsar LINK 2 Dongle",
    0x7507: "Feinmann F01 Noctua Edition",
}


def _pulsar_checksum(pkt: List[int]) -> int:
    """Trailing byte of every packet is 0x55 minus the sum of the preceding 16."""
    return (0x55 - sum(pkt[:16])) & 0xFF


def _pulsar_build(cmd: int) -> List[int]:
    pkt = [PULSAR_REPORT_ID, cmd] + [0x00] * 14
    pkt.append(_pulsar_checksum(pkt))
    return pkt


def find_pulsar() -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """Return (path, model_name, pid) for the Pulsar LINK 2 vendor collection."""
    for d in hid.enumerate(PULSAR_VID):
        pid = d['product_id']
        if pid in PULSAR_DEVICES and d.get('usage_page') == PULSAR_USAGE_PAGE:
            return d['path'], PULSAR_DEVICES[pid], pid
    return None, None, None


def read_pulsar_battery(path: str) -> Tuple[Optional[int], Optional[bool], Optional[int]]:
    """Active: send the 0x04 battery query. Returns (battery%, charging, millivolts)."""
    try:
        dev = hid.device()
        dev.open_path(path.encode('utf-8') if isinstance(path, str) else path)
        dev.set_nonblocking(True)
    except OSError:
        return None, None, None

    try:
        try:
            dev.write(bytes(_pulsar_build(PULSAR_CMD_BATTERY)))
        except OSError:
            return None, None, None

        deadline = time.time() + 1.5
        while time.time() < deadline:
            try:
                resp = dev.read(17)
            except OSError:
                break
            if resp:
                b = list(resp)
                if (len(b) >= 17 and b[0] == PULSAR_REPORT_ID
                        and b[1] == PULSAR_CMD_BATTERY
                        and b[16] == _pulsar_checksum(b)):
                    batt = b[6]
                    if 0 <= batt <= 100:
                        return batt, bool(b[7]), (b[8] << 8) | b[9]
            time.sleep(0.01)
        return None, None, None
    finally:
        try:
            dev.close()
        except Exception:
            pass
