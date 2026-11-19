// Execute only inside an authorized Vercel Preview Node server function/job.
// Import runProbe from this VRAE artifact; VF owns the integration and deployment.
import { request } from 'node:https';
import { createHash, X509Certificate, createPrivateKey } from 'node:crypto';
import { pathToFileURL } from 'node:url';

const MEDIA = 'application/vnd.vrae.launch+json; profile="vf-vrae-r0.1-vfb.1"';
const API = 'vrae.diagnosis-api.v1';
const ORIGIN = 'https://dong.tail27555e.ts.net';
const TARGET = 'https://vrae-owned-source.tail27555e.ts.net/';
const sha256 = raw => createHash('sha256').update(raw).digest('hex');
function requireThat(ok) { if (!ok) throw new Error('CHECK_REFUSED'); }

export function validateResponse(cfg, headers, status, expected, json) {
  // The current server's Refused path uses frozen VF safe_error media, even
  // when the successful endpoint uses JSON. Do not confuse a 403 with a 503.
  const responseMedia = json && expected !== 403 ? 'application/json' : MEDIA;
  requireThat(status === expected && headers['x-vrae-source-sha'] === cfg.sha &&
    headers['x-vrae-api-version'] === API && headers['content-type'] === responseMedia &&
    /(?:^|,\s*)no-store(?:,|$)/i.test(headers['cache-control'] ?? ''));
}

export function config(env) {
  requireThat(env.VERCEL_ENV === 'preview' && env.VERCEL && env.VERCEL_URL &&
    env.VERCEL_GIT_COMMIT_REF === 'feature/vf-b-offline-g1-adapter');
  requireThat([ORIGIN, ORIGIN + '/', ORIGIN + ':443', ORIGIN + ':443/'].includes(env.VRAE_DIAGNOSIS_BASE_URL));
  const pem = name => (env[name] ?? '').replace(/\\n/g, '\n');
  const cert = pem('VRAE_DIAGNOSIS_CLIENT_CERT_PEM');
  const key = pem('VRAE_DIAGNOSIS_CLIENT_KEY_PEM');
  const ca = pem('VRAE_DIAGNOSIS_CA_PEM');
  const parsed = new X509Certificate(cert);
  requireThat(parsed.checkPrivateKey(createPrivateKey(key)) && Date.parse(parsed.validFrom) <= Date.now() &&
    Date.parse(parsed.validTo) > Date.now());
  new X509Certificate(ca);
  requireThat(/^[a-f0-9]{40}$/.test(env.VRAE_DIAGNOSIS_SOURCE_SHA ?? '') &&
    /^[A-Za-z0-9._~+/-]{16,512}={0,2}$/.test(env.VRAE_DIAGNOSIS_BEARER ?? ''));
  return { cert, key, ca, bearer: env.VRAE_DIAGNOSIS_BEARER, sha: env.VRAE_DIAGNOSIS_SOURCE_SHA,
    fingerprint: sha256(parsed.raw), notBefore: parsed.validFrom, expiresAt: parsed.validTo };
}

export function wire(cfg, path, expected, body, session, json = false, bearer = cfg.bearer) {
  return new Promise((resolve, reject) => {
    const raw = body === undefined ? undefined : JSON.stringify(body);
    const headers = { Accept: json ? 'application/json' : MEDIA, Authorization: 'Bearer ' + bearer };
    if (raw !== undefined) Object.assign(headers, { 'Content-Type': MEDIA, 'Content-Length': Buffer.byteLength(raw) });
    if (session) Object.assign(headers, { Cookie: session.cookie, 'X-CSRF-Token': session.csrf });
    const req = request(ORIGIN, { path, method: raw === undefined ? 'GET' : 'POST', headers,
      ca: cfg.ca, cert: cfg.cert, key: cfg.key, rejectUnauthorized: true, minVersion: 'TLSv1.2',
      agent: false, signal: AbortSignal.timeout(8000) }, res => {
      let size = 0; const chunks = [];
      res.on('data', chunk => { size += chunk.length; if (size > 2_000_000) res.destroy(); else chunks.push(chunk); });
      res.on('error', reject);
      res.on('aborted', () => reject(new Error('RESPONSE_ABORTED')));
      res.on('end', () => {
        try {
          const bytes = Buffer.concat(chunks);
          validateResponse(cfg, res.headers, res.statusCode, expected, json);
          const doc = JSON.parse(bytes.toString('utf8'));
          resolve({ doc, headers: res.headers, evidence: { path, status: res.statusCode,
            response_sha256: sha256(bytes), source_sha: res.headers['x-vrae-source-sha'] } });
        } catch {
          const error = new Error('WIRE_CHECK_REFUSED');
          error.evidence = { path, status: res.statusCode, expected,
            response_sha256: sha256(Buffer.concat(chunks)), passed: false };
          reject(error);
        }
      });
    });
    req.on('error', reject); req.end(raw);
  });
}

export async function runProbe(env = process.env, execute = false, send = wire, confirmConsent) {
  const result = { contract: 'vrae.vf-preview-handoff.v1', state: 'BLOCKED', events: [],
    origin: ORIGIN, target: TARGET, observed_at: new Date().toISOString(),
    deployment: { url: env.VERCEL_URL, id: env.VERCEL_DEPLOYMENT_ID, sha: env.VERCEL_GIT_COMMIT_SHA },
    vercel_environment_asserted: false, real_customer_sources: false };
  try {
    const cfg = config(env);
    result.vercel_environment_asserted = true; // corroborate with deployment logs; env is not provenance
    Object.assign(result, { source_sha: cfg.sha, client_certificate_sha256: cfg.fingerprint,
      certificate_not_before: cfg.notBefore, certificate_expires_at: cfg.expiresAt });
    const call = async (...args) => {
      try { const r = await send(cfg, ...args); result.events.push(r.evidence); return r; }
      catch (error) {
        result.events.push(error.evidence ?? { path: args[0], expected: args[1], passed: false,
          failure: 'TRANSPORT_OR_TLS_FAILURE_NOT_A_SUCCESSFUL_DENIAL' });
        throw error;
      }
    };
    const ready = await call('/health/ready', 200, undefined, undefined, true);
    requireThat(ready.doc.status === 'READY' && ready.doc.source_sha === cfg.sha);
    const spec = await call('/v1/openapi.json', 200, undefined, undefined, true);
    requireThat(spec.doc.paths['/v1/diagnoses'] && spec.doc['x-vrae-target-intake']);
    await call('/health/ready', 403, undefined, undefined, true, 'deliberately-invalid-preview-bearer');
    await call('/v1/audits/aref-' + '0'.repeat(32), 403);
    if (!execute) { result.state = 'TRANSPORT_ONLY_NOT_HANDOFF_READY'; return result; }
    // The explicit approval flag represents the operator's attestation that the
    // invited person accepted the literal CURRENT contract. Never infer consent.
    requireThat(typeof confirmConsent === 'function' &&
      env.VRAE_PREVIEW_ACTUAL_CONSENT === 'CURRENT_INVITED_PERSON_ACCEPTED' &&
      /^[A-Za-z0-9._~-]{16,512}$/.test(env.VRAE_PREVIEW_INVITATION ?? ''));
    const intake = (await call('/v1/target-intake-contract', 200, undefined, undefined, true)).doc;
    const exchange = await call('/v1/invitation-session', 200, { invitation_token: env.VRAE_PREVIEW_INVITATION });
    const cookies = exchange.headers['set-cookie']?.filter(c => c.startsWith('__Host-vrae-targets='));
    requireThat(cookies?.length === 1 && exchange.headers['x-csrf-token']);
    const session = { cookie: cookies[0].split(';')[0], csrf: exchange.headers['x-csrf-token'] };
    const application = await call('/v1/target-applications', 201, { url: TARGET, paths: ['/products', '/contact'],
      consent: { version: intake.consent_version, read_only_authorized: true, model_data_notice: true } }, session);
    requireThat(application.doc.proof.type === 'OPERATOR_OWNED_PUBLIC_ORIGIN');
    await call('/v1/target-applications/authorize', 201, { application_token: application.doc.application_token }, session);
    // Actual person reconfirms consent after authorization, so accepted_at is current.
    // VF must collect this through its UI; automated acceptance is not authority.
    const acceptedAt = await confirmConsent({ consentVersion: intake.consent_version,
      consentText: intake.consent_text, target: TARGET });
    requireThat(Number.isFinite(Date.parse(acceptedAt)) && Date.parse(acceptedAt) <= Date.now() &&
      Date.parse(acceptedAt) >= Date.now() - 30 * 60 * 1000);
    const body = { url: TARGET, idempotency_key: env.VRAE_PREVIEW_IDEMPOTENCY_KEY,
      accepted_at: acceptedAt, consent_version: intake.consent_version, language: 'zh' };
    requireThat(/^[A-Za-z0-9_.-]{8,128}$/.test(body.idempotency_key ?? ''));
    const accepted = (await call('/v1/diagnoses', 202, body, session)).doc;
    requireThat(/^aref-[a-f0-9]{32}$/.test(accepted.audit_ref));
    const repeated = (await call('/v1/diagnoses', 202, body, session)).doc;
    requireThat(repeated.audit_ref === accepted.audit_ref && repeated.run_id === accepted.run_id);
    await call('/v1/diagnoses', 409, { ...body, language: 'en' }, session);
    for (let n = 0; n < 30; n++) {
      const status = (await call('/v1/audits/' + accepted.audit_ref, 200, undefined, session)).doc;
      if (status.task.status === 'DRAFT_READY') {
        requireThat(status.publication.state === 'UNPUBLISHED');
        await call('/v1/audits/' + accepted.audit_ref + '/report', 403, undefined, session);
        result.state = 'DRAFT_READY_PENDING_REVOCATION_AND_CROSS_SUBJECT_EVIDENCE'; return result;
      }
      requireThat(status.task.status !== 'FAILED');
      await new Promise(resolve => setTimeout(resolve, 5000));
    }
    throw new Error('WORKER_TIMEOUT');
  } catch {
    result.state = 'BLOCKED:PRIVATE_OPERATOR_OR_PROTOCOL_CHECK_REQUIRED';
    return result;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const result = await runProbe(process.env, process.argv.includes('--execute'));
  process.stdout.write(JSON.stringify(result) + '\n');
  if (result.state.startsWith('BLOCKED')) process.exitCode = 1;
}
