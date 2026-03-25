# Genesys Voice Live Connector

This repository provides **Voice AI Agent** implementations that integrate with **Genesys Cloud Audio Connector** using the **Azure Voice Live API** (Real-time Speech-to-Speech) with **Azure Speech voices**.

The project includes both **TypeScript** and **Python** implementations with identical functionality.

---

## 🏗️ Architecture Overview

```
                    ┌─────────────────┐
                    │  Genesys Cloud  │
                    │ AudioConnector  │
                    └────────┬────────┘
                             │ WebSocket (µ-law 8kHz)
                             ▼
                    ┌─────────────────┐
                    │  Voice Agent    │
                    │ (TS or Python)  │
                    └────────┬────────┘
                             │ WebSocket (PCM16 24kHz)
                             ▼
                    ┌─────────────────┐
                    │ Azure Voice Live│
                    │       API       │
                    └─────────────────┘
```

### Key Components

| Component | Description |
|-----------|-------------|
| **Genesys Cloud AudioConnector** | Streams audio via WebSocket using AudioHook v2 protocol (µ-law 8kHz) |
| **Voice Agent (TypeScript/Python)** | Server that bridges AudioConnector with AI backends |
| **Azure Voice Live API** | Real-time Speech-to-Speech API with GPT-Realtime and Azure Speech voices |
| **Azure Cosmos DB** | NoSQL database for customer data (invoices, billing info) |
| **Genesys Cloud Simulator** | Python-based local simulator for testing without Genesys Cloud |

### Audio Processing

The server handles audio format conversion between Genesys and Azure:

| Direction | Source Format | Target Format | Conversion |
|-----------|---------------|---------------|------------|
| **Genesys → Azure** | µ-law 8kHz mono | PCM16 24kHz mono | Decode + Upsample (3x) |
| **Azure → Genesys** | PCM16 24kHz mono | µ-law 8kHz mono | Downsample (3x) + Encode |

---

## 📁 Project Structure

```
genesys-voice-live-connector/
├── src/
│   ├── typescript/              # TypeScript implementation
│   │   ├── auth/                # Authentication and signature verification
│   │   ├── common/              # Shared utilities and environment variables
│   │   ├── prompts/             # Prompt templates and tool definitions
│   │   ├── protocol/            # AudioHook v2 protocol definitions
│   │   ├── services/            # Business logic and AI integrations
│   │   ├── websocket/           # WebSocket server and session management
│   │   └── index.ts             # TypeScript entry point
│   │
│   └── python/                  # Python implementation
│       ├── common/              # Shared utilities and environment variables
│       ├── prompts/             # Prompt templates and tool definitions
│       ├── protocol/            # Protocol type definitions
│       ├── services/            # Business logic and AI integrations
│       └── websocket/           # WebSocket server and session management
│
├── genesys_simulator/           # Local testing simulator
│   ├── genesys_client_simulator.py
│   ├── requirements.txt
│   └── README.md
│
├── main.py                      # Python entry point
├── package.json                 # Node.js dependencies (TypeScript)
├── tsconfig.json                # TypeScript configuration
├── requirements.txt             # Python dependencies
│
├── Dockerfile.typescript        # Docker image for TypeScript version
├── Dockerfile.python            # Docker image for Python version
│
├── deploy-typescript.ps1        # Deployment script for TypeScript
├── deploy-python.ps1            # Deployment script for Python
│
├── start-typescript.bat/.sh     # Start scripts for TypeScript
├── start-python.bat/.sh         # Start scripts for Python
│
├── .env.sample                  # Environment variables template
├── .gitignore                   # Git ignore rules
└── README.md                    # This file
```

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

### TypeScript Version

#### Option 1: Local Development (Without Docker)

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
# Or use: start-typescript.bat (Windows) / start-typescript.sh (Linux/Mac)

# Server will be available at ws://localhost:8081
```

#### Option 2: Docker Deployment

```bash
# Build and deploy (local or Azure)
.\deploy-typescript.ps1
```

---

### Python Version

#### Option 1: Local Development (Without Docker)

**Prerequisites:**
- Python 3.11+
- pip

**Steps:**

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.sample .env
# Edit .env with your API keys

# 4. Start the server
python main.py
# Or use: start-python.bat (Windows) / start-python.sh (Linux/Mac)

# Server will be available at ws://localhost:8081
```

#### Option 2: Docker Deployment

```bash
# Build and deploy (local or Azure)
.\deploy-python.ps1
```

---

## 🧪 Testing with Genesys Simulator

The `genesys_simulator/` folder contains a Python-based simulator for testing without a real Genesys Cloud environment.

```bash
cd genesys_simulator
pip install -r requirements.txt
python genesys_client_simulator.py
```

See [genesys_simulator/README.md](genesys_simulator/README.md) for detailed instructions.

---

## 🐳 Docker Images

| Dockerfile | Description | Build Command |
|------------|-------------|---------------|
| `Dockerfile.typescript` | Multi-stage build for TypeScript | `docker build -f Dockerfile.typescript -t voice-agent-ts .` |
| `Dockerfile.python` | Python 3.11 slim image | `docker build -f Dockerfile.python -t voice-agent-py .` |

---

## 📦 Deployment Scripts

Both deployment scripts support:
1. **Local Docker Desktop** - For development and testing
2. **Azure Container Apps** - For production deployment

| Script | Description |
|--------|-------------|
| `deploy-typescript.ps1` | Deploy TypeScript version |
| `deploy-python.ps1` | Deploy Python version |

---

## 🔄 Choosing Between TypeScript and Python

| Aspect | TypeScript | Python |
|--------|------------|--------|
| **Performance** | Excellent for I/O-bound operations | Good, with async support |
| **Ecosystem** | Rich npm packages | Extensive AI/ML libraries |
| **Docker Image Size** | ~200MB (Node.js slim) | ~150MB (Python slim) |
| **Development** | Strong typing, better IDE support | Simpler syntax, faster prototyping |

Both implementations are feature-complete and production-ready. Choose based on your team's expertise and existing infrastructure.

---

## 📖 Additional Documentation

| Document | Description |
|----------|-------------|
| [genesys_simulator/README.md](genesys_simulator/README.md) | Local simulator usage and configuration |

---

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details.
