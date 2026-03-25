import dotenv from 'dotenv';
import * as crypto from 'crypto';
import { Server } from './websocket/server';
import { initCosmosDB } from './services/open-ai-tools';

// Polyfill for crypto.randomUUID() - required by @azure/cosmos SDK in Node.js
if (!(globalThis as any).crypto) {
    (globalThis as any).crypto = crypto;
}

console.log('Starting service.');

dotenv.config();

// Initialize Cosmos DB connection for invoice queries
initCosmosDB();

new Server().start();