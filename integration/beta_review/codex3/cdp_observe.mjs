// Passive allowlisted CDP observation; no headers, cookies, tokens, HTML or body.
import {appendFileSync} from 'node:fs';
const NativeWebSocket = globalThis.WebSocket;
const file = process.env.C3_CDP_TRACE;
if (!file) throw Error('PRIVATE_CDP_TRACE_REQUIRED');
const begun = performance.now();
const sessionIds = new Map(), requestIds = new Map();
const tag = (map, value) => {
  if (!value) return null;
  if (!map.has(value)) map.set(value, map.size + 1);
  return map.get(value);
};
const pathname = value => {
  try { return new URL(value).pathname; } catch { return 'NON_URL'; }
};
const log = value => appendFileSync(file, JSON.stringify({
  ms: Math.round(performance.now() - begun), ...value,
}) + '\n', {encoding: 'utf8', mode: 0o600});
globalThis.WebSocket = class ObservedWebSocket extends NativeWebSocket {
  constructor(...args) {
    super(...args);
    this.c3Calls = new Map();
    this.addEventListener('message', event => {
      const m = JSON.parse(event.data);
      if (m.id) {
        const saved = this.c3Calls.get(m.id);
        if (saved) {
          this.c3Calls.delete(m.id);
          log({direction:'return', id:m.id, method:saved.method,
            session:saved.session, elapsed_ms:Math.round(performance.now()-saved.time),
            error_code:m.error?.code ?? null});
        }
        return;
      }
      const p = m.params || {};
      const base = {direction:'event', method:m.method, session:tag(sessionIds,m.sessionId)};
      if (m.method === 'Fetch.requestPaused')
        log({...base, request:tag(requestIds,p.requestId), verb:p.request.method,
          path:pathname(p.request.url), resource_type:p.resourceType});
      else if (m.method === 'Network.requestWillBeSent')
        log({...base, verb:p.request.method, path:pathname(p.request.url)});
      else if (m.method === 'Network.responseReceived')
        log({...base, path:pathname(p.response.url), status:p.response.status});
      else if (m.method === 'Network.loadingFailed')
        log({...base, error_text:p.errorText, canceled:!!p.canceled});
      else if (m.method === 'Page.frameNavigated')
        log({...base, path:pathname(p.frame.url)});
      else if (['Page.loadEventFired','Inspector.targetCrashed','Target.targetCrashed'].includes(m.method))
        log(base);
    });
  }
  send(data) {
    const m = JSON.parse(data), p=m.params || {};
    const session = tag(sessionIds,m.sessionId);
    this.c3Calls.set(m.id,{method:m.method,session,time:performance.now()});
    const row={direction:'send', id:m.id, method:m.method, session};
    if (m.method === 'Page.navigate') row.path=pathname(p.url);
    if (m.method.startsWith('Fetch.')) {
      row.request=tag(requestIds,p.requestId);
      if (p.method) row.override_verb=p.method;
      if (p.postData) row.override_body_bytes=Buffer.from(p.postData,'base64').length;
      if (p.headers) row.override_header_names=p.headers.map(h=>h.name);
    }
    log(row);
    return super.send(data);
  }
};
