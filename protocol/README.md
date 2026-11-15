# TRACE protocol v1: NDJSON over USB CDC / UART

> Historical prototype protocol. The November 12 desktop/USB architecture requires
> an expanded identity/capability, session/configuration, activation/deactivation,
> validity/freshness and heartbeat contract. See `docs/CONCEPT_UPDATE_2026-11-12.md`.
> The new concept UI uses a separate offline session service; it does not claim this
> v1 transport implements the revised hardware lifecycle.

UTF-8, one JSON object and LF per message, at most 262144 bytes per line.
Malformed or oversized messages are rejected. Prototype serial default: 115200
baud, 8N1. A simulated device uses the same encode/decode path.

## Handshake and capabilities

Host sends `{"t":"hello","protocol":1,"id":"command-id"}`. Device replies:

```json
{"t":"hello","protocol":1,"mode":"serial","max_channels":8,"max_rate_hz":1000000,"max_depth":20000,"scan_hz":1000,"publish_hz":10,"vic_supported":[],"vic_max_hz":0,"hardware_verified":false}
```

Numbers above are illustrative, not measured hardware limits. Firmware must report
its actual supported configuration; set hardware_verified only after bench validation.
The backend refuses configurations exceeding these capabilities. Simulated limits
are 16 channels, 10 MS/s, 200000 samples; these are generated timestamps, not a
claim that Python samples at 10 MHz.

Every host command has an `id`. Reply `{"t":"ack","cmd":"cfg","id":"..."}`
or `{"t":"err","id":"...","msg":"reason"}`. An ack means accepted, not
that emulation or capture finished. UI readiness follows status messages.

## Scanning

`cfg`: `vh`, `vl` in integer mV, `scan_hz` in Hz.
`watch`: `ids`, the mapped channels requested by the backend.
`frame`: `ts` monotonic device milliseconds, `ch`: array of `{id,mv}`.
Each frame is a complete published snapshot of the requested channels. Omitted
channels become UNKNOWN, never zero. Publish snapshots around 10 Hz independently
of the hardware scan frequency. No fresh frame for 3 seconds invalidates live UI.
HIGH >= vh; LOW <= vl; intermediate voltage is FLOATING/indeterminate. This label
is not an electrical high-impedance detector.

## Capture

Host `cap_cfg`: `ch` ordered channel IDs, `rate` Hz, `depth` samples,
`pre` samples (1 <= pre < depth), `trig:{src,edge}` (rise/fall/either).
Then `cap_arm` with a new `capture_id`. `cap_stop` cancels acquisition; acknowledge
with `cap_stopped`. Continuous mode is host-managed repeated single captures.

```json
{"t":"cap_data","capture_id":"abc","seq":0,"t0":0,"dt":1000,"depth":1000,"ch":["BB01A","BB02A"],"trigger_index":100,"ev":[[0,0],[100,1],[100,3]]}
{"t":"cap_done","capture_id":"abc","chunks":1,"overflow":false,"dropped_samples":0}
```

`dt` is ns/sample; `t0` is the device time origin in ns. `trigger_index` is relative
to capture start. Each event is `[delta_samples,bitmask]`, bit 0 = ch[0]. The first
event of the WHOLE capture has delta 0 and is the state at sample 0. All later
deltas are positive and relative to the previous event, including across chunks.
Last state persists to `depth * dt` (exclusive). Each chunk has a contiguous `seq`
starting at zero. First chunk carries metadata; do not repeat a zero-delta initial
event in later chunks. Keep each chunk bounded; at most depth events total.
Stale capture IDs are ignored. Missing/reordered chunks invalidate the capture.
No analog samples are represented by this format. Export supports JSON and VCD.

## Virtual IC

`vic_load` with `ic`, `vic_release`. Firmware configures physical pin directions
only after confirming sensed VCC 4500..5500 mV and |GND| <= 100 mV. Power pins are
passive. A mandatory power/communication watchdog must release all driven outputs
on power fault, disconnect, reset, or invalid mapping. Never drive MCU pins directly
into 5 V logic. Translator enables must start disabled before firmware boots.

`vic_status`: `ic` (null when released), `state`, `vcc_mv`, `gnd_mv`, `pins` mapping
pin-number strings to bits, `max_hz`, `hardware_verified`. `ready` comes from firmware.
`vic_pin`, `vic_power`, `sim_set` are simulator-only controls, not hardware commands.

Physical firmware is intentionally not fabricated: MCU, ADC, mux pins, capture
matrix, translator wiring, and power supervision are not supplied. Implement the
contract on the selected MCU; perform PIO/DMA capture there, not over Python GPIO.
JSON capture transfer occurs after acquisition; it cannot sustain raw MHz samples.
