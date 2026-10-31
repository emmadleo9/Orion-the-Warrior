'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const proxyaddr = require('proxy-addr');

test('IPv4 proxy trust requires a subnet covering the mapped marker', () => {
  for (const peer of ['203.0.113.9', '::ffff:203.0.113.9']) {
    assert.equal(proxyaddr.compile(['::ffff:10.0.0.0/8'])(peer), false);
    assert.equal(proxyaddr.compile(['::/1', '192.0.2.0/24'])(peer), false);
  }
  const mapped = proxyaddr.compile(['::ffff:10.0.0.0/104']);
  assert.equal(mapped('10.0.0.1'), true);
  assert.equal(mapped('203.0.113.9'), false);
  assert.equal(proxyaddr.compile(['10.0.0.0/8'])('10.0.0.1'), true);
});
