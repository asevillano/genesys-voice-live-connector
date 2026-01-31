# Genesys Cloud Audio Connector - Client Simulator

This directory contains a client simulator that emulates **Genesys Cloud Audio Connector** behavior for local Voice Agent testing.

## 🎯 Purpose

The simulator allows you to test the Voice Agent server without needing to:
- Have access to Genesys Cloud
- Configure the real Audio Connector
- Use NGrok or deploy to the cloud

Ideal for:
- **Local development** - Test prompt and tool changes without deploying
- **Integration testing** - Verify connection with Azure Voice Live API
- **Demonstrations** - Show the agent working without Genesys infrastructure

## 📋 Requirements

- Python 3.9+ (compatible with Python 3.14)
- Working microphone and speakers
- The `gc-audioconnector-voiceagent` server running (locally or on Azure Container Apps)

## 🚀 Installation

```powershell
# 1. Navigate to directory
cd genesys_simulator

# 2. Create virtual environment (recommended)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt
```

### Dependencies

| Package | Version | Description |
|---------|---------|-------------|
| `websocket-client` | 1.7.0 | WebSocket client for Python |
| `sounddevice` | 0.4.6 | Audio capture and playback (Python 3.14 compatible) |
| `numpy` | >=1.26.0 | Audio array processing |
| `python-dotenv` | 1.0.1 | Environment variable loading |

## ▶️ Usage

### 1. Start the AudioConnector server

```powershell
# In another terminal, from the project root directory
npm run start
```

### 2. Run the simulator

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Use default URL (ws://localhost:8081)
python genesys_client_simulator.py

# Or specify a different URL (local Docker)
python genesys_client_simulator.py ws://localhost:8081

# Connect to Azure Container Apps
python genesys_client_simulator.py wss://voice-agent.<region>.azurecontainerapps.io
```

### 3. Interact with the agent

- 🎤 The simulator will capture audio from your microphone
- 📤 Send the audio to the Voice Agent server
- 📥 Receive AI agent responses
- 🔊 Play audio through speakers
- ⏹️ Press `Ctrl+C` to stop

## ⚙️ Configuration

Configure the simulator via environment variables or a `.env` file:

```env
# AudioConnector server URL
# Local (npm run start or Docker)
SIMULATOR_SERVER_URL=ws://localhost:8081

# Azure Container Apps (use wss:// for HTTPS)
# SIMULATOR_SERVER_URL=wss://voice-agent.<region>.azurecontainerapps.io

# Prompt name to use (available: Invoices, NewBooking)
PROMPT_NAME=Invoices

# Session IDs (optional, auto-generated)
SIMULATOR_ORG_ID=your-organization-id
SIMULATOR_CONV_ID=your-conversation-id
```

## 🔧 Parameters sent to server

The simulator sends the following input variables (`inputVariables`):

| Variable | Value | Description |
|----------|-------|-------------|
| `phoneNumber` | +34666123456 | User phone number |
| `emailAddress` | test@example.com | User email |
| `storedCardPresent` | false | Whether card is stored |
| `CURRENT_DATE` | Current date | Current date for the prompt |
| `promptName` | From `PROMPT_NAME` env var | Prompt name to use |

> **Note:** To test the Invoices prompt with Cosmos DB, ensure the server has `COSMOS_*` variables configured.

## 📊 AudioHook v2 Protocol

The simulator implements the Genesys AudioHook v2 protocol:

### Client → Server Messages
| Message | Description |
|---------|-------------|
| `open` | Establishes session with audio parameters |
| `ping` | Keep-alive (every 15 seconds) |
| `close` | Closes the session |
| `playback_started` | Indicates audio playback started |
| `playback_completed` | Indicates playback finished |

### Server → Client Messages
| Message | Description |
|---------|-------------|
| `opened` | Confirms session established |
| `disconnect` | Server closes connection |
| `pong` | Response to ping |
| `event` | Events (transcripts, barge-in, etc.) |

### Audio Format
| Parameter | Value |
|-----------|-------|
| **Format** | PCMU (µ-law) |
| **Sample Rate** | 8000 Hz |
| **Channels** | Mono |
| **Transmission** | Binary via WebSocket |

## 🔄 Communication Flow

```
┌──────────────┐                    ┌──────────────────┐                    ┌─────────────────┐
│  Simulator   │                    │    Voice Agent   │                    │  Azure Voice    │
│  (Python)    │                    │     Server       │                    │   Live API      │
└──────┬───────┘                    └────────┬─────────┘                    └────────┬────────┘
       │                                     │                                       │
       │──── WebSocket Connect ─────────────▶│                                       │
       │──── open (AudioHook v2) ───────────▶│                                       │
       │◀─── opened ─────────────────────────│                                       │
       │                                     │──── WebSocket Connect ───────────────▶│
       │                                     │◀─── session.created ──────────────────│
       │                                     │                                       │
       │════ Audio (µ-law 8kHz) ════════════▶│════ Audio (PCM16 24kHz) ═════════════▶│
       │                                     │     (Upsampled 3x)                    │
       │                                     │◀═══ response.audio.delta ═════════════│
       │                                     │     (Azure Speech Voice)              │
       │◀═══ Audio (µ-law binary) ═══════════│                                       │
       │                                     │                                       │
       │──── playback_started ──────────────▶│                                       │
       │──── playback_completed ────────────▶│                                       │
       │                                     │                                       │
       │──── close ─────────────────────────▶│                                       │
       │◀─── disconnect ─────────────────────│                                       │
       │                                     │                                       │
```

## 🐛 Troubleshooting

### "No audio output"
1. Verify the server is running (`npm run start` or Docker)
2. Check that `BOT_PROVIDER=voicelive` in server's `.env`
3. Review server logs for Azure Voice Live errors
4. Verify these variables are configured:
   - `AZURE_VOICE_LIVE_ENDPOINT`
   - `AZURE_VOICE_LIVE_API_KEY`
   - `AZURE_VOICE_LIVE_VOICE` (e.g., `es-ES-Ximena:DragonHDLatestNeural`)

### "sounddevice error"
```powershell
# Reinstall sounddevice
pip uninstall sounddevice
pip install sounddevice
```

### "Connection refused"
- Verify the server is running on the correct port
- Check the URL: `ws://localhost:8081`
- Ensure no firewall is blocking the port

### "Session not opened"
- Check server logs for authentication errors
- The simulator uses `ApiKey1` which must match `SecretService`

### "Cosmos DB error"
- Verify `COSMOS_*` variables are configured on the server
- Check logs: `docker logs -f voice-agent`
- The Invoices prompt requires Cosmos DB data with `TitularDNI` field

### "Failed to open microphone"
- Verify your microphone is connected and working
- On Windows, check microphone permissions in Settings > Privacy
- Test with: `python -c "import sounddevice; print(sounddevice.query_devices())"`

## 📁 Structure

```
genesys_simulator/
├── genesys_client_simulator.py  # Main simulator script
├── requirements.txt             # Python dependencies
├── .env                         # Environment configuration
├── .venv/                       # Virtual environment (created by you)
└── README.md                    # This file
```

## 🛠️ Development

### Modify input variables

The simulator reads `PROMPT_NAME` from the environment. To change the prompt:

```env
# In .env file
PROMPT_NAME=NewBooking
```

Or edit the `on_open` function in `genesys_client_simulator.py`:

```python
input_vars = {
    "phoneNumber": "+34666123456",
    "emailAddress": "test@example.com",
    "storedCardPresent": "false",
    "CURRENT_DATE": datetime.now().strftime("%Y-%m-%d"),
    "promptName": os.getenv("PROMPT_NAME", "Invoices")  # Options: "Invoices", "NewBooking"
}
```

### Change audio format

The simulator uses µ-law (PCMU) at 8kHz as required by AudioConnector. To modify this, edit the constants at the beginning of the file:

```python
SAMPLE_RATE = 8000  # Hz
CHANNELS = 1  # Mono
CHUNK_SIZE = 1600  # 200ms of audio
```
