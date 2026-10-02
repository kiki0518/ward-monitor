# Ward Monitor

A smart ward monitoring prototype built for the Mei-Chu Hackathon, combining live ward dashboards, edge pose detection, camera streaming, and AI-assisted nursing handovers.

## Features

- **Ward dashboard** — View bed status, vital signs, and prioritized alerts.
- **Live monitoring** — Stream MJPEG video and detect posture and possible falls with MoveNet on an edge board.
- **Care records** — Document alert responses and follow-up tasks.
- **AI handovers** — Generate TAIDE summaries for nurses to review, edit, and submit.

**Stack:** React · Vite · FastAPI · WebSocket · GStreamer · MoveNet · TAIDE

## Quick Start

Requires Python 3.10+ and Node.js 22.12+ with npm. Run these commands from the repository root on macOS / Linux.

**Backend**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
python -m uvicorn app.main:app --app-dir backend \
  --host 0.0.0.0 --port 8000 --workers 1 \
  --ws-max-size 2097152 --ws-max-queue 1 --ws-per-message-deflate false
```

**Frontend** — in another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal (usually `http://localhost:5173`). API docs are available at `http://localhost:8000/docs`.

The dashboard runs with simulated data without a camera or AI model. The frontend connects to port `8000` on the same hostname. Keep the backend on **one worker**, as live state is stored in memory.

## Documentation

Detailed setup and API guides are currently in Traditional Chinese:

- [Camera streaming and MoveNet setup](streaming/README.md)
- [TAIDE setup and AI handovers](docs/HANDOVER.md)
- [Frontend/backend API contract](API_CONTRACT.md)
- [Board reporting API](BOARD_API_SPEC.md)

## Prototype Scope

This is a demo, not a clinically validated system. Vital signs are simulated; bed `101` supports board posture input, and video uses a single shared camera channel. Care and handover records persist locally, while live state resets on restart.

Authentication and access control are not implemented. Use fictional data on a local or trusted network.
