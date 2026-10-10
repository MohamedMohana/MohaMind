import { mkdir } from "node:fs/promises";
import { createInterface } from "node:readline";
import makeWASocket, { DisconnectReason, useMultiFileAuthState } from "baileys";
import pino from "pino";
import qrcode from "qrcode-terminal";
import { normalizeJid, REPLY_PREFIX, selfMessage } from "./policy.mjs";

process.umask(0o077);
const sessionDir = process.argv[2];
const pairOnly = process.argv.includes("--pair");
if (!sessionDir) process.exit(2);
const emit = (event) => process.stdout.write(`${JSON.stringify(event)}\n`);
const logger = pino({ level: "silent" });
const startedAt = Math.floor(Date.now() / 1000);
const seen = new Set();
let socket;
let online = false;
let stopping = false;
let retries = 0;
let retryTimer;
let ownJids = new Set();
let ownJid = "";
let savePending = Promise.resolve();

await mkdir(sessionDir, { recursive: true, mode: 0o700 });
const { state, saveCreds } = await useMultiFileAuthState(sessionDir);

async function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  clearTimeout(retryTimer);
  await savePending;
  socket?.end(undefined);
  process.exit(code);
}

async function connect() {
  if (stopping) return;
  const current = makeWASocket({
    auth: state,
    logger,
    syncFullHistory: false,
    shouldSyncHistoryMessage: () => false,
    markOnlineOnConnect: false,
    shouldIgnoreJid: (jid) => !normalizeJid(jid),
  });
  socket = current;
  current.ev.on("creds.update", () => {
    savePending = savePending.then(saveCreds).catch(() => {
      emit({ type: "fatal", reason: "Could not save WhatsApp session credentials." });
      void stop(1);
    });
  });
  current.ev.on("connection.update", ({ connection, lastDisconnect, qr }) => {
    if (current !== socket || stopping) return;
    if (qr) {
      if (!pairOnly) {
        emit({ type: "fatal", reason: "WhatsApp is not linked. Run: uv run mohamind whatsapp setup" });
        void stop(1);
        return;
      }
      qrcode.generate(qr, { small: true }, (terminal) => emit({ type: "qr", terminal }));
    }
    if (connection === "open") {
      online = true;
      retries = 0;
      ownJid = normalizeJid(current.user?.id || state.creds.me?.id);
      ownJids = new Set([ownJid, current.user?.lid, state.creds.me?.lid].map(normalizeJid).filter(Boolean));
      if (!ownJid) {
        emit({ type: "fatal", reason: "Could not identify the linked account." });
        void stop(1);
        return;
      }
      emit({ type: "connected", account: ownJid });
      if (pairOnly) void stop();
    }
    if (connection === "close") {
      online = false;
      emit({ type: "disconnected" });
      const code = lastDisconnect?.error?.output?.statusCode;
      if (code === DisconnectReason.loggedOut || code === DisconnectReason.connectionReplaced || retries >= 8) {
        emit({ type: "fatal", reason: "WhatsApp disconnected. Check Linked Devices and run whatsapp setup if needed." });
        void stop(1);
      } else {
        retryTimer = setTimeout(() => void connect().catch(fail), Math.min(1000 * 2 ** retries++, 30000));
      }
    }
  });
  current.ev.on("messages.upsert", ({ type, messages }) => {
    if (pairOnly || !online || type !== "notify" || current !== socket) return;
    for (const message of messages) {
      const event = selfMessage(message, ownJids, startedAt);
      if (!event || seen.has(message.key.id)) continue;
      seen.add(message.key.id);
      if (seen.size > 2000) seen.delete(seen.values().next().value);
      emit(event);
    }
  });
}

const input = createInterface({ input: process.stdin });
input.on("line", async (line) => {
  let command;
  try {
    command = JSON.parse(line);
    if (command.type === "stop") return void stop();
    if (command.type !== "send" || typeof command.request_id !== "string") return;
    if (pairOnly || !online || typeof command.text !== "string" || command.text.length > 4000) {
      throw new Error("invalid send");
    }
    await socket.sendMessage(ownJid, { text: REPLY_PREFIX + command.text });
    emit({ type: "sent", request_id: command.request_id });
  } catch {
    if (typeof command?.request_id === "string") {
      emit({ type: "send_error", request_id: command.request_id });
    }
  }
});
input.on("close", () => void stop());
process.on("SIGTERM", () => void stop());
process.on("SIGINT", () => void stop());
function fail() {
  emit({ type: "fatal", reason: "WhatsApp bridge failed. Check Node.js and the saved session, then retry." });
  void stop(1);
}
process.on("unhandledRejection", fail);
await connect().catch(fail);
