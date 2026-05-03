import pino from 'pino';
import { createServer } from 'http';
import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import fs from 'fs-extra';
import path from 'path';
import { fileURLToPath } from 'url';
import axios from 'axios';
import { create } from '@open-wa/wa-automate';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const logger = pino({
  level: 'debug',
  transport: {
    target: 'pino-pretty',
    options: { colorize: true },
  },
}).default ?? pino();

logger.info('Starting Inika WhatsApp Gateway...');

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());

// Store for OpenWA clients per tenant
const clients = new Map();

// Store for session state (connection status, phone number, etc)
const sessionStates = new Map();

const SESSIONS_DIR = process.env.SESSIONS_DIR || './sessions';
const WEBHOOK_URL = process.env.WEBHOOK_URL || 'http://localhost:8000/webhook/whatsapp-baileys';
const PORT = process.env.PORT || 3002;
const API_KEY = process.env.API_KEY || '';

fs.ensureDirSync(SESSIONS_DIR);

// API Key middleware
const apiKeyAuth = (req, res, next) => {
  if (!API_KEY || req.headers['x-api-key'] === API_KEY) {
    next();
  } else {
    res.status(401).json({ error: 'Unauthorized' });
  }
};

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'inika-whatsapp-gateway',
    timestamp: new Date().toISOString(),
  });
});

// List all sessions
app.get('/api/sessions', apiKeyAuth, (req, res) => {
  const sessions = [];
  for (const [tenantId, state] of sessionStates.entries()) {
    sessions.push({
      name: tenantId,
      status: state.connected ? 'CONNECTED' : 'DISCONNECTED',
      number: state.phoneNumber || null,
      pushName: state.pushName || null,
    });
  }
  res.json(sessions);
});

// Get session by name
app.get('/api/sessions/:name', apiKeyAuth, async (req, res) => {
  const { name } = req.params;
  const state = sessionStates.get(name);
  const client = clients.get(name);

  if (!state) {
    return res.status(404).json({ error: 'Session not found' });
  }

  // Try to get latest session info from client
  let phoneNumber = state.phoneNumber;
  let pushName = state.pushName;
  let connected = state.connected;

  try {
    if (client && state.connected) {
      const info = await client.getHostDevice();
      if (info) {
        phoneNumber = info.wid;
        pushName = info.pushname;
      }
    }
  } catch (e) {
    // Client might be disconnected
  }

  res.json({
    name,
    status: connected ? 'CONNECTED' : 'DISCONNECTED',
    number: phoneNumber,
    pushName,
  });
});

// Get QR code
app.get('/api/sessions/:name/qr', apiKeyAuth, async (req, res) => {
  const { name } = req.params;
  const state = sessionStates.get(name);

  if (!state) {
    return res.status(404).json({ error: 'Session not found' });
  }

  if (state.connected) {
    return res.status(200).json({ qr: [], message: 'Already connected' });
  }

  if (state.qr) {
    return res.status(200).json({ qr: [{ code: state.qr, base64: state.qr }] });
  }

  res.status(200).json({ qr: [], message: 'No QR code available' });
});

// Create/start session
app.post('/api/sessions', apiKeyAuth, async (req, res) => {
  const { name, config, force } = req.body;

  if (!name) {
    return res.status(400).json({ error: 'Session name is required' });
  }

  try {
    await connectToWhatsApp(name, config?.webhookUrl);
    res.status(201).json({ name, status: 'created' });
  } catch (error) {
    logger.error({ err: error, tenantId: name }, 'Failed to create session');
    res.status(500).json({ error: error.message });
  }
});

// Delete/logout session
app.delete('/api/sessions/:name', apiKeyAuth, async (req, res) => {
  const { name } = req.params;
  const client = clients.get(name);

  if (client) {
    try {
      await client.logout();
    } catch (e) {
      logger.warn({ err: e, tenantId: name }, 'Logout error');
    }
    clients.delete(name);
  }

  // Delete session files
  const sessionPath = path.join(SESSIONS_DIR, name);
  await fs.remove(sessionPath).catch(() => {});

  sessionStates.delete(name);
  logger.info({ tenantId: name }, 'Session deleted');
  res.json({ success: true, message: 'Session deleted' });
});

// Send text message
app.post('/api/messages/sendText', apiKeyAuth, async (req, res) => {
  const { session, chatId, text } = req.body;

  if (!session || !chatId || !text) {
    return res.status(400).json({ error: 'session, chatId, and text are required' });
  }

  const client = clients.get(session);
  if (!client) {
    return res.status(400).json({ error: 'Session not connected' });
  }

  try {
    const message = await client.sendText(chatId, text);
    logger.info({ chatId, tenantId: session }, 'Message sent');
    res.json({
      key: { id: message.id, remoteJid: chatId },
      message: { text },
    });
  } catch (error) {
    logger.error({ err: error, tenantId: session }, 'Send message error');
    res.status(500).json({ error: error.message });
  }
});

// Connect to WhatsApp using OpenWA
async function connectToWhatsApp(tenantId, webhookUrl) {
  const sessionPath = path.join(SESSIONS_DIR, tenantId);
  await fs.ensureDir(sessionPath);

  // Initialize session state
  const state = {
    qr: null,
    connected: false,
    phoneNumber: null,
    pushName: null,
    webhookUrl: webhookUrl || WEBHOOK_URL,
  };
  sessionStates.set(tenantId, state);

  // Check if already connected
  const existingClient = clients.get(tenantId);
  if (existingClient) {
    logger.info({ tenantId }, 'Client already exists');
    return state;
  }

  logger.info({ tenantId }, 'Creating OpenWA client...');

  const client = await create({
    sessionId: tenantId,
    headless: true,
    multiDevice: true,
    sessionStoragePath: SESSIONS_DIR,
    qrTimeoutMs: 120000,
    authTimeoutMs: 60000,
    throwErrorOnTosBlock: false,
    customUserAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    onMessage: async (message) => {
      if (message.fromMe) return;

      const remoteJid = message.from || message.chatId;
      if (!remoteJid || remoteJid === 'status@broadcast') return;

      const text = message.body || '';
      const messageType = message.type || 'chat';

      logger.info({
        tenantId,
        from: message.from,
        messageType,
        hasText: !!text,
      }, 'Incoming message');

      try {
        const fullWebhookUrl = `${state.webhookUrl}${state.webhookUrl.includes('?') ? '&' : '?'}tenant_id=${tenantId}`;
        await axios.post(fullWebhookUrl, {
          event: 'onMessage',
          session: tenantId,
          data: {
            key: { id: message.id, remoteJid },
            message: message,
            pushName: message.pushName || state.pushName,
            messageType,
            text,
          },
        }, { timeout: 10000 });
        logger.debug({ remoteJid, tenantId }, 'Webhook sent');
      } catch (e) {
        logger.error({ err: e, tenantId }, 'Webhook error');
      }
    },
    onStateChange: async (stateChange) => {
      logger.info({ tenantId, state: stateChange }, 'State changed');

      if (stateChange === 'CONNECTED') {
        state.connected = true;
        state.qr = null;
        try {
          const info = await client.getHostDevice();
          if (info) {
            state.phoneNumber = info.wid;
            state.pushName = info.pushname;
          }
        } catch (e) {}

        logger.info({ tenantId, phoneNumber: state.phoneNumber }, 'WhatsApp connected successfully');
      } else if (stateChange === 'DISCONNECTED' || stateChange === 'LOGGED_OUT') {
        state.connected = false;
        logger.warn({ tenantId }, 'WhatsApp disconnected');
      }
    },
    onSessionToken: async (token) => {
      logger.debug({ tenantId }, 'Session token updated');
    },
    onQR: (qr) => {
      logger.info({ tenantId }, 'QR code received');
      state.qr = qr;
      // Print QR in terminal
      try {
        const qrcodeTerminal = require('qrcode-terminal');
        qrcodeTerminal.generate(qr, { small: true });
      } catch (e) {
        logger.warn({ tenantId }, 'qrcode-terminal not available');
      }
    },
  });

  clients.set(tenantId, client);

  // Check if already authenticated
  try {
    const info = await client.getHostDevice();
    if (info && info.wid) {
      state.connected = true;
      state.phoneNumber = info.wid;
      state.pushName = info.pushname;
      logger.info({ tenantId, phoneNumber: state.phoneNumber }, 'Session already authenticated');
    }
  } catch (e) {
    logger.info({ tenantId }, 'Not authenticated yet, waiting for QR scan');
  }

  return state;
}

// Start server
const server = createServer(app);
server.listen(PORT, () => {
  logger.info({
    port: PORT,
    sessionsDir: SESSIONS_DIR,
    webhookUrl: WEBHOOK_URL,
  }, 'Inika WhatsApp Gateway started (OpenWA)');
});

// Graceful shutdown
const shutdown = async (signal) => {
  logger.info({ signal }, 'Shutting down...');

  for (const [tenantId, client] of clients.entries()) {
    try {
      await client.kill();
      logger.info({ tenantId }, 'Client killed');
    } catch (e) {
      logger.warn({ err: e, tenantId }, 'Kill error');
    }
  }

  server.close(() => {
    logger.info('Server closed');
    process.exit(0);
  });

  setTimeout(() => {
    logger.warn('Forced exit');
    process.exit(1);
  }, 10000);
};

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));
