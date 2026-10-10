export const REPLY_PREFIX = "[MohaMind]\n";

export function normalizeJid(value) {
  if (typeof value !== "string") return "";
  const match = value.match(/^(\d+)(?::\d+)?@(s\.whatsapp\.net|lid)$/);
  return match ? `${match[1]}@${match[2]}` : "";
}

export function selfMessage(message, ownJids, startedAt) {
  const key = message?.key;
  if (!key?.fromMe || !key.id || !normalizeJid(key.remoteJid)) return null;
  const remote = normalizeJid(key.remoteJid);
  const alternate = normalizeJid(key.remoteJidAlt);
  if (!ownJids.has(remote) && !(alternate && ownJids.has(alternate))) return null;
  const timestamp = Number(message.messageTimestamp);
  if (!Number.isFinite(timestamp) || timestamp < startedAt - 5) return null;
  let content = message.message;
  if (content?.ephemeralMessage) content = content.ephemeralMessage.message;
  const text = content?.conversation ?? content?.extendedTextMessage?.text;
  if (typeof text !== "string" || !text.trim() || text.startsWith(REPLY_PREFIX)) return null;
  if (text.length > 8000) return { type: "too_long" };
  return { type: "message", id: key.id, text, from_me: true, is_self: true };
}
