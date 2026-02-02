# Voice Agent - Genesys Cloud AudioConnector Integration

This repository provides a **Voice AI Agent** implementation that integrates with **Genesys Cloud Audio Connector** using the **Azure Voice Live API** (Real-time Speech-to-Speech) with **Azure Speech voices**.

> **Note:** This started as a fork of [AudioConnectorBluePrint](https://github.com/GenesysCloudBlueprints/audioconnector-server-reference-implementation) and has been significantly enhanced to support Azure Voice Live API with premium Azure Speech voices and Cosmos DB integration.

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                              ARCHITECTURE OVERVIEW                                 │
├────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                    │
│   ┌──────────────┐        ┌───────────────────────┐        ┌──────────────────┐    │
│   │   Genesys    │  WS    │   Voice Agent Server  │   WS   │  Azure Voice     │    │
│   │    Cloud     │◄──────►│   (Node.js/TS)        │◄──────►│  Live API        │    │
│   │              │ 8kHz   │                       │ 24kHz  │  (GPT-Realtime)  │    │
│   │ AudioHook v2 │ µ-law  │   Audio Conversion    │ PCM16  │                  │    │
│   └──────────────┘        │   ┌───────────────┐   │        │  Azure Speech    │    │
│          │                │   │ µ-law ↔ PCM16 │   │        │  Voices          │    │
│          │                │   │ 8kHz ↔ 24kHz  │   │        │  (es-ES-Ximena)  │    │
│          ▼                │   └───────────────┘   │        └──────────────────┘    │
│   ┌──────────────┐        │                       │                                │
│   │  Caller /    │        │   ┌───────────────┐   │        ┌──────────────────┐    │
│   │  Simulator   │        │   │ Tool Handlers │   │◄──────►│  Azure Cosmos DB │    │
│   └──────────────┘        │   │ - getInvoices │   │        │  (Invoices)      │    │
│                           │   │ - endCall     │   │        └──────────────────┘    │
│                           │   │ - transfer    │   │                                │
│                           │   └───────────────┘   │                                │
│                           └───────────────────────┘                                │
│                                                                                    │
└────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Description |
|-----------|-------------|
| **Genesys Cloud AudioConnector** | Streams audio via WebSocket using AudioHook v2 protocol (µ-law 8kHz) |
| **Voice Agent Server** | Node.js/TypeScript server that bridges AudioConnector with AI backends |
| **Azure Voice Live API** | Real-time Speech-to-Speech API with GPT-Realtime and Azure Speech voices |
| **Azure Cosmos DB** | NoSQL database for customer data (invoices, billing info) |
| **Genesys Cloud Simulator** | Python-based local simulator for testing without Genesys Cloud |

### Audio Processing

The server handles audio format conversion between Genesys and Azure:

| Direction | Source Format | Target Format | Conversion |
|-----------|---------------|---------------|------------|
| **Genesys → Azure** | µ-law 8kHz mono | PCM16 24kHz mono | Decode + Upsample (3x) |
| **Azure → Genesys** | PCM16 24kHz mono | µ-law 8kHz mono | Downsample (3x) + Encode |

> **What is 8kHz µ-law?**
> - **8kHz** = Sample rate of 8000 samples per second (standard telephony quality)
> - **µ-law** (mu-law) = Audio compression algorithm that reduces 16-bit samples to 8-bit using a logarithmic scale
> 
> This format is the standard in North American and Japanese telephony systems. Genesys Cloud AudioConnector uses this format because it's native to traditional telephony. In contrast, Azure Voice Live API uses **PCM16 24kHz** (uncompressed, higher quality audio), which is why the server must convert between both formats.

---

## 📁 Project Structure

```
gc-audioconnector-voiceagent/
├── src/
│   ├── auth/                    # Authentication and signature verification
│   ├── common/                  # Shared utilities and environment variables
│   ├── prompts/                 # Prompt templates and tool definitions
│   │   ├── InvoicesPrompt.md    # Customer service prompt for billing inquiries
│   │   ├── InvoicesTools.json   # Tool definitions (getInvoices, endCall, transfer)
│   │   ├── NewBookingPrompt.md  # Travel booking prompt example
│   │   └── NewBookingTools.json # Booking tool definitions
│   ├── protocol/                # AudioHook v2 protocol definitions
│   ├── services/                # Business logic and AI integrations
│   │   ├── voice-live.ts        # Azure Voice Live API integration ⭐
│   │   ├── open-ai.ts           # OpenAI Realtime API integration
│   │   ├── deepgram.ts          # Deepgram Voice Agent integration
│   │   ├── open-ai-tools.ts     # Tool implementations (Cosmos DB queries)
│   │   └── voice-aiagent-base.ts # Base class for AI agents
│   ├── websocket/               # WebSocket server and session management
│   │   ├── server.ts            # Express + WebSocket server
│   │   └── session.ts           # Audio session handling with rate limiting
│   └── index.ts                 # Application entry point
├── genesys_simulator/           # Local testing simulator
│   ├── genesys_client_simulator.py  # Python simulator script
│   ├── requirements.txt         # Python dependencies
│   └── README.md                # Simulator documentation
├── deploy-azure-container-apps.ps1  # Deployment script (Local Docker + Azure)
├── Dockerfile                   # Production Docker image (multi-stage build)
├── .env                         # Environment configuration
├── README_Config_Genesys_Cloud.md   # Genesys Cloud configuration guide ⭐
└── package.json                 # Node.js dependencies
```

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [README.md](./README.md) | This file - Project overview and deployment |
| [README_Config_Genesys_Cloud.md](./README_Config_Genesys_Cloud.md) | **Step-by-step guide to configure Genesys Cloud** |
| [genesys_simulator/README.md](./genesys_simulator/README.md) | Local simulator usage and configuration |

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file based on `.env.sample`:

```bash
# ============= Voice Live API (Recommended) =============
BOT_PROVIDER=voicelive
AZURE_VOICE_LIVE_ENDPOINT=https://<your-resource>.services.ai.azure.com/
AZURE_VOICE_LIVE_API_KEY=<your-api-key>
AZURE_VOICE_LIVE_VOICE=es-ES-Ximena:DragonHDLatestNeural
VOICE_LIVE_MODEL=gpt-realtime
AZURE_VOICE_LIVE_API_VERSION=2025-10-01

# ============= Azure Cosmos DB (Optional) =============
COSMOS_ENDPOINT=https://<your-cosmosdb>.documents.azure.com:443/
COSMOS_KEY=<your-cosmos-key>
COSMOS_DATABASE_NAME=<database-name>
COSMOS_CONTAINER_NAME=<container-name>

# ============= Alternative: OpenAI Realtime API =============
# BOT_PROVIDER=openai
# OPENAI_MODEL_ENDPOINT=wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview
# OPENAI_API_KEY=<your-openai-key>
# OPENAI_VOICE_ID=alloy

# ============= Application Settings =============
PORT=8081
NO_INPUT_TIMEOUT=15000
NO_INPUT_MESSAGE=User did not provide any input. Act accordingly.
INITIAL_GREETING=Greet the user warmly
```

### Voice Options

| Provider | Voice Format | Examples |
|----------|--------------|----------|
| **Voice Live (Azure Speech)** | `locale-VoiceName:Style` | `es-ES-Ximena:DragonHDLatestNeural`, `en-US-Ava:DragonHDLatestNeural` |
| **OpenAI Realtime** | Simple name | `alloy`, `echo`, `shimmer`, `ash`, `coral`, `sage`, `verse` |

---

## 🚀 Running the Solution

### Option 1: Local Development (Without Docker)

**Prerequisites:**
- Node.js 18+
- npm

**Steps:**

```bash
# 1. Install dependencies
npm install

# 2. Configure environment
cp .env.sample .env
# Edit .env with your API keys

# 3. Start the server
npm run start

# Server will be available at ws://localhost:8081
```

**Testing with the Simulator:**

```bash
# In a new terminal
cd genesys_simulator

# Create virtual environment (Windows)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Create virtual environment (Linux/Mac)
# python -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run simulator
python genesys_client_simulator.py
```

---

### Option 2: Local Docker Desktop

**Prerequisites:**
- Docker Desktop installed and running

**Using the Deployment Script:**

```powershell
# Run the deployment script
.\deploy-azure-container-apps.ps1

# Select option 1: Local Docker Desktop
```

**Or manually:**

```bash
# Build the image (--no-cache ensures all changes are applied)
docker build --no-cache -t voice-agent:latest .

# Run the container
docker run -d --name voice-agent -p 8081:8081 --env-file .env voice-agent:latest

# Check logs
docker logs -f voice-agent

# Health check
curl http://localhost:8081/health
```

**Testing:**
```bash
cd genesys_simulator
python genesys_client_simulator.py
# Uses ws://localhost:8081 by default
```

---

### Option 3: Azure Container Apps (Production)

**Prerequisites:**
- Azure CLI installed and logged in (`az login`)
- Docker Desktop running
- Azure subscription with permissions to create resources

**Deployment Script:**

```powershell
# Run the deployment script
.\deploy-azure-container-apps.ps1

# Select option 2: Azure Container Apps
# Follow the prompts (you can skip completed steps if re-deploying)
```

**What the script does:**

| Step | Description |
|------|-------------|
| 1 | Creates Resource Group (`rg-voice-agent`) |
| 2 | Creates Azure Container Registry (ACR) |
| 3 | Builds and pushes Docker image to ACR |
| 4 | Creates Container Apps Environment |
| 5 | Prepares environment variables and secrets |
| 6 | Creates/updates Container App with YAML config |
| 7 | Retrieves the application URL |

**After Deployment:**
- WebSocket URL: `wss://<app-name>.<region>.azurecontainerapps.io`
- Health Check: `https://<app-name>.<region>.azurecontainerapps.io/health`

---

## 🧪 Genesys Client Simulator

The `genesys_simulator/` folder contains a Python-based simulator that emulates Genesys Cloud Audio Connector for local testing.

### Features
- Full AudioHook v2 protocol implementation
- Real-time microphone capture
- µ-law encoding/decoding (same as Genesys Cloud)
- Speaker playback of agent responses
- Configurable input variables (promptName, phoneNumber, etc.)

### Usage

```bash
cd genesys_simulator

# Activate virtual environment
.\.venv\Scripts\Activate.ps1  # Windows
# source .venv/bin/activate   # Linux/Mac

# Run with default settings (ws://localhost:8081)
python genesys_client_simulator.py
```

### Simulator Configuration

Edit `genesys_simulator/.env` or set environment variables:

```bash
SIMULATOR_SERVER_URL=ws://localhost:8081   # Local
# SIMULATOR_SERVER_URL=wss://your-app.azurecontainerapps.io  # Azure
```

For more details, see [`genesys_simulator/README.md`](./genesys_simulator/README.md).

---

## 🗣️ Creating Custom Prompts

### 1. Create Prompt File

Create `src/prompts/YourPromptPrompt.md`:

```json
{
  "identity": {
    "name": "Your Agent Name",
    "languages": ["Spanish", "English"],
    "description": "Agent description"
  },
  "globalRules": [
    "Rule 1: Be helpful and concise",
    "Rule 2: Always confirm before taking actions"
  ],
  "states": [
    {
      "id": "1_intro",
      "description": "Welcome the user",
      "instructions": ["Greet warmly", "Ask how to help"],
      "transitions": [{ "next_step": "2_action", "condition": "User states intent" }]
    }
  ]
}
```

### 2. Create Tools File

Create `src/prompts/YourPromptTools.json`:

```json
[
  {
    "type": "function",
    "name": "yourFunction",
    "description": "What this function does",
    "parameters": {
      "type": "object",
      "properties": {
        "param1": { "type": "string", "description": "Parameter description" }
      },
      "required": ["param1"]
    }
  },
  {
    "type": "function",
    "name": "endCall",
    "description": "Terminate the call"
  },
  {
    "type": "function",
    "name": "transferToAgent",
    "description": "Transfer to human agent",
    "parameters": {
      "type": "object",
      "properties": {
        "reason": { "type": "string" }
      }
    }
  }
]
```

### 3. Implement Tool Handler

In `src/services/voice-live.ts` (or `open-ai.ts`), add your handler in `handleFunctionCall()`:

```typescript
} else if (funcCall.name === 'yourFunction') {
    const result = await yourFunctionImplementation(args);
    responseData.item.output = JSON.stringify(result);
}
```

### 4. Pass Prompt Name from Genesys

In your Architect Flow or simulator, pass `promptName` as an input variable:
```
promptName = "YourPrompt"
```

---

## 🔧 Useful Commands

### Development
```bash
npm run start      # Start with ts-node (development)
npm run build      # Compile TypeScript to JavaScript
npm run clean      # Remove dist/ folder
```

### Docker
```bash
docker logs -f voice-agent         # Follow logs
docker exec -it voice-agent sh     # Shell into container
docker restart voice-agent         # Restart container
docker rm -f voice-agent           # Remove container
```

### Azure Container Apps
```bash
az containerapp logs show -n voice-agent -g rg-voice-agent --follow
az containerapp show -n voice-agent -g rg-voice-agent
az containerapp update -n voice-agent -g rg-voice-agent --min-replicas 2
```

---

## 🧹 Core Classes

### [`Server`](./src/websocket/server.ts)

Hosts the Express and WebSocket servers to manage real-time audio connections with Genesys Cloud Audio Connector.

### [`Session`](./src/websocket/session.ts)

Handles communication with the AudioConnector Client (Genesys Cloud). Regulates audio streaming rate to prevent buffer overflows.

### [`VoiceAIAgentBaseClass`](./src/services/voice-aiagent-base.ts)

Base class for all Voice AI Agent platforms. New integrations should inherit from this class.

#### Implementations:

| Class | Description |
|-------|-------------|
| [`VoiceLiveAgent`](./src/services/voice-live.ts) | **Azure Voice Live API** - Premium Azure Speech voices (es-ES-Ximena, etc.) ⭐ |
| [`OpenAIRealTime`](./src/services/open-ai.ts) | OpenAI Realtime API integration |
| [`DeepgramAIVoiceAgent`](./src/services/deepgram.ts) | Deepgram Voice Agent integration |

---

## 📚 References

- [Genesys AudioConnector Documentation](https://developer.genesys.cloud/devapps/audiohook/)
- [Azure Voice Live API](https://learn.microsoft.com/azure/ai-services/speech-service/how-to-use-voice-live-api)
- [Azure Speech Voices](https://learn.microsoft.com/azure/ai-services/speech-service/language-support?tabs=tts)
- [Azure Cosmos DB](https://learn.microsoft.com/azure/cosmos-db/)
- [OpenAI Realtime API](https://platform.openai.com/docs/api-reference/realtime)

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.