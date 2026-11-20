# TRACE Workspace Guide

Updated 20 November 2026.

## Project overview

TRACE means **Teaching and Real-Time Analysis of Circuits and Experiments**. This
repository contains an offline desktop mockup for a proposed digital-logic
laboratory trainer.

The current application demonstrates the intended software workflow while the
physical trainer is still under development. It combines a local Python service,
an HTML/CSS/JavaScript interface, and a PyWebView desktop window. The application
does not require an internet connection after its dependencies have been
installed.

The mockup uses generated readings and simulated acknowledgements. It has not
been connected to, or validated with, the physical TRACE trainer. It must not be
presented as evidence of actual voltage accuracy, timing, output loading, USB
communication, firmware behavior, or hardware safety performance.

## Current source of requirements

The current four-view design follows these project documents:

- `Project Sketches.pdf`
- `TRACE-Concept-of-Operation.pdf`
- `TRACE-System-Architecture.pdf`
- The thesis manuscript and value proposition

The reference PDFs are project inputs and are not stored in this repository.
Their original computer locations are intentionally omitted from this guide.

The Concept of Operation is the main behavioral reference. It defines a desktop
application connected to the trainer through USB, physical operation of the
predefined experiment controls, bounded breadboard monitoring, logical Virtual IC
port assignments, acknowledged state changes, explicit output disable, and clear
separation between offline examples and live hardware data.

## Current application

The default interface contains four views.

### Experiments

- Displays a physical locator for experiment regions E1 through E15.
- Selecting an experiment shows its known physical input labels.
- Experiment 4 is identified as NOR and NAND gates with `A / SWA`, `B / SWB`,
  and `C / SWC`.
- Physical input labels are read-only references. Students operate the switches
  on the trainer itself.
- The interface does not claim remote switching or remote experiment power
  control.
- Activity metadata comes from `data/concept_experiments.json`. Entries without
  verified laboratory-manual data remain incomplete instead of being invented.

### Breadboard monitor

- Shows the central 63-column breadboard representation.
- Treats A-E and F-J contact groups as electrically connected node groups rather
  than independent measurements at every socket.
- Demonstrates supported groups N01, N02, N03, N04, and N07.
- Displays voltage, interpreted logic state, sample validity, freshness, and
  sequence information in the underlying mockup data.
- Uses `LOW`, `HIGH`, `UNDEFINED`, and `UNAVAILABLE` consistently with the
  Concept of Operation.
- Offline values are clearly marked as demonstrations while hardware remains
  disconnected.

### Virtual IC

- Presents logical signals assigned to breadboard node groups.
- Treats the port map as an interface assignment rather than a copy of a physical
  IC package pinout.
- Displays a proposed two-section 7476 mapping. Activation is blocked because the
  exact variant, clock edge, initialization, and asynchronous behavior have not
  been finalized.
- Provides a simulated 74LS00 rehearsal with configure, activate, input-state,
  deactivate, and output-disable behavior.
- Checks complete assignments, exclusive node ownership, accepted configuration
  identity, and operating state before simulated activation.
- Keeps the separate NAND and generic JK behavior examples offline and distinct
  from trainer operation.

### Connection

- Shows the planned physical trainer identity, protocol, supported-node, model,
  and operating-limit fields.
- Leaves unreported hardware capabilities visibly unreported.
- Provides an offline session rehearsal for the states `disconnected`,
  `connected and inactive`, `configured`, `active`, and `interlocked`.
- Models acknowledgements, a heartbeat timeout, protection interruption, explicit
  reconnect, and configuration clearing.
- Never represents a simulated session as a real USB connection.

## Interface design

The active interface is based on the approved TRACE Figma direction and uses a
clean desktop layout with a fixed header, workspace navigation, and four focused
views.

- Primary blue is `#2A66C0`.
- Soft sage is `#D8E9D3`.
- Blue-gray is `#CACDE2`.
- Terracotta is `#CE6B4B` and identifies disconnected hardware states.
- The TRACE wordmark uses the bundled Iceland font.
- Interface text uses the bundled IBM Plex Sans font.
- The header includes a sun/moon theme control.
- The selected light or dark theme is stored locally and restored on later
  launches.
- Both fonts and all interface assets are local, so the application remains
  usable offline.

## Technology stack

- Python and FastAPI provide the local application service.
- Native HTML, CSS, and JavaScript provide the interface.
- PyWebView with the Edge WebView2 runtime provides the desktop window.
- The current concept state machine is implemented in `backend/concept.py`.
- No Node.js build, npm installation, cloud account, analytics service, CDN, or
  external runtime API is required.

## Important files

```text
TRACE.pyw                       Double-click Windows launcher
desktop.py                      Desktop window and application-owned local server
run.py                          Browser-development server entry point
setup.ps1                       Windows environment and dependency setup
requirements.txt                Runtime Python dependencies
requirements-dev.txt            Test and development dependencies

backend/app.py                  FastAPI application and routes
backend/concept.py              Current mockup state and offline session simulator
frontend/concept.html           Current application shell
frontend/concept.css            Base responsive interface styles
frontend/desktop-theme.css      Figma-aligned desktop theme and dark mode
frontend/concept.js             Current four-view interface behavior
frontend/theme.js               Persistent light/dark theme control
frontend/Iceland-Regular.ttf    Offline TRACE wordmark font
frontend/IBM-Plex-Sans.ttf      Offline interface font

data/concept_experiments.json   E1-E15 reference metadata
tests/test_concept.py           Concept behavior and state-machine tests
tools/concept_browser_check.py  Current interface acceptance checks
protocol/README.md              Planned device/firmware communication boundary
docs/CONCEPT_UPDATE_2026-11-12.md
                                Detailed document-to-implementation alignment
```

The previous simulator interface remains available internally at `/legacy`. Its
waveform analyzer, older experiment fixtures, package-style Virtual IC view, and
Pi/hotspot assumptions belong to an earlier prototype. They are not current TRACE
hardware specifications and are not linked from the student-facing mockup.

## Installation and startup

Python 3.11 or newer is recommended.

On a new Windows computer, double-click `TRACE.pyw`. If `.venv` is missing, the
launcher offers to run the setup process. The first installation requires internet
access to download Python packages. Later launches are local and offline.

Setup can also be started manually from PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Start the desktop application manually with:

```powershell
.\.venv\Scripts\python.exe desktop.py
```

For browser-based development, run:

```powershell
.\.venv\Scripts\python.exe run.py
```

Then open `http://127.0.0.1:8000`. The browser route is intended for development.
The PyWebView window is the normal mockup entry point.

## Demonstration flow

1. Open **Experiments**, select E4, and identify its physical region and A, B,
   and C switch labels.
2. Explain that the inputs are operated on the physical trainer and the software
   locator is a reference.
3. Open **Breadboard monitor** and enable offline example values. Identify the
   supported node groups and the LOW, HIGH, UNDEFINED, and UNAVAILABLE states.
4. Open **Connection** and start an example session.
5. Open **Virtual IC**, choose the supported 74LS00 rehearsal, review the logical
   map, and request configuration.
6. Complete the visible wiring confirmation and activate the example.
7. Toggle simulated input signals and observe the calculated NAND output state.
8. Deactivate the example and disconnect the example session.

During a presentation, describe the application as an **interactive offline
software mockup backed by simulated trainer data**. The four screens demonstrate
the intended workflow and do not establish physical prototype performance.

## Verification

Run the Python test suite with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Run the JavaScript syntax checks with:

```powershell
node --check frontend/concept.js
node --check frontend/theme.js
```

With the development server running and Playwright installed, run the interface
checks with:

```powershell
.\.venv\Scripts\python.exe tools/concept_browser_check.py
```

The latest local test run completed with **73 passing Python tests**. These tests
verify software behavior and simulated state transitions. They do not validate
physical hardware.

## Scope boundaries

- Only mapped or selected breadboard groups may be described as monitored.
- The breadboard voltage display is not an analog oscilloscope.
- `UNDEFINED` means the voltage lies between the selected LOW and HIGH
  thresholds. It is not an automatic diagnosis of a wiring fault.
- Missing, invalid, or stale readings must appear unavailable rather than as zero
  volts or a current logic state.
- Simulator values and timing limits must not be reported as measured hardware
  capabilities.
- Virtual IC behavior is logic-level emulation. It does not establish physical
  propagation delay, drive current, loading, or unrestricted replacement of ICs.
- The application should not provide automatic troubleshooting diagnoses,
  corrective recommendations, or student troubleshooting logs.
- No student accounts or personal data are required by the current design.

## Physical hardware integration plan

The intended integration boundary is a USB connection between the desktop service
and the trainer MCU. The current offline session service must be replaced or
extended with a real device service that provides:

- Device, firmware, protocol, and board-revision identity
- Supported sensing nodes and Virtual IC models
- Electrical and timing limits established through physical validation
- Voltage samples with channel identity, validity, sequence, and freshness
- Versioned logical signal maps and resource ownership
- Correlated configure, activate, deactivate, status, and error acknowledgements
- Hardware output-enable and output-disable confirmation
- Heartbeat handling, autonomous firmware watchdog behavior, and explicit restart
- Actual input and output state reports for an active Virtual IC configuration

The MCU should perform time-sensitive acquisition, logical IC execution, pin
direction control, and safe output release. The Python service should manage USB
communication, configuration, state presentation, and application requests.

Recommended implementation sequence:

1. Finalize the MCU, sensing, buffering, power, protection, and USB design.
2. Establish a minimal versioned device handshake.
3. Send one verified physical voltage sample from a named node to the current UI.
4. Expand to the reviewed breadboard node map and validate readings against a
   reference instrument.
5. Integrate one complete physical experiment before populating all E1-E15 data.
6. Implement a simple combinational Virtual IC such as 74LS00 with safe output
   defaults and verified disable behavior.
7. Finalize the exact 7476 variant and validate both sections, clock behavior, and
   asynchronous controls before enabling it.
8. Publish only measured and reproducible hardware capabilities.

Physical integration is complete only after bench validation confirms the USB
session, measurement accuracy, logical behavior, timing, reset, watchdog,
disconnect, and output-release behavior on the actual trainer.
