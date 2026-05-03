import pino from 'pino';
import { createServer } from 'http';
import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import fs from 'fs-extra';
import path from 'path';
import { fileURLToPath } from 'url';
import qrcode from 'qrcode';
import axios from 'axios';
import { Boom } from '@hapi/boom';
import {
  useMultiFileAuthState,
  makeCacheableSignalKeyStore,
  makeWASocket,
  Browsers,
  DisconnectReason,
  getContentType,
} from '@whiskeysockets/baileys';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Create proper logger with debug level for Baileys
const logger = pino({
  level: 'debug',
  transport: {
    target: 'pino-pretty',
    options: {
      colorize: true,
    },
  },
}).default ?? pino();

logger.info('Starting Inika WhatsApp Gateway...');

// Load environment variables
dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());

// Store for sockets separately (can't be stored in JSON-serializable cache)
const sockets = new Map();

// Store for serializable session state (QR code, connection status, etc)
const sessionStates = new Map();

const SESSIONS_DIR = process.env.SESSIONS_DIR || './sessions';
const WEBHOOK_URL = process.env.WEBHOOK_URL || 'http://localhost:8000/webhook/whatsapp-baileys';
const PORT = process.env.PORT || 3002;
const API_KEY = process.env.API_KEY || '';

// Ensure sessions directory exists
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

  if (!state) {
    // Check if auth files exist
    const sessionPath = path.join(SESSIONS_DIR, name);
    if (await fs.pathExists(sessionPath)) {
      return res.json({
        name,
        status: 'DISCONNECTED',
        number: null,
        pushName: null,
      });
    }
    return res.status(404).json({ error: 'Session not found' });
  }

  res.json({
    name,
    status: state.connected ? 'CONNECTED' : 'CONNECTING',
    number: state.phoneNumber || null,
    pushName: state.pushName || null,
    imgUrl: state.qr || null,
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
    const qrData = [{
      code: state.qr.split(',')[1] || state.qr,
      base64: state.qr,
    }];
    return res.status(200).json({ qr: qrData });
  }

  res.status(200).json({ qr: [], message: 'No QR code available' });
});

// Create session
app.post('/api/sessions', apiKeyAuth, async (req, res) => {
  const { name, config, force } = req.body;

  if (!name) {
    return res.status(400).json({ error: 'Session name is required' });
  }

  // If force=true, delete existing session first
  if (force) {
    const existingSocket = sockets.get(name);
    if (existingSocket) {
      try {
        await existingSocket.logout();
      } catch (e) {}
      sockets.delete(name);
    }
    const sessionPath = path.join(SESSIONS_DIR, name);
    await fs.remove(sessionPath).catch(() => {});
    sessionStates.delete(name);
    logger.info({ tenantId: name }, 'Existing session forcefully deleted');
  }

  const existingSocket = sockets.get(name);
  if (existingSocket) {
    return res.status(409).json({ error: 'Session already exists' });
  }

  // Initialize session
  try {
    await connectToWhatsApp(name, config?.webhookUrl);
    res.status(201).json({ name, status: 'created' });
  } catch (error) {
    logger.error({ err: error, tenantId: name }, 'Failed to create session');
    res.status(500).json({ error: error.message });
  }
});

// Start session
app.post('/api/sessions/:name/start', apiKeyAuth, async (req, res) => {
  const { name } = req.params;
  try {
    await connectToWhatsApp(name);
    res.status(200).json({ name, status: 'started' });
  } catch (error) {
    logger.error({ err: error, tenantId: name }, 'Failed to start session');
    res.status(500).json({ error: error.message });
  }
});

// Delete session (logout)
app.delete('/api/sessions/:name', apiKeyAuth, async (req, res) => {
  const { name } = req.params;
  const sock = sockets.get(name);

  if (sock) {
    try {
      await sock.logout();
    } catch (e) {
      logger.warn({ err: e, tenantId: name }, 'Logout error');
    }
    sockets.delete(name);
  }

  // Delete auth files
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

  const sock = sockets.get(session);
  if (!sock) {
    return res.status(400).json({ error: 'Session not connected' });
  }

  try {
    const jid = chatId.includes('@') ? chatId : `${chatId}@s.whatsapp.net`;
    const message = await sock.sendMessage(jid, { text });

    logger.info({ jid, tenantId: session }, 'Message sent');
    res.json({
      key: { id: message.key.id, remoteJid: jid },
      message: { text },
    });
  } catch (error) {
    logger.error({ err: error, tenantId: session }, 'Send message error');
    res.status(500).json({ error: error.message });
  }
});

/**
 * Connect to WhatsApp using official Baileys patterns
 */
async function connectToWhatsApp(tenantId, webhookUrl) {
  const sessionPath = path.join(SESSIONS_DIR, tenantId);
  await fs.ensureDir(sessionPath);

  // Initialize session state
  const sessionState = {
    qr: null,
    connected: false,
    phoneNumber: null,
    pushName: null,
    webhookUrl: webhookUrl || WEBHOOK_URL,
    reconnectAttempts: 0,
    maxReconnectAttempts: 3,
  };
  sessionStates.set(tenantId, sessionState);

  // Use official useMultiFileAuthState pattern - generates keys automatically
  let { state, saveCreds } = await useMultiFileAuthState(sessionPath);

  // Check if credentials are valid
  const credsPath = path.join(sessionPath, 'creds.json');
  const hasValidCreds = await fs.pathExists(credsPath);

  if (hasValidCreds) {
    try {
      const creds = JSON.parse(await fs.readFile(credsPath, 'utf-8'));
      if (creds.me && creds.me.id) {
        logger.info({ tenantId }, 'Valid credentials found - will try to resume session');
      } else {
        logger.info({ tenantId }, 'Invalid credentials - removing for fresh login');
        await fs.remove(sessionPath);
        await fs.ensureDir(sessionPath);
        // Re-initialize auth state after cleanup
        const result = await useMultiFileAuthState(sessionPath);
        state = result.state;
        saveCreds = result.saveCreds;
      }
    } catch (e) {
      logger.info({ tenantId }, 'Error reading credentials - forcing fresh login');
      await fs.remove(sessionPath);
      await fs.ensureDir(sessionPath);
      const result = await useMultiFileAuthState(sessionPath);
      state = result.state;
      saveCreds = result.saveCreds;
    }
  }

  logger.info({ tenantId, hasMe: !!state.creds?.me }, 'Auth state ready');

  // Create socket with auth
  const sock = makeWASocket({
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger),
    },
    logger: logger,
    browser: Browsers.ubuntu('Inika WhatsApp Gateway'),
    printQRInTerminal: false,
    qrTimeout: 120000,
    connectTimeoutMs: 60000,
  });

  // Store socket
  sockets.set(tenantId, sock);

  // Store socket reference in session state for reconnect logic
  sessionState.socket = sock;

  // Listen to raw WebSocket messages to capture QR before it's lost
  if (sock.ws && sock.ws.on) {
    sock.ws.on('message', (data) => {
      try {
        const msg = data.toString();
        // Look for pair-device message which contains QR refs
        if (msg.includes('pair-device') && msg.includes('ref')) {
          logger.info({ tenantId, msg: msg.substring(0, 200) }, 'Raw pair-device message detected');
        }
      } catch (e) {
        // Ignore parsing errors
      }
    });
  }

  // Listen to creds events to catch QR generation
  sock.ev.on('creds.update', async (creds) => {
    logger.debug({ tenantId, hasMe: !!creds?.me }, 'Credentials updated');
    try {
      await fs.writeJson(path.join(sessionPath, 'creds.json'), creds, { spaces: 2 });
    } catch (e) {
      logger.error({ err: e, tenantId }, 'Failed to save credentials');
    }
  });

  /**
   * Connection update handler
   */
  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr: qrData, phoneNumber, pushName } = update;

    logger.debug({ tenantId, connection, hasQR: !!qrData, qrData }, 'Connection update received');

    // Handle QR code generation
    if (qrData) {
      try {
        const qrImage = await qrcode.toDataURL(qrData);
        sessionState.qr = qrImage;
        logger.info({ tenantId, qrLength: qrImage.length }, 'QR code generated - scan with WhatsApp');
      } catch (e) {
        logger.error({ err: e, tenantId }, 'QR generation error');
      }
    }

    // Handle connection state changes
    switch (connection) {
      case 'connecting':
        logger.info({ tenantId }, 'Connecting to WhatsApp...');
        break;
      case 'open':
        sessionState.connected = true;
        sessionState.qr = null;
        sessionState.phoneNumber = phoneNumber || sock.user?.id?.split('@')[0];
        sessionState.pushName = pushName || sock.user?.name || 'Inika Bot';
        logger.info({ tenantId, phoneNumber: sessionState.phoneNumber, pushName: sessionState.pushName }, 'WhatsApp connected successfully');
        break;
      case 'close':
        const statusCode = lastDisconnect?.error?.output?.statusCode;
        const reason = lastDisconnect?.error?.message;

        logger.warn({ tenantId, statusCode, reason }, 'Connection closed');

        sessionState.connected = false;
        sessionState.reconnectAttempts++;

        // Only reconnect for specific transient errors
        // Don't reconnect for auth failures (401, 405) - user needs to re-scan QR
        const isAuthFailure = statusCode === DisconnectReason.loggedOut || statusCode === 405;
        const isTransientError = statusCode === DisconnectReason.connectionClosed ||
                                statusCode === DisconnectReason.timedOut ||
                                statusCode === undefined;

        if (isAuthFailure) {
          logger.info({ tenantId }, 'Authentication failed - delete session and re-scan QR to reconnect');
          sessionState.qr = null; // Clear any stale QR
        } else if (isTransientError && sessionState.reconnectAttempts < sessionState.maxReconnectAttempts) {
          logger.info({ tenantId, attempt: sessionState.reconnectAttempts }, 'Transient error - retrying...');
          setTimeout(async () => {
            try {
              await connectToWhatsApp(tenantId, sessionState.webhookUrl);
            } catch (error) {
              logger.error({ err: error, tenantId }, 'Reconnection failed');
            }
          }, 3000);
        } else if (sessionState.reconnectAttempts >= sessionState.maxReconnectAttempts) {
          logger.warn({ tenantId }, 'Max reconnection attempts reached - giving up');
        }
        break;
    }
  });

  /**
   * Handle incoming messages
   */
  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    logger.debug({ tenantId, type, count: messages.length }, 'Messages upsert');

    for (const msg of messages) {
      // Skip messages we sent
      if (msg.key.fromMe) continue;

      const remoteJid = msg.key.remoteJid;
      if (!remoteJid || remoteJid === 'status@broadcast') continue;

      // Extract message content
      const messageContent = msg.message;
      if (!messageContent) continue;

      const messageType = getContentType(messageContent);
      const text = messageContent?.conversation ||
                   messageContent?.extendedTextMessage?.text ||
                   '';

      // Extract phone number
      const phone = remoteJid.split('@')[0];

      logger.info({
        tenantId,
        phone,
        messageType,
        hasText: !!text,
      }, 'Incoming message');

      // Build webhook payload
      const webhookPayload = {
        event: 'onMessage',
        session: tenantId,
        data: {
          key: msg.key,
          message: messageContent,
          pushName: msg.pushName || sessionState.pushName,
          messageType,
          text,
        },
      };

      // Send to webhook
      try {
        const fullWebhookUrl = `${sessionState.webhookUrl}${sessionState.webhookUrl.includes('?') ? '&' : '?'}tenant_id=${tenantId}`;
        await axios.post(fullWebhookUrl, webhookPayload, {
          timeout: 10000,
        });
        logger.debug({ phone }, 'Webhook sent successfully');
      } catch (e) {
        logger.error({ err: e, phone, tenantId }, 'Webhook error');
      }
    }
  });

  /**
   * Handle groups updates
   */
  sock.ev.on('groups.update', async (events) => {
    for (const event of events) {
      logger.debug({ tenantId, event }, 'Group update');
    }
  });

  /**
   * Handle chat updates
   */
  sock.ev.on('messages.update', async ({ updates }) => {
    for (const update of updates) {
      if (update.pollUpdates) {
        logger.debug({ tenantId, update }, 'Poll update received');
      }
    }
  });

  /**
   * Handle new chats
   */
  sock.ev.on('chats.upsert', async ({ chats }) => {
    logger.debug({ tenantId, count: chats.length }, 'Chats upsert');
  });

  /**
   * Handle new contacts
   */
  sock.ev.on('contacts.upsert', async ({ contacts }) => {
    logger.debug({ tenantId, count: contacts.length }, 'Contacts upsert');
  });

  // No need to wait - connection updates will be handled via the event listener
  return sessionState;
}

// Start server
const server = createServer(app);
server.listen(PORT, () => {
  logger.info({
    port: PORT,
    sessionsDir: SESSIONS_DIR,
    webhookUrl: WEBHOOK_URL,
  }, 'Inika WhatsApp Gateway started');
});

// Graceful shutdown
const shutdown = async (signal) => {
  logger.info({ signal }, 'Shutting down...');

  // Close all WhatsApp sessions
  for (const [tenantId, sock] of sockets.entries()) {
    try {
      await sock.logout();
      logger.info({ tenantId }, 'Session logged out');
    } catch (e) {
      logger.warn({ err: e, tenantId }, 'Logout error during shutdown');
    }
  }

  // Close HTTP server
  server.close(() => {
    logger.info('Server closed');
    process.exit(0);
  });

  // Force exit after timeout
  setTimeout(() => {
    logger.warn('Forced exit');
    process.exit(1);
  }, 10000);
};

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));