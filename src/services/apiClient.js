import { hashText } from '../core/utils.js';

const parseEndpoint = (endpoint = '') => {
  const [methodLike, ...pathParts] = endpoint.trim().split(' ');
  if (!pathParts.length) {
    return { method: 'POST', path: methodLike || '/api/unknown' };
  }
  return { method: methodLike.toUpperCase(), path: pathParts.join(' ').trim() };
};

const maskToken = (token = '') => {
  if (!token || token === 'runtime-anon') return token || 'runtime-anon';
  if (token.length < 8) return 'runtime-***';
  return `${token.slice(0, 10)}***`;
};

export const createApiClient = ({
  mode = 'mock',
  provider = 'openai',
  model = '',
  getApiKey = () => '',
  onLog = () => {},
  onRunningChange = () => {},
}) => {
  const createRuntimeToken = () => {
    const key = String(getApiKey() || '').trim();
    if (!key) return 'runtime-anon';
    return `runtime-${hashText(`${key}:${Date.now()}`).slice(0, 12)}`;
  };

  const call = async (endpoint, payload = {}) => {
    const runtimeToken = payload.runtimeToken || createRuntimeToken();
    const safePayload = { ...payload, runtimeToken: maskToken(runtimeToken) };

    onRunningChange({ running: true, endpoint });

    try {
      if (mode === 'real') {
        const { method, path } = parseEndpoint(endpoint);
        const key = String(getApiKey() || '').trim();
        const response = await fetch(path, {
          method,
          headers: {
            'Content-Type': 'application/json',
            ...(key ? { Authorization: `Bearer ${key}` } : {}),
            'X-LLM-Provider': provider,
            'X-LLM-Model': model,
          },
          body: JSON.stringify({ ...payload, runtimeToken }),
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json().catch(() => ({ ok: true }));
        onLog({ endpoint, payload: safePayload, at: new Date().toISOString(), mode: 'real' });
        return { ok: true, data };
      }

      await new Promise((resolve) => setTimeout(resolve, 240 + Math.random() * 280));
      onLog({ endpoint, payload: safePayload, at: new Date().toISOString(), mode: 'mock' });
      return { ok: true, endpoint, mode: 'mock' };
    } catch (error) {
      onLog({
        endpoint,
        payload: safePayload,
        at: new Date().toISOString(),
        mode,
        error: String(error?.message || error),
      });
      return { ok: false, error: String(error?.message || error) };
    } finally {
      onRunningChange({ running: false, endpoint: '' });
    }
  };

  return {
    createRuntimeToken,
    call,
  };
};
