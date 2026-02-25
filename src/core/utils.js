export const makeId = (prefix = 'id') =>
  `${prefix}-${Date.now().toString(36)}-${Math.floor(Math.random() * 1000000)}`;

export const hashText = (text = '') =>
  Array.from(text)
    .reduce((acc, ch) => ((acc << 5) - acc + ch.charCodeAt(0)) >>> 0, 0)
    .toString(16);

export const detectLanguage = (text = '') => {
  if (/[\uac00-\ud7a3]/.test(text)) return 'ko';
  if (/[a-zA-Z]/.test(text)) return 'en';
  return 'und';
};

export const stripHtml = (html = '') =>
  html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

export const splitSentences = (text = '') => {
  const normalized = text.replace(/\r/g, ' ').replace(/\n+/g, ' ').trim();
  if (!normalized) return [];

  const first = normalized
    .replace(/([.!?])\s+/g, '$1|')
    .split('|')
    .map((s) => s.trim())
    .filter(Boolean);

  if (first.length > 1) return first;

  return normalized
    .split(/[;,]/)
    .map((s) => s.trim())
    .filter(Boolean);
};

export const extractCitation = (text = '') => {
  const m = text.match(/\([^\)]+\)|\[[^\]]+\]|10\.\d{4,9}\/[A-Za-z0-9._-]+/g);
  return m ? m.join('; ') : '';
};

export const inferMetadata = (text = '') => {
  const lines = text
    .split(/\n+/)
    .map((l) => l.trim())
    .filter(Boolean);

  const year = text.match(/\b(19|20)\d{2}\b/)?.[0] || '';
  const doi = text.match(/10\.\d{4,9}\/[A-Za-z0-9._-]+/)?.[0] || '';
  const journal = lines.find((l) => /journal|conference|proceedings|review/i.test(l)) || '';
  const authors = lines.find((l) => l.includes(',') && l.length < 140 && !l.includes('://')) || '';

  return {
    title: lines[0] || 'Untitled',
    authors,
    year,
    journal,
    doi,
  };
};

export const truncate = (value = '', len = 120) =>
  value.length > len ? `${value.slice(0, len - 1)}...` : value;

export const toLocalTime = (iso) =>
  new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });

export const readFileAsText = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(reader.error || new Error('file read failed'));
    reader.readAsText(file, 'utf-8');
  });

export const extractTextFromUpload = async (file) => {
  if (!file) return { text: '', mode: 'none' };

  const name = file.name || '';
  const textLike = /\.(txt|md|csv|json)$/i.test(name) || file.type.startsWith('text/');
  if (textLike) {
    const text = await readFileAsText(file);
    return { text, mode: 'text' };
  }

  if (/\.(pdf|docx|doc)$/i.test(name)) {
    return {
      text: `[Binary upload placeholder] ${name}`,
      mode: 'binary',
    };
  }

  try {
    const text = await readFileAsText(file);
    return { text, mode: 'fallback' };
  } catch (_error) {
    return { text: `[Unsupported upload placeholder] ${name}`, mode: 'unsupported' };
  }
};

export const resetSentenceOrder = (arr) =>
  [...arr]
    .sort((a, b) => a.index - b.index)
    .map((s, idx) => ({
      ...s,
      index: idx,
      paragraphId: `p-${Math.floor(idx / 8)}`,
    }));
