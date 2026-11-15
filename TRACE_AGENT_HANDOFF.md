# TRACE workspace handoff for the next AI agent

> **Superseding update - 12 November 2026:** Read
> [docs/CONCEPT_UPDATE_2026-11-12.md](docs/CONCEPT_UPDATE_2026-11-12.md) first.
> Three new user-provided PDFs change the current direction to a desktop/USB
> application, a physical experiment locator, node-group monitoring and logical
> Virtual IC port assignments. The new four-view mock-up is served at `/`, with
> hardware disconnected and offline examples explicitly separated. The previous
> Pi/hotspot, decoder EXP4, package-pin dock and analyzer prototype remains at
> `/legacy`; those assumptions below are historical, not the latest specification.
> New files: `backend/concept.py`, `frontend/concept.*`, `tests/test_concept.py`,
> `tools/concept_browser_check.py`. Latest checks: 73 Python tests and 12 current
> page/viewport combinations passed. Physical USB integration remains pending.
>
> Continuation enhancements and remaining work are recorded in
> [docs/MOCKUP_ENHANCEMENTS_2026-11-12.md](docs/MOCKUP_ENHANCEMENTS_2026-11-12.md).

Updated: 5 November 2026 (Asia/Manila).

Workspace: `C:\Users\AndreiG\Python Mini Projects\T.R.A.C.E`

## 1. Read this first: what this project actually is today

**This is a working software prototype connected to simulated hardware. It is not yet an operational physical TRACE training board.**

The browser interface, Python backend, comparison logic, digital waveform viewer, simulator controls, and simulated IC behavior are implemented. The voltages, digital captures, faults, and dock readings currently come from Python-generated data. There is a reconnecting serial adapter and a firmware protocol, but **no real MCU firmware has been implemented in this repository and no physical board has been validated**.

The user explicitly asked whether this was still a simulation. We confirmed that it is more than a visual mockup, but does not prove that the physical system works. Preserve that distinction in all future explanations and thesis evidence.

The user's current request was to create this handoff, not to change application behavior or configure hardware. This document records future work; it is not blanket authorization to operate hardware, change network settings, or claim measurements.

## 2. Thesis context and working requirements

TRACE means **Teaching and Real-Time Analysis of Circuits and Experiments**. It is an RTU BS Computer Engineering capstone for the Logic Circuits and Design Laboratory.

The proposed board combines predefined experiment circuits, a central instrumented breadboard, voltage/logic-state monitoring, selected digital-signal capture, and a Virtual IC dock. The handoff describes approximately 15 experiment blocks and a 16-pin dock; final quantities and routing have not been supplied.

The intended experience is:

- Software runs on an onboard Raspberry Pi with a 5-inch, 800 x 480 touchscreen.
- Students use the board without needing their own laptop.
- The same local web interface can be opened from phones/tablets over the board's Wi-Fi hotspot.
- Runtime is offline: no accounts, analytics, CDN assets, or required external requests.
- Optional PC connection is useful for development and validation, but not required for normal student use.

### Source documents supplied by the user

These files are external to this repository. They may need to be supplied again on a different machine:

| Document | Original location |
| --- | --- |
| Original software handoff | `D:\geana\Downloads\TRACE_Software_Handoff_Prompt.md` |
| UI reference (five screens) | `D:\geana\Downloads\TRACE Software – UI Concept.pdf` |
| Thesis manuscript | `C:\Users\AndreiG\Documents\4th Year 1st Sem Documents Assignments\CpE Practice and Design 1\Capstone_Manuscript latest.pdf` |
| Value proposition | `C:\Users\AndreiG\Documents\4th Year 1st Sem Documents Assignments\CpE Practice and Design 1\Value Proposition.pdf` |

The UI concept was visually inspected and used as a reference, not a pixel-for-pixel specification. The original handoff requested review stops after each phase; the user subsequently said: **"just do everything even the front-end, we'll just reivew it later"**. That authorized the initial simulator-backed application work without phase-by-phase stops.

### Scope constraints to preserve

1. Report **what differs**: expected value, measured value, channel, and timing where available. Do not add step-by-step troubleshooting, recommended repairs, or student troubleshooting logs.
2. Digital capture only. The voltage monitor is not an analog oscilloscope.
3. Only mapped/selected contacts are monitored. Do not imply coverage of every breadboard hole.
4. Label Virtual IC behavior **"Emulated, logic-level"**. Do not claim equivalence to physical propagation, drive current, loading, or electrical characteristics.
5. No personal data, student accounts, or runtime external network dependencies.
6. Display actual device capabilities once measured. Simulator settings are not hardware results.

### Document conflicts still requiring researcher clarification

- Value proposition: guided troubleshooting/history. Manuscript: excludes troubleshooting instructions, corrective recommendations, and troubleshooting logs. Current implementation follows the restrictive manuscript/handoff scope.
- Manuscript: desktop application. Software handoff: onboard Pi/browser application. Current architecture follows the handoff; manuscript wording may need researcher revision.
- Manuscript scope describes hardware-backed Virtual IC functionality, while its delimitation says it will not physically replace ICs or automatically modify hardware configurations. Clarify the intended physical dock scope before final hardware implementation. Do not silently rewrite the manuscript.

## 3. Implemented software inventory

| Area | Current implementation | Important boundary |
| --- | --- | --- |
| Home | Experiment tiles, Free Build, connection/mode chips, local QR and configured URL/SSID | QR/SSID do not create a hotspot or prove one exists |
| Experiment | Active truth-table row, expected/observed outputs, voltages, MATCH/DIFF, observation, reset | Only two demonstration experiments, not the verified RTU manual |
| Breadboard | Example mapped-contact view, channel readings, selected slow timelines, threshold controls | 32 example contacts; routing is not final |
| Analyzer | Canvas waveforms, Single/Run/Stop, trigger selection, pretrigger, channel selection, zoom/pan, timebase auto-selection, cursors, bus value, expected overlay, mismatch windows, JSON/VCD exports | Generated digital captures; no real acquisition yet |
| Virtual IC | Library, DIP pinout, load/release, simulated input toggles, sensed-power display and simulated power fault | Python models only; nothing drives a physical dock |
| Diagnostics | Server-configured PIN, reference-meter comparison, absolute/percentage error, pass rate, CSV export | Records use simulated measurements in simulator mode; no automated physical timing/IC test bench |
| Backend | FastAPI, WebSocket snapshots, validation, settings, shared board state | Prototype command lifecycle needs hardware hardening |
| Device interface | NDJSON protocol, simulator, reconnecting pyserial transport | Serial selection does not create or flash firmware |
| Deployment | Windows launcher/setup, Pi service/kiosk/hotspot scripts, nginx example | Pi scripts are prepared, not tested on the final hardware |

IC models: **7400, 7404, 7408, 7432, 74138, 7483, 7474**. Counter IC models are not implemented. The 7474 model includes rising-edge handling and asynchronous preset/clear; it is not a metastability or setup/hold timing model.

Samples: **EXP1, two-input AND gate**, and **EXP4, 2-to-4 decoder**. Do not invent the missing official experiment list. Expected waveforms are demonstration fixtures: the default decoder reference uses a 20 ms capture, 1 MHz sampling, 2000 pretrigger samples, rising A trigger, and 1 kHz input-counter steps. Different capture timing can legitimately differ from that fixed fixture.

## 4. Repository map and actual stack

The final implementation uses **buildless HTML/CSS/native JavaScript**, not the React/TypeScript stack initially proposed during planning. There is no npm build requirement.

```text
T.R.A.C.E/
  backend/
    app.py                  FastAPI routes, runtime state, device ingestion, WebSocket
    logic.py                Classification, experiment validation/comparison, capture logic
    protocol.py             NDJSON framing, protocol version and line-size bound
    transport.py            Reconnecting serial adapter
  simulator/
    device.py               Generated frames/captures, faults, IC models and commands
  frontend/
    index.html              Application shell
    style.css               Dark-green/teal responsive UI
    app.js                  Screens, API/WebSocket client, canvas rendering
  data/
    channels.json           Editable channel IDs; physical routing fields currently null
    experiments/            Two sample JSON definitions
    ics/library.json        Pin names/directions, power pins and gate definitions
  tests/
    test_logic.py           Pure logic/model tests
    test_api.py             Simulator/API integration tests
  tools/browser_check.py    Optional Edge/Playwright acceptance checks
  protocol/README.md        Firmware message contract
  deploy/                  Pi installer, hotspot script, kiosk/service docs, nginx example
  docs/
    HARDWARE_VALIDATION.md  Bench integration/validation outline and datasheet links
    VALIDATION.md           Recorded software verification
  README.md                 Setup, use, scope and limitations
  TRACE.pyw                 Console-free Windows browser/server launcher
  setup.ps1                 Windows dependency setup and foreground launch
  run.py                    Uvicorn entry point
  requirements.txt          Runtime Python dependencies
  requirements-dev.txt      Test dependencies
  runtime/                  Local generated settings/logs/screenshots; ignored by Git
```

Runtime dependencies include FastAPI, Uvicorn, pyserial, qrcode and websockets. Tests use pytest/httpx; optional browser checks use Playwright and installed Microsoft Edge. A `.venv` was created with Python 3.14 on this machine. Recreate it on another machine; do not treat a copied Windows virtual environment as portable.

## 5. Run, configure and verify

From the workspace on this machine:

```powershell
.\.venv\Scripts\python.exe run.py
```

Open `http://127.0.0.1:8000`. Alternatively, double-click `TRACE.pyw`. The launcher uses the workspace virtual environment, reuses a responding local server, and opens a browser without a console. The launcher currently assumes port 8000.

Fresh Windows setup (dependency installation needs internet):

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Do not assume a server left running by the previous session is still alive. Check `/api/bootstrap`; avoid starting duplicate processes on the same port. The visible-browser tool was unavailable during the build, but headless Edge testing worked.

| Environment variable | Purpose / default |
| --- | --- |
| `TRACE_DEVICE` | `simulator` by default; `serial` selects the hardware transport |
| `TRACE_SERIAL_PORT` | Serial port; defaults to `/dev/ttyACM0`, use a confirmed `COM` port on Windows |
| `TRACE_HOST` | Bind address; `127.0.0.1` by default |
| `TRACE_PORT` | HTTP port; `8000` by default |
| `TRACE_PUBLIC_URL` | QR/display URL; application default `http://trace.local` |
| `TRACE_WIFI_NAME` | Displayed SSID; `TRACE-07` by default |
| `TRACE_RESEARCH_PIN` | Enables researcher diagnostics; disabled when unset |

The research PIN is a local lab gate, not hardened public-server authentication. Do not publish the board server to the public Internet as part of normal deployment.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
node --check frontend/app.js
```

With a local server running and Microsoft Edge installed:

```powershell
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe tools/browser_check.py
```

Browser tests change shared simulator state. Restore normal conditions afterward if leaving a demo for the user.

### Recorded validation, not a fresh test claim

The build session recorded **41 passing backend tests** and **15 screen/viewport checks** (five screens at 1280 x 800, 800 x 480, and 390 x 844), plus simulator fault controls, dock loading, timebase selection and 16-channel capture checks. No JavaScript exceptions or external browser requests were detected during those checks. Representative screenshots were visually inspected.

See `docs/VALIDATION.md`, `runtime/browser-results.json` and `runtime/screenshots/`. These were reviewed while preparing this handoff; tests were **not rerun just to write this document**. Rerun appropriate checks after code changes. Physical display, electrical behavior and Pi deployment remain unverified.

### State and persistence

- Settings persist in `runtime/settings.json`.
- Truth-table observations, current capture and calibration rows are in memory. Export before restart.
- All connected browsers share one board's state; controls are not isolated per student.
- `FLOATING` means an intermediate measured voltage, not proven high impedance.
- Missing/stale readings are UNKNOWN; a frame older than three seconds makes the live board view unlinked.
- Sequential comparison currently counts observed LOW-to-HIGH transitions in published frames. It cannot reliably count fast clocks from a slow UI stream.

## 6. How the software and hardware will connect

The key integration boundary is the **device protocol**, not the frontend. Keep the interface and comparison engine; replace generated measurements with messages from actual firmware.

```text
Physical experiment switches / outputs / mapped breadboard contacts
    |
    +-- Slow voltage path: mux + ADC + firmware
    |       -> frame {channel ID, millivolts}
    |
    +-- Fast digital path: selection matrix + protected digital inputs
            -> MCU capture engine / trigger / buffer
            -> cap_data chunks + cap_done

MCU(s) <-- USB CDC or UART, NDJSON --> Pi Python backend
                                       |
                                       +-- comparison and capture processing
                                       +-- WebSocket --> onboard browser / phone
                                       +-- commands --> MCU(s)

Virtual IC path:
Browser selection -> backend command -> MCU logic engine
    -> controlled direction/enable translators -> dock signal pins
    <- input pin states and passive power-sense readings
```

**MCU responsibilities:** time-critical acquisition, sampling, trigger/pretrigger buffering, logical IC execution, pin direction, power supervision, and safe output release.

**Pi responsibilities:** configuration, serial communications, comparison/presentation, serving the UI, exports, and researcher measurements. Do not implement MHz acquisition or timing-critical dock behavior in Python or browser callbacks.

**Frontend responsibilities:** display actual status/limits and send requests. A button click is not proof that the hardware completed an action.

### Physical channel mapping

`data/channels.json` currently has logical IDs and example channels, with `mux` and `capture_input` set to null. Preserve IDs where practical, but replace example routing with a reviewed schematic-derived map. Record ADC inputs, mux banks/select lines, physical test points, capture inputs, and board revision.

The current JSON routing fields do **not** automatically program a mux or upload a map to firmware. Implement a deliberate mapping workflow: generate firmware configuration from the reviewed map, or define a validated mapping-upload command. Add a map/version identity to the handshake and reject incompatible combinations.

### Device selection

Once working firmware and mapping exist, set:

```powershell
$env:TRACE_DEVICE = 'serial'
$env:TRACE_SERIAL_PORT = 'COM5' # example only: identify the actual board port
.\.venv\Scripts\python.exe run.py
```

On Pi, configure the actual serial device in `/etc/trace.env`. Serial mode must visibly show no link when hardware is absent; do not silently substitute simulator data.

The current runtime supports **one serial device**. If the final design uses separate capture and dock MCUs, add a device manager/routing layer or an agreed hardware bridge. A second MCU is not supported merely by connecting another USB cable.

## 7. Firmware contract and integration gaps

Read `protocol/README.md` before writing firmware. Important current rules:

- Version 1, UTF-8 newline-delimited JSON, bounded lines. Serial default is 115200 baud.
- Device `hello` reports protocol, channel/rate/depth capabilities and supported ICs.
- Backend sends `cfg`, `watch`, `cap_cfg`, `cap_arm`, `cap_stop`, `vic_load`, `vic_release`.
- Device publishes `frame`, `cap_data`, `cap_done`, `cap_stopped`, `vic_status`, `ack`, `err`.
- Slow frames are complete snapshots of requested channels, not partial updates.
- Capture event deltas are **samples**; `dt` is **nanoseconds per sample**. Bit order follows the configured channel list.
- Capture IDs distinguish acquisitions; chunk sequence numbers must be contiguous. Only the first event of the entire capture has delta zero.
- The backend currently requires reported `dt` to match the requested rate within its validation tolerance. If hardware supports discrete/rounded rates, add negotiated actual-rate handling rather than misreporting timing.
- Overflow/dropped samples are visible and must never be hidden.
- `sim_set`, `vic_pin` and `vic_power` are simulator controls, not physical output commands.

Hardware limits must be established with the real ADC, mux, buffers, MCU and transport. The simulator's 16 channels, 10 MS/s, 200000 samples, nominal 1 kHz scan and 1 kHz IC target are **not measured performance**. The simulator generates frames around 10 Hz; it does not physically scan at 1 kHz.

The following are **future hardening tasks**, not implemented guarantees:

1. Correlate command acknowledgements with pending requests; implement deadlines, error recovery, configuration acceptance and busy-state handling. Current code assigns IDs and stores the last ack, but has no full command transaction manager.
2. Add an explicit host heartbeat/watchdog protocol and firmware output-release behavior. The current documentation calls for this; no heartbeat sender or physical watchdog implementation exists here.
3. Associate stop/status messages with acquisition IDs so a delayed stop response cannot invalidate a newly armed capture.
4. Decide how frame freshness behaves during long captures/transfers. Avoid falsely marking a healthy board disconnected merely because acquisition pauses voltage publications.
5. Add serial/hardware-in-the-loop tests for truncated lines, split reads, disconnect/reconnect, reset, chunk loss, delayed acknowledgements and unplugged dock behavior. Current integration tests use the simulator, not a physical serial link.
6. Drive UI limits, IC speed labels and selectable rates from real negotiated capabilities. Some current presentation/configuration values remain simulator-oriented; audit them before hardware demonstrations.
7. Add capture rendering decimation or visible-range processing if worst-case dense captures are slow. Tested 16-channel generated captures do not prove smooth rendering for every 200000-event buffer.

## 8. Practical integration roadmap

### Stage A: freeze the minimum hardware and experiment contract

Obtain Pi model, screen module/interface, MCU choice, ADC/mux parts, capture matrix, buffer/translator design, dock power sensing and actual schematic/pin map. Obtain the lab manual and selected experiment truth tables/sequential behavior.

Agree whether one or two MCUs are used and resolve the physical Virtual IC scope. Review exact IC variants and pinouts; for example, the included 7483 model uses the 83A-style DIP arrangement, not the 74283 arrangement. Consult manufacturer documentation for the actual purchased parts before wiring.

**Exit condition:** reviewed board revision, mapping, power/interface design, and an agreed first experiment. Do not guess routing from UI illustrations.

### Stage B: first real measurement, one channel at a time

Implement minimal MCU firmware: protocol handshake, accepted configuration, one protected ADC input and one `frame` channel. Confirm readings against a reference meter. Switch the backend to serial mode and watch the same reading appear in the browser.

Then add mux scanning, settling time, ADC calibration/scale conversion and remaining mapped channels. Separate hardware scan frequency from publication frequency so serial bandwidth is respected.

**Exit condition:** a real known voltage on a named contact appears correctly, missing data becomes UNKNOWN, and reconnect does not leave stale values displayed.

### Stage C: integrate one complete physical experiment

Map actual switches and outputs to a JSON experiment. Exercise every truth-table row with the real circuit; verify live row selection, outputs, voltages and reset. Test intermediate voltages and disconnected/omitted readings without claiming automatic fault diagnosis.

Expand to the official experiment library only after the first end-to-end path works. For sequential activities, define reset/synchronization and expected state progression; move fast-edge comparisons into captured data rather than slow snapshots.

**Exit condition:** a real experiment's expected-versus-measured results agree with independent observations for every supported test condition.

### Stage D: add digital capture conservatively

Start with a small number of protected channels and a modest verified sample rate. Implement MCU-local trigger detection, ring/pretrigger buffering, acquisition completion, change-event encoding and bounded chunk transfer. Extend channel count/rate/depth only as measured resources permit.

USB CDC/UART NDJSON is a control/transfer interface, not an assumed raw MHz streaming path. Transfer captures after acquisition; consider binary transfer later if measurements justify it. Report actual timing, overflow and transport loss honestly.

Compare with a reference analyzer/oscilloscope, then validate expected-waveform alignment, trigger placement, cursor timing and VCD exports.

**Exit condition:** independently verified captures and published measured capability limits, including failure behavior.

### Stage E: physical Virtual IC integration

Only proceed after the electrical interface and thesis scope are approved. Begin with one simple combinational IC, such as the 7400. Use the reviewed input/output directions, controlled translators, passive VCC/GND sense and output-enable supervision.

Implement safe startup/release and firmware-local power/watchdog checks before allowing outputs. Verify logic behavior against a real chip, then measure propagation and reliable rates under the intended load. Add remaining combinational ICs, then 7474 and selected counters if in scope.

**Exit condition:** verified truth tables, measured timing/load limits and proven release on power faults, reset and lost communication. Software simulation tests cannot establish these properties.

### Stage F: deploy on the Pi and physical touchscreen

Use `deploy/install-pi.sh` as a starting point; verify OS packages, service permissions, serial access, display rotation and touch input on the actual Pi. Configure kiosk desktop auto-login separately.

Run hotspot configuration locally because it changes the active Wi-Fi connection. The supplied initial Pi service uses `http://trace.local:8000`; the handoff's portless `http://trace.local` requires the supplied nginx configuration to be installed and the public URL updated. Check QR, hostname, SSID and actual reachable address together.

Test with internet unavailable, a phone and the touchscreen connected simultaneously, MCU unplug/replug, reboot and power cycling. Network/display scripts are not proven by Windows tests.

**Exit condition:** the board boots into a usable offline app and phones can reach the same board state without accounts or installs.

### Stage G: thesis technical validation

Use `docs/HARDWARE_VALIDATION.md` to organize reference-voltage, timing, IC and operational tests. Agree tolerances and procedures with the researchers before evaluating results. Add timing-comparison and real-chip test tooling as needed; current diagnostics only calculate voltage-reference comparisons.

Record board/firmware/software revisions, instrument identity/calibration, conditions and limitations alongside exports. Separate simulator records from physical records. Publish pass rates using valid tests and do not invent measurement results or learning-outcome claims.

**Exit condition:** reproducible physical evidence supports each reported capability and limitation.

## 9. Recommended next-agent behavior

1. Read this file, then `README.md`, `protocol/README.md`, `docs/VALIDATION.md` and the current source. Confirm what changed since this snapshot.
2. Preserve the working simulator as a regression/development option and the existing UI reference direction.
3. Ask for the missing hardware/material decisions only when they block the requested integration step. There is no selected, wired MCU hidden elsewhere in this handoff.
4. Prefer the smallest real end-to-end milestone: **one physical input -> MCU frame -> serial adapter -> backend -> browser**. Prove it before adding all channels and the dock.
5. Keep measured hardware capabilities separate from aspirational targets and synthetic limits.
6. Run relevant tests after changes and document what was actually verified. Do not call physical integration complete because simulator or browser checks passed.

Suggested opening prompt for a new agent:

> Read TRACE_AGENT_HANDOFF.md in this workspace and inspect the existing code before changing it. This is currently a simulator-backed TRACE thesis application, not a verified hardware system. Preserve the current functionality and scope constraints. Help me continue from this baseline toward the specific software or hardware milestone I describe next, and distinguish implemented behavior, proposed work, and physical validation throughout.
