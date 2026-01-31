# Genesys Cloud Audio Connector - Client Simulator

Este directorio contiene un simulador de cliente que emula el comportamiento de **Genesys Cloud Audio Connector** para pruebas locales del Voice Agent.

## 🎯 Propósito

El simulador permite probar el servidor de Voice Agent sin necesidad de:
- Tener acceso a Genesys Cloud
- Configurar el Audio Connector real
- Usar NGrok o desplegar en la nube

Es ideal para:
- **Desarrollo local** - Prueba cambios en prompts y tools sin desplegar
- **Testing de integración** - Verifica la conexión con Azure Voice Live API
- **Demostración** - Muestra el agente funcionando sin infraestructura de Genesys

## 📋 Requisitos

- Python 3.9+ (compatible con Python 3.14)
- Micrófono y altavoces funcionales
- El servidor `gc-audioconnector-voiceagent` corriendo (local o en Azure Container Apps)

## 🚀 Instalación

```powershell
# 1. Navegar al directorio
cd genesys_simulator

# 2. Crear entorno virtual (recomendado)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Instalar dependencias
pip install -r requirements.txt
```

### Dependencias

| Paquete | Versión | Descripción |
|---------|---------|-------------|
| `websocket-client` | 1.7.0 | Cliente WebSocket para Python |
| `sounddevice` | 0.4.6 | Captura y reproducción de audio (compatible con Python 3.14) |
| `numpy` | >=1.26.0 | Procesamiento de arrays de audio |
| `python-dotenv` | 1.0.1 | Carga de variables de entorno |

## ▶️ Uso

### 1. Inicia el servidor AudioConnector

```powershell
# En otra terminal, desde el directorio raíz del proyecto
npm run start
```

### 2. Ejecuta el simulador

```powershell
# Activar el entorno virtual
.\.venv\Scripts\Activate.ps1

# Usar URL por defecto (ws://localhost:8081)
python genesys_client_simulator.py

# O especificar una URL diferente (local Docker)
python genesys_client_simulator.py ws://localhost:8081

# Conectar a Azure Container Apps
python genesys_client_simulator.py wss://voice-agent.<region>.azurecontainerapps.io
```

### 3. Interactúa con el agente

- 🎤 El simulador capturará audio de tu micrófono
- 📤 Enviará el audio al servidor de Voice Agent
- 📥 Recibirá las respuestas del agente IA
- 🔊 Reproducirá el audio por los altavoces
- ⏹️ Presiona `Ctrl+C` para terminar

## ⚙️ Configuración

Puedes configurar el simulador mediante variables de entorno o un archivo `.env`:

```env
# URL del servidor AudioConnector
# Local (npm run start o Docker)
SIMULATOR_SERVER_URL=ws://localhost:8081

# Azure Container Apps (usar wss:// para HTTPS)
# SIMULATOR_SERVER_URL=wss://voice-agent.<region>.azurecontainerapps.io

# IDs de sesión (opcionales, se generan automáticamente)
SIMULATOR_ORG_ID=your-organization-id
SIMULATOR_CONV_ID=your-conversation-id
```

## 🔧 Parámetros enviados al servidor

El simulador envía las siguientes variables de entrada (`inputVariables`):

| Variable | Valor | Descripción |
|----------|-------|-------------|
| `phoneNumber` | +34666123456 | Número de teléfono del usuario |
| `emailAddress` | test@example.com | Email del usuario |
| `storedCardPresent` | false | Si hay tarjeta guardada |
| `CURRENT_DATE` | Fecha actual | Fecha actual para el prompt |
| `promptName` | Invoices | Nombre del prompt a usar |

> **Nota:** Para probar el prompt de Invoices con Cosmos DB, asegúrate de que el servidor tiene las variables `COSMOS_*` configuradas.

## 📊 Protocolo AudioHook v2

El simulador implementa el protocolo AudioHook v2 de Genesys:

### Mensajes del Cliente → Servidor
| Mensaje | Descripción |
|---------|-------------|
| `open` | Establece la sesión con parámetros de audio |
| `ping` | Keep-alive (cada 15 segundos) |
| `close` | Cierra la sesión |
| `playback_started` | Indica que comenzó la reproducción de audio |
| `playback_completed` | Indica que terminó la reproducción |

### Mensajes del Servidor → Cliente
| Mensaje | Descripción |
|---------|-------------|
| `opened` | Confirma la sesión establecida |
| `disconnect` | El servidor cierra la conexión |
| `pong` | Respuesta al ping |
| `event` | Eventos (transcripts, barge-in, etc.) |

### Formato de Audio
| Parámetro | Valor |
|-----------|-------|
| **Formato** | PCMU (µ-law) |
| **Sample Rate** | 8000 Hz |
| **Canales** | Mono |
| **Transmisión** | Binaria vía WebSocket |

## 🔄 Flujo de Comunicación

```
┌──────────────┐                    ┌──────────────────┐                    ┌─────────────────┐
│  Simulador   │                    │    Servidor      │                    │  Azure Voice    │
│  (Python)    │                    │  AudioConnector  │                    │   Live API      │
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

## 🐛 Solución de Problemas

### "No se escucha nada"
1. Verifica que el servidor está corriendo (`npm run start` o Docker)
2. Verifica que `BOT_PROVIDER=voicelive` en el `.env` del servidor
3. Revisa los logs del servidor para errores de Azure Voice Live
4. Verifica que las variables están configuradas:
   - `AZURE_VOICE_LIVE_ENDPOINT`
   - `AZURE_VOICE_LIVE_API_KEY`
   - `AZURE_VOICE_LIVE_VOICE` (ej: `es-ES-Ximena:DragonHDLatestNeural`)

### "Error de sounddevice"
```powershell
# Reinstalar sounddevice
pip uninstall sounddevice
pip install sounddevice
```

### "Connection refused"
- Verifica que el servidor está corriendo en el puerto correcto
- Verifica la URL: `ws://localhost:8081`
- Comprueba que no hay firewall bloqueando el puerto

### "Session not opened"
- Revisa los logs del servidor para ver errores de autenticación
- El simulador usa `ApiKey1` que debe coincidir con `SecretService`

### "Error de Cosmos DB"
- Verifica que las variables `COSMOS_*` están configuradas en el servidor
- Revisa los logs: `docker logs -f voice-agent`
- El prompt Invoices requiere datos en Cosmos DB con campo `TitularDNI`

### "Failed to open microphone"
- Verifica que tu micrófono está conectado y funcionando
- En Windows, verifica los permisos de micrófono en Configuración > Privacidad
- Prueba con: `python -c "import sounddevice; print(sounddevice.query_devices())"`

## 📁 Estructura

```
genesys_simulator/
├── genesys_client_simulator.py  # Script principal del simulador
├── requirements.txt             # Dependencias Python
├── .venv/                       # Entorno virtual (creado por ti)
└── README.md                    # Este archivo
```

## 🛠️ Desarrollo

### Modificar las variables de entrada

Edita la función `on_open` en `genesys_client_simulator.py`:

```python
input_vars = {
    "phoneNumber": "+34666123456",
    "emailAddress": "test@example.com",
    "storedCardPresent": "false",
    "CURRENT_DATE": datetime.now().strftime("%Y-%m-%d"),
    "promptName": "Invoices"  # Opciones: "Invoices", "NewBooking"
}
```

### Cambiar el formato de audio

El simulador usa µ-law (PCMU) a 8kHz como requiere el AudioConnector. Si necesitas modificar esto, edita las constantes al inicio del archivo:

```python
SAMPLE_RATE = 8000  # Hz
CHANNELS = 1  # Mono
CHUNK_SIZE = 1600  # 200ms de audio
```
