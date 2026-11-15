# TRACE

TRACE is an offline desktop mockup for a proposed laboratory trainer for teaching
and real-time analysis of circuits and experiments. It presents the planned software
workflow for locating experiments, viewing breadboard node groups, assigning Virtual
IC signals, and managing a trainer connection.

The application uses a Python/FastAPI local service, an HTML/CSS/JavaScript
interface, and a PyWebView desktop window. It runs locally and does not require an
internet connection after dependencies have been installed.

## Current mockup behavior

The application starts with hardware disconnected. It provides offline example
values and a simulated 74LS00 session so the interface can be demonstrated without
a physical trainer.

The four views are:

- **Experiments** shows the trainer locator and physical input controls. E1-E15
  entries are driven by `data/concept_experiments.json`.
- **Breadboard monitor** shows the breadboard layout and monitored node groups.
  Offline values demonstrate `LOW`, `HIGH`, `UNDEFINED`, and `UNAVAILABLE` states.
- **Virtual IC** shows logical signal assignments to breadboard node groups. The
  74LS00 model supports a simulated configure, activate, input-change, and deactivate
  cycle. The proposed 7476 map is displayed for review and is not executable.
- **Connection** shows planned device identity and USB session states. Its example
  controls exercise the state machine without sending commands to hardware.

The mockup demonstrates software behavior and screen layout. Its simulated values
are not measurements from the physical prototype, and an example activation does
not enable electrical outputs.

## Setup on Windows

Python 3.11 or newer is recommended. From the project folder, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

For an existing environment, install dependencies with:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The first installation may require internet access to download packages. The
application itself runs locally after setup.

## Start the application

For the desktop window, double-click `TRACE.pyw` or run:

```powershell
.\.venv\Scripts\python.exe desktop.py
```

The launcher starts the local FastAPI service on an available loopback port and
opens the interface in a WebView2 desktop window. Close the window to stop it.
On a fresh clone, `TRACE.pyw` detects the missing `.venv`, asks whether to install
the environment, runs `setup.ps1`, and opens TRACE after installation completes.
The first launch requires internet access for package downloads and may take a few
minutes. Later launches use the existing environment.

For browser-based development, run:

```powershell
.\.venv\Scripts\python.exe run.py
```

Then open <http://127.0.0.1:8000>. Stop a foreground server with `Ctrl+C`.

## Demonstration flow

1. Open **Experiments** and select E4 to show the physical locator and the
   `A / SWA`, `B / SWB`, and `C / SWC` input labels.
2. Open **Breadboard monitor** and enable **Show offline example values**. Explain
   that these are demonstration values while hardware is disconnected.
3. Open **Connection** and click **Start example session**.
4. Open **Virtual IC**, select `74LS00`, and click **Configure example**.
5. Confirm the wiring step, then click **Activate example**.
6. Toggle the simulated inputs. The NAND output changes according to the inputs.
7. Click **Deactivate example**, confirm the power-off step, and disconnect the
   example session.

The intended presentation explains that the workflow is ready for USB integration,
while current values and acknowledgements come from the local simulation service.

## Project structure

- `backend/app.py` exposes the local FastAPI application.
- `backend/concept.py` implements the desktop concept state and simulated sessions.
- `frontend/concept.html`, `frontend/concept.css`, and `frontend/concept.js` contain
  the interface.
- `desktop.py` starts the local service and desktop window.
- `TRACE.pyw` is the double-click launcher.
- `data/concept_experiments.json` contains the E1-E15 reference index.
- `tools/concept_browser_check.py` runs interface acceptance checks.
- `protocol/README.md` documents the planned USB and firmware boundary.
- `docs/` contains concept, validation, data-schema, and hardware handoff notes.

## Verification

Run the Python tests with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Run the JavaScript syntax check with:

```powershell
node --check frontend/concept.js
```

With a local server running, run the browser checks with:

```powershell
.\.venv\Scripts\python.exe tools/concept_browser_check.py
```

The checks cover the four views, desktop and small viewport layouts, the experiment
index, map conflicts, simulated 74LS00 feedback, reversible confirmations, and the
absence of external browser requests.

## Future hardware integration

The planned production connection is a USB link between the desktop application and
the trainer MCU. The firmware must provide device identity, supported models, node
capabilities, configuration acknowledgements, input-state reports, output-disable
behavior, heartbeat handling, and error reporting.

Before hardware activation is enabled, the project needs an approved USB protocol,
finalized MCU and signal-conditioning design, reviewed node routing, the exact 7476
variant if retained, laboratory-manual data for E1-E15, and bench validation against
reference instruments.
