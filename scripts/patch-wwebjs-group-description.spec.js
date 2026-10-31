'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');

const {
  applyGroupDescriptionFix,
  isApplied,
  POSITIONAL_CALL,
  OPTIONS_CALL,
} = require('./patch-wwebjs-group-description.js');

function makeDependency(source) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'openwa-group-description-'));
  const groupChat = path.join(root, 'src', 'structures', 'GroupChat.js');
  fs.mkdirSync(path.dirname(groupChat), { recursive: true });
  fs.writeFileSync(groupChat, source);
  return { root, groupChat };
}

test('patches the description job call to the options object', () => {
  const { root, groupChat } = makeDependency(`before\n${POSITIONAL_CALL}\nafter\n`);

  const result = applyGroupDescriptionFix(root);

  assert.deepEqual(result, { skipped: false, note: 'group description job called with an options object' });
  assert.equal(fs.readFileSync(groupChat, 'utf8'), `before\n${OPTIONS_CALL}\nafter\n`);
});

test('reports the patch as applied only once the transform has run', () => {
  const { root } = makeDependency(`before\n${POSITIONAL_CALL}\nafter\n`);

  assert.equal(isApplied(root), false);

  applyGroupDescriptionFix(root);

  assert.equal(isApplied(root), true);
});

test('sends an empty description as null, which clears rather than writing an empty body', () => {
  const { root, groupChat } = makeDependency(`before\n${POSITIONAL_CALL}\nafter\n`);

  applyGroupDescriptionFix(root);

  assert.match(fs.readFileSync(groupChat, 'utf8'), /desc: description === '' \? null : description/);
});

test('is idempotent when the options object is already present', () => {
  const { root, groupChat } = makeDependency(`before\n${OPTIONS_CALL}\nafter\n`);
  const original = fs.readFileSync(groupChat, 'utf8');

  assert.deepEqual(applyGroupDescriptionFix(root), {
    skipped: true,
    reason: 'installed whatsapp-web.js already calls the description job with an options object',
  });
  assert.equal(fs.readFileSync(groupChat, 'utf8'), original);
});

test('rejects an unknown dependency shape without changing it', () => {
  const { root, groupChat } = makeDependency('module.exports = class GroupChat {};\n');
  const original = fs.readFileSync(groupChat, 'utf8');

  assert.throws(() => applyGroupDescriptionFix(root), /unsupported GroupChat\.js shape/);
  assert.equal(fs.readFileSync(groupChat, 'utf8'), original);
});

test('rejects an ambiguous dependency shape without changing it', () => {
  const { root, groupChat } = makeDependency(`${POSITIONAL_CALL}\n${OPTIONS_CALL}\n`);
  const original = fs.readFileSync(groupChat, 'utf8');

  assert.throws(() => applyGroupDescriptionFix(root), /unsupported GroupChat\.js shape/);
  assert.equal(fs.readFileSync(groupChat, 'utf8'), original);
});

test('reports a missing dependency tree', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'openwa-group-description-empty-'));

  assert.throws(() => applyGroupDescriptionFix(root), /GroupChat\.js not found/);
});

test('matches the call shape the installed whatsapp-web.js ships', () => {
  const installed = path.join(__dirname, '..', 'node_modules', 'whatsapp-web.js', 'src', 'structures', 'GroupChat.js');
  const source = fs.readFileSync(installed, 'utf8');

  assert.ok(
    source.includes(POSITIONAL_CALL) || source.includes(OPTIONS_CALL),
    'installed GroupChat.js matches neither the upstream call nor the patched one',
  );
});
