import dotenv from 'dotenv';
dotenv.config();

import WebSocket from 'ws';
import { Session } from '../websocket/session';
import { VoiceAIAgentBaseClass } from './voice-aiagent-base';
import { lookupAirport, searchFlight, createItinerary, getInvoices } from './open-ai-tools';
import { getNoInputTimeout } from '../common/environment-variables';

// ============== Voice Live API Configuration ==============
// Voice Live uses a different endpoint format and supports Azure Speech voices

const VOICE_LIVE_ENDPOINT = process.env.AZURE_VOICE_LIVE_ENDPOINT || '';
const VOICE_LIVE_API_KEY = process.env.AZURE_VOICE_LIVE_API_KEY || '';
const VOICE_LIVE_MODEL = process.env.VOICE_LIVE_MODEL || 'gpt-realtime';
const VOICE_LIVE_API_VERSION = process.env.AZURE_VOICE_LIVE_API_VERSION || '2025-10-01';
const VOICE_LIVE_VOICE = process.env.AZURE_VOICE_LIVE_VOICE || 'es-ES-Ximena:DragonHDLatestNeural';

const INITIAL_GREETING = process.env.INITIAL_GREETING || 'Hello';

// Voice Live uses PCM16 at 24kHz, but AudioConnector uses g711_ulaw at 8kHz
// We need to handle audio format conversion

// List of Event Types to log
const LOG_EVENT_TYPES = [
    'error',
    'session.created',
    'session.updated',
    'response.created',
    'response.done',
    'response.audio.done',
    'input_audio_buffer.speech_started',
    'input_audio_buffer.speech_stopped',
    'conversation.item.created',
];

/**
 * Builds the Voice Live WebSocket endpoint URL
 * Voice Live SDK format: wss://{resource}.services.ai.azure.com/voice-live/realtime?api-version={version}&model={model}
 * NOTE: Voice Live uses /voice-live/realtime path (NOT /openai/realtime)
 */
function buildVoiceLiveEndpoint(): string {
    if (!VOICE_LIVE_ENDPOINT) return '';
    
    // Remove trailing slash if present
    let baseEndpoint = VOICE_LIVE_ENDPOINT.replace(/\/$/, '');
    
    // Convert https to wss
    const wsEndpoint = baseEndpoint.replace('https://', 'wss://');
    
    // Build the full WebSocket URL for Voice Live API
    // Format: wss://{resource}.services.ai.azure.com/voice-live/realtime?api-version={version}&model={model}
    const fullEndpoint = `${wsEndpoint}/voice-live/realtime?api-version=${VOICE_LIVE_API_VERSION}&model=${VOICE_LIVE_MODEL}`;
    
    console.log(new Date().toISOString() + ':' + '[VoiceLive]Built endpoint:', fullEndpoint);
    
    return fullEndpoint;
}

/**
 * Check if voice is an Azure Speech voice (contains colon or regional prefix)
 */
function isAzureSpeechVoice(voice: string): boolean {
    return voice.includes(':') || voice.match(/^[a-z]{2}-[A-Z]{2}-/i) !== null;
}

/**
 * µ-law to PCM16 conversion (8kHz µ-law to 16-bit PCM)
 * Voice Live expects PCM16 at 24kHz, AudioConnector sends g711_ulaw at 8kHz
 */
const ULAW_DECODE_TABLE = new Int16Array([
    -32124, -31100, -30076, -29052, -28028, -27004, -25980, -24956,
    -23932, -22908, -21884, -20860, -19836, -18812, -17788, -16764,
    -15996, -15484, -14972, -14460, -13948, -13436, -12924, -12412,
    -11900, -11388, -10876, -10364, -9852, -9340, -8828, -8316,
    -7932, -7676, -7420, -7164, -6908, -6652, -6396, -6140,
    -5884, -5628, -5372, -5116, -4860, -4604, -4348, -4092,
    -3900, -3772, -3644, -3516, -3388, -3260, -3132, -3004,
    -2876, -2748, -2620, -2492, -2364, -2236, -2108, -1980,
    -1884, -1820, -1756, -1692, -1628, -1564, -1500, -1436,
    -1372, -1308, -1244, -1180, -1116, -1052, -988, -924,
    -876, -844, -812, -780, -748, -716, -684, -652,
    -620, -588, -556, -524, -492, -460, -428, -396,
    -372, -356, -340, -324, -308, -292, -276, -260,
    -244, -228, -212, -196, -180, -164, -148, -132,
    -120, -112, -104, -96, -88, -80, -72, -64,
    -56, -48, -40, -32, -24, -16, -8, 0,
    32124, 31100, 30076, 29052, 28028, 27004, 25980, 24956,
    23932, 22908, 21884, 20860, 19836, 18812, 17788, 16764,
    15996, 15484, 14972, 14460, 13948, 13436, 12924, 12412,
    11900, 11388, 10876, 10364, 9852, 9340, 8828, 8316,
    7932, 7676, 7420, 7164, 6908, 6652, 6396, 6140,
    5884, 5628, 5372, 5116, 4860, 4604, 4348, 4092,
    3900, 3772, 3644, 3516, 3388, 3260, 3132, 3004,
    2876, 2748, 2620, 2492, 2364, 2236, 2108, 1980,
    1884, 1820, 1756, 1692, 1628, 1564, 1500, 1436,
    1372, 1308, 1244, 1180, 1116, 1052, 988, 924,
    876, 844, 812, 780, 748, 716, 684, 652,
    620, 588, 556, 524, 492, 460, 428, 396,
    372, 356, 340, 324, 308, 292, 276, 260,
    244, 228, 212, 196, 180, 164, 148, 132,
    120, 112, 104, 96, 88, 80, 72, 64,
    56, 48, 40, 32, 24, 16, 8, 0
]);

/**
 * Cubic interpolation helper for smoother upsampling
 */
function cubicInterpolate(y0: number, y1: number, y2: number, y3: number, t: number): number {
    const a0 = y3 - y2 - y0 + y1;
    const a1 = y0 - y1 - a0;
    const a2 = y2 - y0;
    const a3 = y1;
    return Math.round(a0 * t * t * t + a1 * t * t + a2 * t + a3);
}

/**
 * Convert µ-law (8kHz) to PCM16 and upsample to 24kHz
 * Uses cubic interpolation for smoother, higher quality audio
 */
function ulawToPcm16_24kHz(ulawData: Uint8Array): Buffer {
    // First decode µ-law to PCM16 at 8kHz
    const pcm8kHz = new Int16Array(ulawData.length);
    for (let i = 0; i < ulawData.length; i++) {
        pcm8kHz[i] = ULAW_DECODE_TABLE[ulawData[i]];
    }
    
    // Upsample from 8kHz to 24kHz (3x) using cubic interpolation
    const pcm24kHz = new Int16Array(pcm8kHz.length * 3);
    for (let i = 0; i < pcm8kHz.length; i++) {
        // Get 4 samples for cubic interpolation (with boundary handling)
        const y0 = i > 0 ? pcm8kHz[i - 1] : pcm8kHz[i];
        const y1 = pcm8kHz[i];
        const y2 = i < pcm8kHz.length - 1 ? pcm8kHz[i + 1] : pcm8kHz[i];
        const y3 = i < pcm8kHz.length - 2 ? pcm8kHz[i + 2] : y2;
        
        // Original sample
        pcm24kHz[i * 3] = y1;
        // Cubic interpolation at 1/3 and 2/3 positions
        pcm24kHz[i * 3 + 1] = cubicInterpolate(y0, y1, y2, y3, 1/3);
        pcm24kHz[i * 3 + 2] = cubicInterpolate(y0, y1, y2, y3, 2/3);
    }
    
    return Buffer.from(pcm24kHz.buffer);
}

/**
 * PCM16 encoding table for µ-law
 */
const ULAW_ENCODE_TABLE = [
    0, 0, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7
];

/**
 * Convert a single PCM16 sample to µ-law
 */
function linearToUlaw(sample: number): number {
    const BIAS = 0x84;
    const CLIP = 32635;
    
    let sign = (sample >> 8) & 0x80;
    if (sign) sample = -sample;
    if (sample > CLIP) sample = CLIP;
    
    sample = sample + BIAS;
    const exponent = ULAW_ENCODE_TABLE[(sample >> 7) & 0xFF];
    const mantissa = (sample >> (exponent + 3)) & 0x0F;
    
    return ~(sign | (exponent << 4) | mantissa) & 0xFF;
}

/**
 * Convert PCM16 at 24kHz to µ-law at 8kHz (downsample 3x)
 * Uses averaging filter before downsampling to reduce aliasing artifacts
 */
function pcm16_24kHzToUlaw(pcm24kHzBase64: string): Uint8Array {
    const pcm24kHzBuffer = Buffer.from(pcm24kHzBase64, 'base64');
    const pcm24kHz = new Int16Array(pcm24kHzBuffer.buffer, pcm24kHzBuffer.byteOffset, pcm24kHzBuffer.length / 2);
    
    // Downsample from 24kHz to 8kHz using averaging filter (anti-aliasing)
    const ulawLength = Math.floor(pcm24kHz.length / 3);
    const ulawData = new Uint8Array(ulawLength);
    
    for (let i = 0; i < ulawLength; i++) {
        const idx = i * 3;
        // Average 3 samples for anti-aliasing before downsampling
        const sample0 = pcm24kHz[idx] || 0;
        const sample1 = pcm24kHz[idx + 1] || 0;
        const sample2 = pcm24kHz[idx + 2] || 0;
        const avgSample = Math.round((sample0 + sample1 + sample2) / 3);
        ulawData[i] = linearToUlaw(avgSample);
    }
    
    return ulawData;
}


export class VoiceLiveAgent extends VoiceAIAgentBaseClass {
    private voiceLiveWs: WebSocket;
    private endpoint: string;
    private pendingFunctionCall: { name: string; call_id: string; arguments?: string } | null = null;
    
    constructor(session: Session) {
        // Validate configuration
        if (!VOICE_LIVE_API_KEY) {
            throw new Error('[VoiceLive] Missing API key. Please set AZURE_VOICE_LIVE_API_KEY in the .env file.');
        }
        if (!VOICE_LIVE_ENDPOINT) {
            throw new Error('[VoiceLive] Missing endpoint. Please set AZURE_VOICE_LIVE_ENDPOINT in the .env file.');
        }
        
        super(session, () => {
            console.log(new Date().toISOString() + ':' + '[VoiceLive]NoInputTimer:Timeout reached, sending response.create');
            const noInputConversationItem = {
                type: 'conversation.item.create',
                item: {
                    type: 'message',
                    role: 'user',
                    content: [{
                        type: 'input_text',
                        text: process.env.NO_INPUT_MESSAGE || 'User did not provide any input. Act accordingly.'
                    }]
                }
            };
            console.log(new Date().toISOString() + ':' + '[VoiceLive]Sending No Input conversation item');
            this.voiceLiveWs.send(JSON.stringify(noInputConversationItem));
            this.voiceLiveWs.send(JSON.stringify({ type: 'response.create' }));
        }, getNoInputTimeout());
        
        this.endpoint = buildVoiceLiveEndpoint();
        console.log(new Date().toISOString() + ':' + '[VoiceLive]Endpoint:', this.endpoint);
        console.log(new Date().toISOString() + ':' + '[VoiceLive]Voice:', VOICE_LIVE_VOICE);
        console.log(new Date().toISOString() + ':' + '[VoiceLive]Model:', VOICE_LIVE_MODEL);
        
        // Connect to Voice Live WebSocket
        console.log(new Date().toISOString() + ':' + '[VoiceLive]Connecting to WebSocket...');
        this.voiceLiveWs = new WebSocket(this.endpoint, {
            headers: {
                'api-key': VOICE_LIVE_API_KEY
            }
        });
        
        // Handle connection error immediately
        this.voiceLiveWs.on('error', (error: Error) => {
            console.error(new Date().toISOString() + ':' + '[VoiceLive]WebSocket error:', error.message);
            console.error(new Date().toISOString() + ':' + '[VoiceLive]Error details:', JSON.stringify(error));
        });
        
        this.voiceLiveWs.on('close', (code: number, reason: string) => {
            console.log(new Date().toISOString() + ':' + `[VoiceLive]WebSocket closed: code=${code}, reason=${reason}`);
        });
        
        // Initialize session on connection
        const initializeSession = () => {
            // Voice configuration for Voice Live API
            // Azure Speech voices require: { type: 'azure-standard', name: 'es-ES-XimenaNeural' }
            // Note: type uses hyphen (azure-standard) per official Microsoft documentation
            // OpenAI voices can be passed as string: 'alloy', 'echo', 'shimmer', 'ash', 'ballad', 'coral', 'sage', 'verse'
            
            let voiceConfig: any;
            
            if (isAzureSpeechVoice(VOICE_LIVE_VOICE)) {
                // For Azure Speech voices like "es-ES-XimenaNeural" or "en-US-Ava:DragonHDLatestNeural"
                // Using 'azure-standard' (hyphen) per official Voice Live API documentation
                voiceConfig = { type: 'azure-standard', name: VOICE_LIVE_VOICE };
            } else {
                // For OpenAI voices like "alloy", "shimmer", etc.
                voiceConfig = VOICE_LIVE_VOICE;
            }
            
            const sessionUpdate = {
                type: 'session.update',
                session: {
                    modalities: ['text', 'audio'],
                    instructions: this.getSystemMessage(),
                    voice: voiceConfig,
                    input_audio_format: 'pcm16',
                    output_audio_format: 'pcm16',
                    turn_detection: {
                        type: 'server_vad',
                        threshold: 0.5,
                        prefix_padding_ms: 300,
                        silence_duration_ms: 700,  // 700ms like Python SDK for natural pauses
                        create_response: true,
                        interrupt_response: true
                    },
                    // Echo cancellation - prevents the AI from hearing its own output
                    input_audio_echo_cancellation: {
                        type: 'server_echo_cancellation'
                    },
                    // Noise reduction - Azure Deep Noise Suppression
                    input_audio_noise_reduction: {
                        type: 'azure_deep_noise_suppression'
                    },
                    input_audio_transcription: {
                        model: 'whisper-1'
                    },
                    tools: this.getSystemTools(),
                    tool_choice: 'auto',
                    temperature: 0.8
                }
            };
            
            console.log(new Date().toISOString() + ':' + '[VoiceLive]InitializeSession:', JSON.stringify(sessionUpdate));
            this.voiceLiveWs.send(JSON.stringify(sessionUpdate));
        };
        
        // Send initial greeting
        const sendInitialGreeting = () => {
            const initialConversationItem = {
                type: 'conversation.item.create',
                item: {
                    type: 'message',
                    role: 'user',
                    content: [{
                        type: 'input_text',
                        text: INITIAL_GREETING
                    }]
                }
            };
            
            console.log(new Date().toISOString() + ':' + '[VoiceLive]Sending initial greeting');
            this.voiceLiveWs.send(JSON.stringify(initialConversationItem));
            this.voiceLiveWs.send(JSON.stringify({ type: 'response.create' }));
        };
        
        // Handle WebSocket events
        this.voiceLiveWs.on('open', () => {
            console.log(new Date().toISOString() + ':' + '[VoiceLive]Connected to Voice Live API');
            setTimeout(initializeSession, 100);
        });
        
        this.voiceLiveWs.on('message', (data: string) => {
            try {
                const response = JSON.parse(data);
                
                if (LOG_EVENT_TYPES.includes(response.type)) {
                    console.log(new Date().toISOString() + ':' + `[VoiceLive]Event: ${response.type}`, JSON.stringify(response).substring(0, 500));
                } else {
                    console.log(new Date().toISOString() + ':' + `[VoiceLive]Event: ${response.type}`);
                }
                
                // Handle session updated - start greeting
                if (response.type === 'session.updated') {
                    console.log(new Date().toISOString() + ':' + '[VoiceLive]Session configured');
                    sendInitialGreeting();
                }
                
                // Handle audio delta - convert PCM16 24kHz to µ-law 8kHz for AudioConnector
                if (response.type === 'response.audio.delta' && response.delta) {
                    console.log(new Date().toISOString() + ':' + '[VoiceLive]Received audio delta');
                    // Convert PCM16 24kHz to µ-law 8kHz
                    const ulawData = pcm16_24kHzToUlaw(response.delta);
                    this.session.sendAudio(ulawData);
                }
                
                // Handle response done - process function calls
                if (response.type === 'response.done') {
                    console.log(new Date().toISOString() + ':' + '[VoiceLive]Response done');
                    this.session.flushBuffer();
                    
                    // Process function calls
                    if (response.response?.output) {
                        response.response.output
                            .filter((out: any) => out.type === 'function_call')
                            .forEach((funcCall: any) => {
                                this.handleFunctionCall(funcCall);
                            });
                    }
                }
                
                // Handle conversation item created (for function calls)
                if (response.type === 'conversation.item.created') {
                    if (response.item?.type === 'function_call') {
                        this.pendingFunctionCall = {
                            name: response.item.name,
                            call_id: response.item.call_id
                        };
                        console.log(new Date().toISOString() + ':' + `[VoiceLive]Function call detected: ${response.item.name}`);
                    }
                }
                
                // Handle function call arguments
                if (response.type === 'response.function_call_arguments.done') {
                    if (this.pendingFunctionCall) {
                        this.pendingFunctionCall.arguments = response.arguments;
                    }
                }
                
                // Handle speech events
                if (response.type === 'input_audio_buffer.speech_started') {
                    console.log(new Date().toISOString() + ':' + '[VoiceLive]Speech started - sending barge-in');
                    this.noInputTimer.haltTimer();
                    this.session.sendBargeIn();
                    this.session.setIsAudioPlaying(true);
                }
                
                if (response.type === 'input_audio_buffer.speech_stopped') {
                    console.log(new Date().toISOString() + ':' + '[VoiceLive]Speech stopped');
                    this.noInputTimer.resumeTimer();
                }
                
                // Handle errors
                if (response.type === 'error') {
                    console.error(new Date().toISOString() + ':' + '[VoiceLive]Error:', response.error?.message);
                }
                
            } catch (error) {
                console.error(new Date().toISOString() + ':' + '[VoiceLive]Error processing message:', error);
            }
        });
    }
    
    private async handleFunctionCall(funcCall: any) {
        const args = JSON.parse(funcCall.arguments || '{}');
        console.log(new Date().toISOString() + ':' + `[VoiceLive]FunctionCall: ${funcCall.name}`, JSON.stringify(args));
        
        const responseData = {
            type: 'conversation.item.create',
            item: {
                type: 'function_call_output',
                call_id: funcCall.call_id,
                output: ''
            }
        };
        
        if (funcCall.name === 'searchFlightLeg') {
            const output = searchFlight(args);
            responseData.item.output = JSON.stringify(output);
        } else if (funcCall.name === 'createItinerary') {
            try {
                const output = createItinerary(args);
                responseData.item.output = JSON.stringify(output);
            } catch (error) {
                responseData.item.output = 'PNR Creation Failed';
            }
        } else if (funcCall.name === 'getInvoices' || funcCall.name === 'get_billing_info') {
            // Handle invoice/billing queries from Cosmos DB
            try {
                const output = await getInvoices(args);
                responseData.item.output = JSON.stringify(output);
                console.log(new Date().toISOString() + ':' + `[VoiceLive]getInvoices result: ${JSON.stringify(output)}`);
            } catch (error) {
                console.error(new Date().toISOString() + ':' + `[VoiceLive]getInvoices error:`, error);
                responseData.item.output = JSON.stringify({ status: 'error', error: 'Failed to retrieve invoices' });
            }
        } else if (funcCall.name === 'transferToAgent') {
            responseData.item.output = JSON.stringify({ status: 'ok' });
            this.session.sendDisconnect('completed', args.process || 'transfer', {});
        } else if (funcCall.name === 'endCall') {
            this.session.sendDisconnect('completed', 'EndCall', {});
            return;
        }
        
        this.voiceLiveWs.send(JSON.stringify(responseData));
        this.voiceLiveWs.send(JSON.stringify({ type: 'response.create' }));
    }
    
    protected isAgentConnected(): boolean {
        return this.voiceLiveWs && this.voiceLiveWs.readyState === WebSocket.OPEN;
    }
    
    async sendKeepAlive(): Promise<void> {
        // Voice Live handles keep-alive internally
    }
    
    async processAudio(audioPayload: Uint8Array): Promise<void> {
        if (this.isAgentConnected()) {
            // Convert µ-law 8kHz to PCM16 24kHz
            const pcm24kHz = ulawToPcm16_24kHz(audioPayload);
            const audioBase64 = pcm24kHz.toString('base64');
            
            const audioAppend = {
                type: 'input_audio_buffer.append',
                audio: audioBase64
            };
            this.voiceLiveWs.send(JSON.stringify(audioAppend));
        }
    }
    
    async processPlaybackCompleted(): Promise<void> {
        if (this.isAgentConnected()) {
            console.log(new Date().toISOString() + ':' + '[VoiceLive]PlaybackCompleted - starting no input timer');
            this.noInputTimer.startTimer();
        }
    }
    
    async close(): Promise<void> {
        if (this.isAgentConnected()) {
            console.log(new Date().toISOString() + ':' + '[VoiceLive]Closing connection');
            this.voiceLiveWs.close();
        }
    }
}
