import dotenv from 'dotenv';
dotenv.config();

import WebSocket from 'ws';
import {
    Session
} from '../websocket/session';

import { VoiceAIAgentBaseClass } from './voice-aiagent-base';

import {
    lookupAirport,
    searchFlight,
    createItinerary
} from './open-ai-tools';

import { getNoInputTimeout } from '../common/environment-variables';

import { Timer } from './timer';


import { create } from 'lodash';

// Retrieve configuration from environment variables.
// Validation moved to constructor to avoid process.exit at module load time
let { OPENAI_API_KEY } = process.env;

// Support both legacy endpoint format and new GA format
// Legacy (Preview): wss://{resource}.openai.azure.com/openai/realtime?api-version=2024-10-01-preview&deployment={deployment}
// GA (Voice Live): wss://{resource}.openai.azure.com/openai/v1/realtime?model={deployment}
const OPENAI_MODEL_ENDPOINT = process.env.OPENAI_MODEL_ENDPOINT || '';

// Voice Live API specific settings
const USE_VOICE_LIVE_API = process.env.USE_VOICE_LIVE_API === 'true';
const AZURE_OPENAI_RESOURCE = process.env.AZURE_OPENAI_RESOURCE || '';
const AZURE_OPENAI_DEPLOYMENT = process.env.AZURE_OPENAI_DEPLOYMENT || 'gpt-realtime';

/**
 * Builds the WebSocket endpoint URL for Azure OpenAI Realtime API
 * Supports both Preview and GA (Voice Live) formats
 */
function buildRealtimeEndpoint(): string {
    // If explicit endpoint is provided, use it
    if (OPENAI_MODEL_ENDPOINT) {
        return OPENAI_MODEL_ENDPOINT;
    }
    
    // Build GA (Voice Live) endpoint if resource is provided
    if (AZURE_OPENAI_RESOURCE) {
        // GA format: wss://{resource}.openai.azure.com/openai/v1/realtime?model={deployment}
        return `wss://${AZURE_OPENAI_RESOURCE}.openai.azure.com/openai/v1/realtime?model=${AZURE_OPENAI_DEPLOYMENT}`;
    }
    
    return '';
}

/**
 * Detects the API format (GA vs Preview) based on endpoint URL
 */
function isGAEndpoint(endpoint: string): boolean {
    // GA endpoints use /openai/v1/realtime path
    return endpoint.includes('/openai/v1/realtime');
}


// Constants

const INITIAL_GREETING = process.env.INITIAL_GREETING || 'Hello';
const VOICE = process.env.OPENAI_VOICE_ID || 'alloy';

// List of Event Types to log to the console. See the OpenAI Realtime API Documentation: https://platform.openai.com/docs/api-reference/realtime
const LOG_EVENT_TYPES = [
    'error',
    'response.content.done',
    'rate_limits.updated',
    'response.done',
    'input_audio_buffer.committed',
    'input_audio_buffer.speech_stopped',
    'input_audio_buffer.speech_started',
    'session.created'
];



export class OpenAIRealTime extends VoiceAIAgentBaseClass {
    async sendKeepAlive(): Promise<void> {
        // Not Required for OpenAI Realtime API
    }
    
    private openAiWs:WebSocket ;
    private endpoint: string;
    private isGAFormat: boolean;
    
    constructor(session:Session){
        // Validate API key at instantiation time
        if (!OPENAI_API_KEY) {
            throw new Error('[OpenAI] Missing OpenAI API key. Please set OPENAI_API_KEY in the .env file.');
        }
        
        // Build the endpoint URL
        const endpoint = buildRealtimeEndpoint();
        if (!endpoint) {
            throw new Error('[OpenAI] Missing OpenAI endpoint. Please set OPENAI_MODEL_ENDPOINT or AZURE_OPENAI_RESOURCE in the .env file.');
        }
        
        super(session,() => {
        console.log(new Date().toISOString() + ':' + '[OpenAI]NoInputTimer:Timeout reached, sending response.create');
        const noInputConversationItem = {
            type: 'conversation.item.create',
            item: {
                type: 'message',
                role: 'user',
                content: [
                    {
                        type: 'input_text',
                        text: process.env.NO_INPUT_MESSAGE || 'User did not provide any input. Act accordingly.'    
                    }
                ]
            }
        };
        console.log(new Date().toISOString()+':'+'[OpenAI]Sending No Input conversation item:', JSON.stringify(noInputConversationItem));
        this.openAiWs.send(JSON.stringify(noInputConversationItem));
        this.openAiWs.send(JSON.stringify({ type: 'response.create' }));
            
        },getNoInputTimeout());

        this.endpoint = endpoint;
        this.isGAFormat = isGAEndpoint(endpoint);
        
        console.log(new Date().toISOString() + ':' + '[OpenAI]END_POINT:', this.endpoint);
        console.log(new Date().toISOString() + ':' + `[OpenAI]API Format: ${this.isGAFormat ? 'GA (Voice Live)' : 'Preview'}`);
        
        // Detect if using Azure OpenAI or OpenAI directly based on endpoint
        const isAzureOpenAI = this.endpoint.includes('.azure.com') || 
                              this.endpoint.includes('cognitiveservices.azure.com');
        
        const wsHeaders = isAzureOpenAI 
            ? { "api-key": OPENAI_API_KEY as string }  // Azure OpenAI uses api-key header
            : { 
                Authorization: `Bearer ${OPENAI_API_KEY}`,
                "OpenAI-Beta": "realtime=v1" 
              };
        
        console.log(new Date().toISOString() + ':' + `[OpenAI]Using ${isAzureOpenAI ? 'Azure OpenAI' : 'OpenAI'} authentication`);
        
        this.openAiWs = new WebSocket(this.endpoint, {
            headers: wsHeaders
        });
        // Control initial session with OpenAI
        const initializeSession = () => {
            
            const sessionUpdate = {
                type: 'session.update',
                session: {
                    turn_detection: {
                        "type": "server_vad",
                        "threshold": 0.9,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500,
                        "create_response": true, // only in conversation mode
                        "interrupt_response": true, // only in conversation mode
                    },
                    input_audio_format: 'g711_ulaw',
                    input_audio_noise_reduction:{
                        type: 'near_field',
                    },
                    output_audio_format: 'g711_ulaw',
                    voice: VOICE,
                    instructions: this.getSystemMessage(),  
                    tools: this.getSystemTools(), 
                    tool_choice: "auto",
                    modalities: ["text", "audio"],
                    temperature: 0.8
                }
            };

            console.log(new Date().toISOString()+ ':[OpenAI]InitializeSession:', JSON.stringify(sessionUpdate));
            this.openAiWs.send(JSON.stringify(sessionUpdate));
            sendInitialConversationItem();
            
        };
        // Send initial conversation item if AI talks first
        const sendInitialConversationItem = () => {
            const initialConversationItem = {
                type: 'conversation.item.create',
                item: {
                    type: 'message',
                    role: 'user',
                    content: [
                        {
                            type: 'input_text',
                            text: INITIAL_GREETING
                        }
                    ]
                }
            };

            console.log(new Date().toISOString()+':'+'[OpenAI]Sending initial conversation item:', JSON.stringify(initialConversationItem));
            this.openAiWs.send(JSON.stringify(initialConversationItem));
            this.openAiWs.send(JSON.stringify({ type: 'response.create' }));
        };
        // Open event for OpenAI WebSocket
        this.openAiWs.on('open', () => {
            console.log(new Date().toISOString()+':'+'[OpenAI]Connected to the OpenAI Realtime API');
            setTimeout(initializeSession, 100);

        });
        // Listen for messages from the OpenAI WebSocket (and send to Twilio if necessary)
        this.openAiWs.on('message', (data:string) => {
            try {
                const response = JSON.parse(data);
                if (LOG_EVENT_TYPES.includes(response.type)) {
                    console.log(new Date().toISOString() + ':' + `[OpenAI]Received event: ${response.type}`, JSON.stringify(response));
                } else {
                    console.log(new Date().toISOString() + ':' + `[OpenAI]Received event: ${response.type}`);
                }
                if (response.type === 'response.audio.delta' && response.delta) {
                    // media: { payload: Buffer.from(response.delta, 'base64').toString('base64') }
                    // Send Audio
                    //this.timer.stopTimer(); // Stop the timer when we receive audio
                    console.log(new Date().toISOString() + ':' + `[OpenAI]ResponseType:response.audio.delta::PlayingNewAudio`);
                    this.session.sendAudio(new Uint8Array(Buffer.from(response.delta, 'base64')));
                }
                if (response.type === 'response.done') {
                    console.log(new Date().toISOString() + ':' + `[OpenAI]ResponseType:response.done::response.response.Status:${response.response.status}`);
                    if (response.response.status == 'completed') {
                        console.log(new Date().toISOString() + ':' + '[OpenAI]Flush Buffer');
                        this.session.flushBuffer();
                        /** */
                        response.response.output.filter((out :any) => out.type === 'function_call').forEach((func_call:any) => {
                            const args = JSON.parse(func_call.arguments);
                            
                            console.log(new Date().toISOString() + ':' + '[OpenAI]FunctionCall|Name:' + func_call.name + '|Data:' + JSON.stringify(args));
                            // Call the function with the provided arguments
                            const responseData = {
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "function_call_output",
                                    "call_id": func_call.call_id,
                                    "output":''
                                }
                            }
                            if(func_call.name=="searchFlightLeg") {
                                const output =searchFlight(args);
                                console.log(new Date().toISOString() + ':' + '[OpenAI]FunctionCall|Name:' + func_call.name + '|Response:' + JSON.stringify(output));
                                responseData.item['output'] = JSON.stringify(output)
                            } else if(func_call.name=="createItinerary") {
                                try {
                                    const output =createItinerary(args);
                                    console.log(new Date().toISOString() + ':' + '[OpenAI]FunctionCall|Name:' + func_call.name + '|Response:' + JSON.stringify(output));
                                    responseData.item['output'] = JSON.stringify(output)
                                }catch (error) {
                                    console.error(new Date().toISOString() + ':' + '[OpenAI]FunctionCall|Name:' + func_call.name + '|Error:' + error);
                                    responseData.item['output'] = 'PNR Creation Failed';
                                }
                            } else if(func_call.name=="transferToAgent") {   
                                console.log(new Date().toISOString() + ':' + '[OpenAI]FunctionCall|Name:' + func_call.name + '|Response:Transfering to Agent| Not Implemented');
                                responseData.item['output'] = JSON.stringify({
                                    "status": "ok",
                                });
                                this.session.sendDisconnect('completed',args.process,{});
                            } else if(func_call.name=="endCall") {
                                this.session.sendDisconnect('completed','EndCall',{});
                            }
                            this.openAiWs.send(JSON.stringify(responseData));
                            this.openAiWs.send(JSON.stringify({ type: 'response.create' }));

                        });
                        
                        
                    } else if (response.response.status == 'failed') {
                        console.error(new Date().toISOString() + ':' + '[OpenAI]FailedResponse|Sending Disconnect');
                        this.session.sendDisconnect('error','RateLimitError' , response.response.status.status_details.error);
                    }
                }
                if (response.type === 'input_audio_buffer.speech_started') {
                    // this is the place where we stop the timer
                    console.log(new Date().toISOString() + ':' + '[OpenAI]InputAudioBufferSpeechStarted|Halting No Input Timer|Sending BargeIn');
                    //this.noInputTimer.stopTimer();
                    this.noInputTimer.haltTimer();
                    this.session.sendBargeIn();
                    this.session.setIsAudioPlaying(true);
                }
                if(response.type === 'input_audio_buffer.speech_stopped') {
                    console.log(new Date().toISOString() + ':' + '[OpenAI]InputAudioBufferSpeechStopped|Resuming No Input Timer');  
                    this.noInputTimer.resumeTimer();
                    //this.noInputTimer.startTimer();
                }
            }
            catch (error) {
                console.error(new Date().toISOString() + ':' + '[OpenAI]Error processing OpenAI message:', error, 'Raw message:', data);
            }
        });
    }
    protected isAgentConnected(): boolean {
        // Check if the WebSocket connection to OpenAI is open
        return this.openAiWs && this.openAiWs.readyState === WebSocket.OPEN;
    }
    async processAudio(audioPayload: Uint8Array): Promise<void> {
        if (this.isAgentConnected()) {
            const audioAppend = {
                type: 'input_audio_buffer.append',
                audio: Buffer.from(audioPayload).toString('base64')
            };
            this.openAiWs.send(JSON.stringify(audioAppend));
        }
    }
    async processPlaybackCompleted(): Promise<void> {
        if (this.isAgentConnected()) {
            console.log(new Date().toISOString() + ':' + '[OpenAI]PlaybackCompleted|Starting no input timer');
            // Start the no input timer after sending response.create
            this.noInputTimer.startTimer();
        }
    }
    cancelResponse() {
        if(this.isAgentConnected()) {
            const cancelResponsePayload = {
                type:'response.cancel'
            };
            console.log(new Date().toISOString+":"+"Interrupting OpenAIResponse");
            this.openAiWs.send(JSON.stringify(cancelResponsePayload));
        }
    }
    async close(): Promise<void> {
        if(this.isAgentConnected()){
            console.log(new Date().toISOString()+':'+'[OpenAI]Closing OpenAI Connection');
            this.openAiWs.close();
        }
    }
}



