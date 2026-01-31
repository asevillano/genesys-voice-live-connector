# Genesys Cloud Configuration Guide

This guide provides step-by-step instructions to configure **Genesys Cloud** to use the Voice Agent connector deployed on **Azure Container Apps**.

---

## 📋 Prerequisites

Before you begin, ensure you have:

- [ ] **Genesys Cloud Organization** with admin access
- [ ] **Audio Connector license** enabled in your organization
- [ ] **Voice Agent deployed** on Azure Container Apps (see main [README.md](./README.md))
- [ ] **WebSocket URL** of your deployed connector (e.g., `wss://voice-agent.<region>.azurecontainerapps.io`)

> **Note:** Audio Connector integration is billed under the **BYOT Rate E model**. For pricing details, refer to [BYOT Pricing](https://help.mypurecloud.com/articles/bring-your-own-technology-services-model-per-turn-minute-rates-current-model/).

---

## 🔧 Step 1: Enable Audio Connector Integration

### 1.1 Access Admin Console

1. Log in to your **Genesys Cloud** organization
2. Navigate to **Admin** → **Integrations**
3. Click **+ Integrations** button

### 1.2 Add Audio Connector

1. Search for **"Audio Connector"** in the integrations catalog
2. Click **Install**
3. Give it a name (e.g., `Voice Agent - Azure`)
4. Click **Add Integration**

![Audio Connector Integration](https://help.mypurecloud.com/wp-content/uploads/2023/03/audio-connector-integration.png)

### 1.3 Configure Integration Settings

In the **Configuration** tab:

| Setting | Value | Description |
|---------|-------|-------------|
| **Connection URI** | `wss://voice-agent.<region>.azurecontainerapps.io` | Your Azure Container Apps WebSocket URL |
| **Channel** | `external` | For customer-facing voice |

### 1.4 Configure Credentials

In the **Credentials** tab:

1. Click **Configure**
2. Add the following credential:

| Field | Value |
|-------|-------|
| **Credential Type** | `API Key` |
| **API Key Name** | `ApiKey1` |
| **API Key Value** | `ApiKey1Value` |

> **Important:** These credentials must match what's configured in `src/services/secret-service.ts`. The default implementation uses `ApiKey1` / `ApiKey1Value`.

### 1.5 Activate Integration

1. Toggle the integration to **Active**
2. Click **Save**

---

## 🎨 Step 2: Create Architect Flow

### 2.1 Access Architect

1. Navigate to **Admin** → **Architect**
2. Click **+ Add** → **Inbound Call Flow**
3. Name it (e.g., `Voice Agent Flow`)

### 2.2 Configure Initial State

In the **Initial State** section:

1. Add a **Call Audio Connector** action (drag from toolbox)

### 2.3 Configure Call Audio Connector Action

Click on the **Call Audio Connector** action to configure it:

#### Basic Settings

| Setting | Value |
|---------|-------|
| **Integration** | Select your Audio Connector integration (`Voice Agent - Azure`) |
| **Audio Provider Session ID** | Leave as default or set a variable |

#### Input Variables

Add input variables that will be passed to the Voice Agent. Click **+ Add Input Variable** for each:

| Variable Name | Type | Example Value | Description |
|---------------|------|---------------|-------------|
| `promptName` | String | `Invoices` | Name of the prompt to use (must match a file in `src/prompts/`) |
| `phoneNumber` | String | `{{Call.Ani}}` | Caller's phone number |
| `emailAddress` | String | `customer@example.com` | Customer email (optional) |
| `CURRENT_DATE` | String | `{{ToString(GetCurrentDateTimeUtc(), "yyyy-MM-dd")}}` | Current date for context |
| `customerDNI` | String | `12345678A` | Customer identifier (for Cosmos DB lookup) |

> **Tip:** Use Architect expressions like `{{Call.Ani}}` to dynamically pass call data.

#### Example Input Variables Configuration

```
┌─────────────────────────────────────────────────────────────────┐
│  Input Variables                                                │
├─────────────────┬──────────┬───────────────────────────────────┤
│  Variable Name  │  Type    │  Value                            │
├─────────────────┼──────────┼───────────────────────────────────┤
│  promptName     │  String  │  "Invoices"                       │
│  phoneNumber    │  String  │  {{Call.Ani}}                     │
│  customerDNI    │  String  │  {{Flow.CustomerDNI}}             │
│  CURRENT_DATE   │  String  │  {{DateTimeFormat(...)}}          │
└─────────────────┴──────────┴───────────────────────────────────┘
```

### 2.4 Configure Output Handling

After the **Call Audio Connector** action, add actions to handle the outputs:

#### Available Output Variables

| Output Variable | Type | Description |
|-----------------|------|-------------|
| `audioProvider.exitReason` | String | Why the Audio Connector ended (`completed`, `error`, `transfer`) |
| `audioProvider.errorType` | String | Error type if failed |
| `audioProvider.errorMessage` | String | Detailed error message |

#### Handle Transfer Request

If the AI agent calls `transferToAgent`, add logic to transfer:

```
Decision: Is exitReason == "transfer"?
  ├─ Yes → Transfer to Queue (ACD)
  └─ No → Continue to Disconnect
```

### 2.5 Complete Flow Example

```
┌──────────────────────────────────────────────────────────────┐
│                    INBOUND CALL FLOW                         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐                                             │
│  │   Start     │                                             │
│  └──────┬──────┘                                             │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────┐                │
│  │     Call Audio Connector                │                │
│  │     ─────────────────────────           │                │
│  │     Integration: Voice Agent - Azure    │                │
│  │     Input Variables:                    │                │
│  │       - promptName = "Invoices"         │                │
│  │       - phoneNumber = {{Call.Ani}}      │                │
│  │       - customerDNI = {{Flow.DNI}}      │                │
│  └──────────────┬──────────────────────────┘                │
│                 │                                            │
│                 ▼                                            │
│  ┌─────────────────────────────────────────┐                │
│  │     Decision: exitReason                │                │
│  │     ─────────────────────────           │                │
│  │     "transfer" → Transfer to Queue      │                │
│  │     "completed" → Disconnect            │                │
│  │     "error" → Play Error + Disconnect   │                │
│  └─────────────────────────────────────────┘                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 2.6 Save and Publish

1. Click **Validate** to check for errors
2. Click **Save**
3. Click **Publish**

---

## 📞 Step 3: Assign Flow to Phone Number

### 3.1 Configure Call Routing

1. Navigate to **Admin** → **Call Routing**
2. Find or create a route for your phone number
3. Set the **Flow** to your published Architect flow

### 3.2 Alternative: Direct Number Assignment

1. Navigate to **Admin** → **Telephony** → **Phone Number Management**
2. Select your DID number
3. Assign the Architect flow directly

---

## ✅ Step 4: Test the Integration

### 4.1 Using Genesys Cloud

1. Call the assigned phone number
2. You should hear the AI agent greeting
3. Speak to test the voice interaction

### 4.2 Using the Local Simulator

For testing without making real calls:

```powershell
cd genesys_simulator
python genesys_client_simulator.py wss://voice-agent.<region>.azurecontainerapps.io
```

### 4.3 Monitor Logs

View real-time logs in Azure:

```bash
az containerapp logs show -n voice-agent -g rg-voice-agent --follow
```

Or in Azure Portal:
1. Go to your Container App
2. **Monitoring** → **Log stream**

---

## 🔍 Troubleshooting

### "Connection refused" or "WebSocket failed"

1. Verify the Container App is running:
   ```bash
   az containerapp show -n voice-agent -g rg-voice-agent --query "properties.runningStatus"
   ```
2. Check the WebSocket URL is correct (use `wss://` not `ws://`)
3. Verify health endpoint: `https://voice-agent.<region>.azurecontainerapps.io/health`

### "Authentication failed"

1. Check credentials in Genesys Cloud match `SecretService`:
   - API Key Name: `ApiKey1`
   - API Key Value: `ApiKey1Value`
2. Review server logs for authentication errors

### "Prompt not found"

1. Verify `promptName` input variable matches a file in `src/prompts/`
2. Available prompts: `Invoices`, `NewBooking`
3. File naming convention: `<promptName>Prompt.md` and `<promptName>Tools.json`

### "No audio from agent"

1. Check `BOT_PROVIDER=voicelive` is set
2. Verify Azure Voice Live API credentials are configured
3. Review logs for Voice Live API errors

### "Transfer not working"

1. Ensure Architect flow handles `exitReason == "transfer"`
2. Add Transfer to ACD/Queue action after Audio Connector
3. Verify queue exists and has agents available

---

## 🔐 Security Considerations

### Production Credentials

For production deployments, update `src/services/secret-service.ts` to use a secure secret management system:

- **Azure Key Vault**
- **Genesys Cloud Data Actions** (to fetch secrets)
- **Environment variables** from Container Apps secrets

### Network Security

Consider restricting access to your Container App:
- Use **Azure Virtual Network** integration
- Configure **IP restrictions** in Container Apps
- Enable **Genesys Cloud IP allowlisting** (see [Genesys Cloud IPs](https://help.mypurecloud.com/articles/genesys-cloud-public-ip-addresses/))

---

## 📚 References

- [Audio Connector Overview](https://help.mypurecloud.com/articles/audio-connector-overview/)
- [AudioHook Protocol Specification](https://developer.genesys.cloud/devapps/audiohook/)
- [Call Audio Connector Action](https://help.mypurecloud.com/articles/call-audio-connector-action/)
- [Original Blog Post: Audio Connector with OpenAI](https://developer.genesys.cloud/blog/audio-connector-openai)
- [BYOT Pricing](https://help.mypurecloud.com/articles/bring-your-own-technology-services-model-per-turn-minute-rates-current-model/)

---

## 📝 Quick Reference Card

| Item | Value |
|------|-------|
| **WebSocket URL** | `wss://voice-agent.<region>.azurecontainerapps.io` |
| **Health Check** | `https://voice-agent.<region>.azurecontainerapps.io/health` |
| **API Key Name** | `ApiKey1` |
| **API Key Value** | `ApiKey1Value` |
| **Available Prompts** | `Invoices`, `NewBooking` |
| **Required Input Variables** | `promptName` (required), `phoneNumber`, `customerDNI`, `CURRENT_DATE` |
