import test from 'node:test';
import assert from 'node:assert/strict';
import { config, runProbe, validateResponse } from './vercel_probe.mjs';

test('local invocation cannot claim Vercel evidence or send requests', async () => {
  let called = false;
  const result = await runProbe({}, true, async () => { called = true; });
  assert.equal(called, false);
  assert.equal(result.vercel_environment_asserted, false);
  assert.match(result.state, /^BLOCKED:/);
});

test('production and other branches fail closed before credential use', () => {
  for (const env of [{ VERCEL_ENV: 'production' }, { VERCEL_ENV: 'preview', VERCEL: '1',
    VERCEL_URL: 'synthetic.vercel.app', VERCEL_GIT_COMMIT_REF: 'main' }]) {
    assert.throws(() => config(env));
  }
});

test('refused config never echoes secret values', async () => {
  const result = await runProbe({ VRAE_DIAGNOSIS_BEARER: 'SYNTHETIC_SECRET_SENTINEL' });
  assert.equal(JSON.stringify(result).includes('SYNTHETIC_SECRET_SENTINEL'), false);
});

const headers = { 'x-vrae-source-sha': 'a'.repeat(40), 'x-vrae-api-version': 'vrae.diagnosis-api.v1',
  'cache-control': 'no-store', 'content-type': 'application/json' };
test('stale SHA, missing no-store, and wrong API version cannot pass a 200', () => {
  const cfg = { sha: 'a'.repeat(40) };
  validateResponse(cfg, headers, 200, 200, true);
  for (const patch of [{ 'x-vrae-source-sha': 'b'.repeat(40) }, { 'cache-control': 'public' },
    { 'x-vrae-api-version': 'old' }]) {
    assert.throws(() => validateResponse(cfg, { ...headers, ...patch }, 200, 200, true));
  }
});
test('health bearer denial uses actual frozen error media; other failures do not count as 403', () => {
  const cfg = { sha: 'a'.repeat(40) };
  const denied = { ...headers, 'content-type': 'application/vnd.vrae.launch+json; profile="vf-vrae-r0.1-vfb.1"' };
  validateResponse(cfg, denied, 403, 403, true);
  assert.throws(() => validateResponse(cfg, denied, 503, 403, true));
  assert.throws(() => validateResponse(cfg, headers, 403, 403, true));
});
