import assert from "node:assert/strict";
import test from "node:test";
import { normalizeJid, REPLY_PREFIX, selfMessage } from "./policy.mjs";

const owner = "15550000001@s.whatsapp.net";
const aliases = new Set([owner, "12345@lid"]);
function message(overrides = {}) {
  return {
    key: { id: "example", fromMe: true, remoteJid: owner },
    messageTimestamp: 100,
    message: { conversation: "Remember this fictional task" },
    ...overrides,
  };
}

test("accepts only the linked account's self-chat", () => {
  assert.equal(selfMessage(message(), aliases, 100).text, "Remember this fictional task");
  for (const remoteJid of ["15550000002@s.whatsapp.net", "123@g.us", "status@broadcast", "123@newsletter"]) {
    assert.equal(selfMessage(message({ key: { id: "id", fromMe: true, remoteJid } }), aliases, 100), null);
  }
  assert.equal(selfMessage(message({ key: { id: "id", fromMe: false, remoteJid: owner } }), aliases, 100), null);
});

test("handles device and LID aliases", () => {
  assert.equal(normalizeJid("15550000001:9@s.whatsapp.net"), owner);
  for (const remoteJid of ["15550000001:9@s.whatsapp.net", "12345@lid"]) {
    assert.ok(selfMessage(message({ key: { id: "id", fromMe: true, remoteJid } }), aliases, 100));
  }
  assert.ok(selfMessage(message({ key: {
    id: "id", fromMe: true, remoteJid: "987@lid", remoteJidAlt: owner,
  } }), aliases, 100));
});

test("ignores old messages, media, edits and bot echoes", () => {
  assert.equal(selfMessage(message({ messageTimestamp: 10 }), aliases, 100), null);
  assert.equal(selfMessage(message({ messageTimestamp: undefined }), aliases, 100), null);
  for (const content of [
    { conversation: REPLY_PREFIX + "reply" },
    { imageMessage: { caption: "private picture" } },
    { protocolMessage: { editedMessage: { conversation: "edit" } } },
  ]) {
    assert.equal(selfMessage(message({ message: content }), aliases, 100), null);
  }
});

test("bounds input and accepts Arabic extended text", () => {
  assert.equal(selfMessage(message({ message: { conversation: "x".repeat(8001) } }), aliases, 100).type, "too_long");
  assert.equal(selfMessage(message({ message: { extendedTextMessage: { text: "مرحبا" } } }), aliases, 100).text, "مرحبا");
});
