export const API_PROVIDERS = ['openai', 'claude', 'gemini', 'custom'];
export const CATEGORIES = ['core-concept', 'methodology', 'result', 'limitation', 'citable-claim'];
export const METHOD_TEMPLATES = ['qualitative', 'quantitative', 'mixed', 'concept-analysis'];

export const NODE_IDS = {
  REF: 'n-ref-input',
  RAW: 'n-raw-translate',
  NORM: 'n-sentence-normalize',
  EXTRACT: 'n-sentence-extract',
  THEORY: 'n-theory-builder',
  QUESTION: 'n-rq-generator',
  METHOD: 'n-methodology',
};

export const NODE_TEMPLATES = [
  {
    type: 'reference',
    icon: 'Database',
    label: 'Reference Input Node',
    desc: 'Upload/URL + metadata extraction',
  },
  {
    type: 'translate',
    icon: 'Cpu',
    label: 'Raw Translate Node',
    desc: 'Original language to work language',
  },
  {
    type: 'normalize',
    icon: 'Settings',
    label: 'Sentence Normalization Node',
    desc: 'Sentence split/alignment/cleanup',
  },
  {
    type: 'extract',
    icon: 'BoxSelect',
    label: 'Sentence Extract & Highlight Node',
    desc: 'Highlight + extract + edit artifacts',
  },
  {
    type: 'theory',
    icon: 'BrainCircuit',
    label: 'Theoretical Background Builder Node',
    desc: 'Category tree + evidence snapshot',
  },
  {
    type: 'question',
    icon: 'Search',
    label: 'Research Question Generator Node',
    desc: 'Auto/manual/review tabs',
  },
  {
    type: 'methodology',
    icon: 'GitBranch',
    label: 'Methodology Node',
    desc: 'Locked until approved evidence path',
  },
];

export const INITIAL_NODES = [
  {
    id: NODE_IDS.REF,
    x: 40,
    y: 200,
    icon: 'Database',
    label: 'Reference Input Node',
    desc: 'Upload/URL + metadata extraction',
    type: 'reference',
    status: 'ready',
  },
  {
    id: NODE_IDS.RAW,
    x: 350,
    y: 200,
    icon: 'Cpu',
    label: 'Raw Translate Node',
    desc: 'Original language to work language',
    type: 'translate',
    status: 'idle',
  },
  {
    id: NODE_IDS.NORM,
    x: 660,
    y: 200,
    icon: 'Settings',
    label: 'Sentence Normalization Node',
    desc: 'Sentence split/alignment/cleanup',
    type: 'normalize',
    status: 'idle',
  },
  {
    id: NODE_IDS.EXTRACT,
    x: 970,
    y: 200,
    icon: 'BoxSelect',
    label: 'Sentence Extract & Highlight Node',
    desc: 'Highlight + extract + edit artifacts',
    type: 'extract',
    status: 'idle',
  },
  {
    id: NODE_IDS.THEORY,
    x: 1280,
    y: 200,
    icon: 'BrainCircuit',
    label: 'Theoretical Background Builder Node',
    desc: 'Category tree + evidence snapshot',
    type: 'theory',
    status: 'idle',
  },
  {
    id: NODE_IDS.QUESTION,
    x: 1590,
    y: 200,
    icon: 'Search',
    label: 'Research Question Generator Node',
    desc: 'Auto/manual/review tabs',
    type: 'question',
    status: 'idle',
  },
  {
    id: NODE_IDS.METHOD,
    x: 1900,
    y: 200,
    icon: 'GitBranch',
    label: 'Methodology Node',
    desc: 'Locked until approved evidence path',
    type: 'methodology',
    status: 'idle',
  },
];

export const INITIAL_EDGES = [
  { id: 'e1', from: NODE_IDS.REF, to: NODE_IDS.RAW, label: 'rawText', mode: 'horizontal' },
  { id: 'e2', from: NODE_IDS.RAW, to: NODE_IDS.NORM, label: 'translatedText', mode: 'horizontal' },
  { id: 'e3', from: NODE_IDS.NORM, to: NODE_IDS.EXTRACT, label: 'sentenceUnits', mode: 'horizontal' },
  { id: 'e4', from: NODE_IDS.EXTRACT, to: NODE_IDS.THEORY, label: 'sentenceArtifacts', mode: 'horizontal' },
  { id: 'e5', from: NODE_IDS.THEORY, to: NODE_IDS.QUESTION, label: 'theorySupport', mode: 'horizontal' },
  { id: 'e6', from: NODE_IDS.QUESTION, to: NODE_IDS.METHOD, label: 'approvedRQ', mode: 'horizontal' },
];
