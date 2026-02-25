import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  ArrowLeft,
  BrainCircuit,
  BoxSelect,
  CheckCircle2,
  Cpu,
  Database,
  ExternalLink,
  GitBranch,
  Layers,
  Maximize2,
  Network,
  Play,
  Search,
  Settings,
  Terminal,
  X,
} from 'lucide-react';
import {
  API_PROVIDERS,
  CATEGORIES,
  INITIAL_EDGES,
  INITIAL_NODES,
  METHOD_TEMPLATES,
  NODE_IDS,
  NODE_TEMPLATES,
} from './src/core/pipeline.js';
import {
  makeId,
  resetSentenceOrder,
  toLocalTime,
  truncate,
} from './src/core/utils.js';
import { createApiClient } from './src/services/apiClient.js';
import {
  createArtifactIndex,
  createInitialMethodologyContext,
  createInitialResearchQuestionDraft,
  createLocksState,
  computePipelineStatus,
} from './src/state/paperStore.js';
import {
  buildAutoQuestionsExecutor,
  buildMethodologyExecutor,
  buildTheoryBackgroundExecutor,
  runExtractExecutor,
  runRawTranslateExecutor,
  runReferenceInputExecutor,
  runSentenceNormalizationExecutor,
} from './src/runtime/nodeExecutors.js';

const ICON_MAP = {
  Database,
  Cpu,
  Settings,
  BoxSelect,
  BrainCircuit,
  Search,
  GitBranch,
};

export default function PaperFlow() {
  const [nodes, setNodes] = useState(INITIAL_NODES);
  const [edges, setEdges] = useState(INITIAL_EDGES);
  const [selectedNodeId, setSelectedNodeId] = useState(NODE_IDS.REF);
  const [viewMode, setViewMode] = useState('canvas');
  const [activeToolNodeId, setActiveToolNodeId] = useState(null);
  const [showPanel, setShowPanel] = useState(true);
  const [workflowBuilder, setWorkflowBuilder] = useState({
    templateType: NODE_TEMPLATES[0].type,
    placement: 'parallel',
    fromId: NODE_IDS.REF,
    toId: NODE_IDS.RAW,
    edgeMode: 'horizontal',
    edgeLabel: '',
  });

  const [isDragging, setIsDragging] = useState(false);
  const [dragNodeId, setDragNodeId] = useState(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  const [running, setRunning] = useState(false);
  const [runningEndpoint, setRunningEndpoint] = useState('');
  const [nodeExecutionState, setNodeExecutionState] = useState({});
  const [toast, setToast] = useState(null);
  const toastTimerRef = useRef(null);

  const [apiConfig, setApiConfig] = useState({
    projectId: 'project-demo',
    mode: 'mock',
    provider: 'openai',
    model: 'gpt-4o-mini',
    targetLanguage: 'en',
    apiKey: '',
  });
  const [apiLog, setApiLog] = useState([]);

  const [referenceForm, setReferenceForm] = useState({
    sourceType: 'upload',
    sourceUrl: '',
    file: null,
    manualText: '',
    title: '',
    authors: '',
    year: '',
    journal: '',
    doi: '',
  });

  const [referenceDocument, setReferenceDocument] = useState(null);
  const [translatedText, setTranslatedText] = useState('');
  const [sentenceUnits, setSentenceUnits] = useState([]);
  const [sentenceArtifacts, setSentenceArtifacts] = useState([]);
  const [selectedSentenceIds, setSelectedSentenceIds] = useState([]);
  const [sentenceViewMode, setSentenceViewMode] = useState('translated');
  const [highlightColor, setHighlightColor] = useState('amber');
  const [categoryBucket, setCategoryBucket] = useState(CATEGORIES[0]);

  const [theoryBackground, setTheoryBackground] = useState(null);

  const [rqTab, setRqTab] = useState('auto');
  const [manualQuestionInput, setManualQuestionInput] = useState('');
  const [researchQuestionDraft, setResearchQuestionDraft] = useState(
    createInitialResearchQuestionDraft(NODE_IDS.QUESTION),
  );

  const [methodologyContext, setMethodologyContext] = useState(
    createInitialMethodologyContext(NODE_IDS.METHOD, METHOD_TEMPLATES[0]),
  );

  const showToast = useCallback((message) => {
    setToast(message);
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setToast(null), 2800);
  }, []);

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    };
  }, []);

  const apiClient = useMemo(
    () =>
      createApiClient({
        mode: apiConfig.mode,
        provider: apiConfig.provider,
        model: apiConfig.model,
        getApiKey: () => apiConfig.apiKey,
        onLog: (log) => {
          setApiLog((prev) => [{ id: makeId('log'), ...log }, ...prev].slice(0, 16));
        },
        onRunningChange: ({ running: isRunning, endpoint }) => {
          setRunning(isRunning);
          setRunningEndpoint(endpoint || '');
        },
      }),
    [apiConfig.mode, apiConfig.provider, apiConfig.model, apiConfig.apiKey],
  );
  const createRuntimeToken = apiClient.createRuntimeToken;
  const apiCall = apiClient.call;
  const markNodeExecution = useCallback((nodeId, ok, message) => {
    setNodeExecutionState((prev) => ({
      ...prev,
      [nodeId]: {
        ok,
        message,
        at: new Date().toISOString(),
      },
    }));
  }, []);

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) || null;
  const activeToolNode = nodes.find((n) => n.id === activeToolNodeId) || null;
  const selectedNodeType = selectedNode?.type || '';
  const templateByType = useMemo(
    () => Object.fromEntries(NODE_TEMPLATES.map((template) => [template.type, template])),
    [],
  );
  const pipelineNodeIdSet = useMemo(() => new Set(Object.values(NODE_IDS)), []);

  const artifactBySentence = useMemo(() => createArtifactIndex(sentenceArtifacts), [sentenceArtifacts]);

  const status = useMemo(
    () =>
      computePipelineStatus({
        nodeIds: NODE_IDS,
        referenceDocument,
        translatedText,
        sentenceUnits,
        sentenceArtifacts,
        theoryBackground,
        researchQuestionDraft,
        methodologyContext,
      }),
    [
      referenceDocument,
      translatedText,
      sentenceUnits,
      sentenceArtifacts,
      theoryBackground,
      researchQuestionDraft,
      methodologyContext,
    ],
  );
  const evidenceCount = status.counters.evidenceCount;
  const categoryArtifactCount = status.counters.categoryArtifactCount;
  const approvedCount = status.counters.approvedCount;
  const locks = useMemo(
    () =>
      createLocksState({
        readyMethod: status.readyMethod,
        approvedCount,
        evidenceCount,
        categoryArtifactCount,
      }),
    [status.readyMethod, approvedCount, evidenceCount, categoryArtifactCount],
  );

  const isCompleted = (id) =>
    pipelineNodeIdSet.has(id) ? Boolean(status.completed[id]) : Boolean(nodeExecutionState[id]?.ok);
  const isReady = (id) => (pipelineNodeIdSet.has(id) ? Boolean(status.ready[id]) : true);
  const getStatusLabel = (id) => (isCompleted(id) ? 'completed' : isReady(id) ? 'ready' : 'blocked');

  useEffect(() => {
    setNodes((prev) =>
      prev.map((node) => ({
        ...node,
        status: isCompleted(node.id) ? 'completed' : isReady(node.id) ? 'ready' : 'idle',
      })),
    );
  }, [status]);

  useEffect(() => {
    if (approvedCount > 0 && selectedNodeId !== NODE_IDS.METHOD) {
      setSelectedNodeId(NODE_IDS.METHOD);
      showToast('Approved research question fixed. Methodology node unlocked flow started.');
    }
  }, [approvedCount]);

  useEffect(() => {
    if (!nodes.length) return;
    setWorkflowBuilder((prev) => ({
      ...prev,
      fromId: nodes.some((node) => node.id === prev.fromId) ? prev.fromId : nodes[0].id,
      toId: nodes.some((node) => node.id === prev.toId) ? prev.toId : nodes[Math.min(1, nodes.length - 1)].id,
    }));
  }, [nodes]);

  const handleMouseDown = (event, nodeId) => {
    event.stopPropagation();
    const node = nodes.find((n) => n.id === nodeId);
    if (!node) return;
    setSelectedNodeId(nodeId);
    setDragNodeId(nodeId);
    setIsDragging(true);
    setDragOffset({ x: event.clientX - node.x, y: event.clientY - node.y });
  };

  const handleMouseMove = useCallback(
    (event) => {
      if (!isDragging || !dragNodeId) return;
      setNodes((prev) =>
        prev.map((node) =>
          node.id === dragNodeId
            ? { ...node, x: event.clientX - dragOffset.x, y: event.clientY - dragOffset.y }
            : node,
        ),
      );
    },
    [isDragging, dragNodeId, dragOffset],
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
    setDragNodeId(null);
  }, []);

  useEffect(() => {
    if (!isDragging) return undefined;
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, handleMouseMove, handleMouseUp]);

  const openToolView = (node) => {
    if (!node) return;
    setSelectedNodeId(node.id);
    setActiveToolNodeId(node.id);
    setViewMode('tool-focus');
  };

  const closeToolAndSave = () => {
    if (activeToolNode) {
      showToast(`Tool focus result saved: ${activeToolNode.label}`);
      setSelectedNodeId(activeToolNode.id);
    }
    setActiveToolNodeId(null);
    setViewMode('canvas');
  };

  const addNodeFromBuilder = () => {
    const template = templateByType[workflowBuilder.templateType];
    if (!template) {
      showToast('Select a valid node template.');
      return;
    }

    const anchor = selectedNode || nodes[nodes.length - 1];
    const sameTypeCount = nodes.filter((node) => node.type === template.type).length;
    const id = `n-${template.type}-${makeId('node')}`;

    let x = anchor ? anchor.x + 320 : 360;
    let y = anchor ? anchor.y : 200;
    if (workflowBuilder.placement === 'vertical') {
      x = anchor ? anchor.x : 320;
      y = anchor ? anchor.y + 180 : 380;
    } else if (workflowBuilder.placement === 'parallel') {
      x = anchor ? anchor.x + 320 : 360;
      y = (anchor ? anchor.y : 200) + ((sameTypeCount % 4) - 1.5) * 130;
    }

    const newNode = {
      id,
      x,
      y,
      icon: template.icon,
      label: `${template.label} ${sameTypeCount + 1}`,
      desc: template.desc,
      type: template.type,
      status: 'ready',
    };

    setNodes((prev) => [...prev, newNode]);
    setSelectedNodeId(id);
    setWorkflowBuilder((prev) => ({
      ...prev,
      fromId: prev.fromId || id,
      toId: id,
    }));
    showToast(`Node created: ${newNode.label}`);
  };

  const connectBuilderNodes = () => {
    const fromNode = nodes.find((node) => node.id === workflowBuilder.fromId);
    const toNode = nodes.find((node) => node.id === workflowBuilder.toId);
    if (!fromNode || !toNode) {
      showToast('Select valid source and target nodes.');
      return;
    }
    if (fromNode.id === toNode.id) {
      showToast('Source and target must be different.');
      return;
    }

    const siblingCount = edges.filter(
      (edge) => edge.from === fromNode.id && edge.to === toNode.id,
    ).length;
    const label = workflowBuilder.edgeLabel.trim()
      ? workflowBuilder.edgeLabel.trim()
      : `${workflowBuilder.edgeMode}-${siblingCount + 1}`;

    setEdges((prev) => [
      ...prev,
      {
        id: makeId('edge'),
        from: fromNode.id,
        to: toNode.id,
        label,
        mode: workflowBuilder.edgeMode,
      },
    ]);
    setWorkflowBuilder((prev) => ({ ...prev, edgeLabel: '' }));
    showToast('Connection added.');
  };

  const loadSampleWorkflow = () => {
    const sampleSentences = [
      'Digital ethnography reveals recursive trust formation in distributed graduate research teams.',
      'Multilingual drafting friction increases cognitive load when citation formats shift between journals.',
      'Prior studies suggest mentor feedback cadence predicts completion probability.',
      'The observed sample shows weekly feedback loops correlate with higher methodological consistency.',
      'A mixed design combining interview coding and survey triangulation reduced interpretation drift.',
      'However, convenience sampling introduced regional bias and language-specific exclusion effects.',
      'The evidence indicates transparent coding memos improve inter-rater agreement.',
      'Future work should test causality with longitudinal institutional datasets.',
    ];

    const rawText = sampleSentences.join(' ');
    const refId = makeId('ref');
    const sampleUnits = sampleSentences.map((text, idx) => ({
      id: makeId('sentence'),
      docId: refId,
      nodeId: NODE_IDS.NORM,
      paragraphId: `p-${Math.floor(idx / 4)}`,
      index: idx,
      rawText: text,
      translatedText: text,
      startOffset: idx * 100,
      endOffset: idx * 100 + text.length,
      citationSpan: '',
      highlighted: idx < 6,
      note: '',
    }));

    const categoryByIndex = [
      'core-concept',
      'core-concept',
      'methodology',
      'methodology',
      'result',
      'limitation',
      'citable-claim',
      'citable-claim',
    ];
    const sampleArtifacts = sampleUnits.flatMap((unit, idx) => [
      {
        id: makeId('artifact'),
        nodeId: NODE_IDS.EXTRACT,
        type: 'highlight',
        sourceSentenceIds: [unit.id],
        abstractText: '',
        tag: idx % 2 === 0 ? 'amber' : 'cyan',
        confidence: 1,
      },
      {
        id: makeId('artifact'),
        nodeId: NODE_IDS.EXTRACT,
        type: 'category',
        sourceSentenceIds: [unit.id],
        abstractText: '',
        tag: categoryByIndex[idx],
        confidence: 0.9,
      },
    ]);
    sampleArtifacts.push({
      id: makeId('artifact'),
      nodeId: NODE_IDS.EXTRACT,
      type: 'abstract',
      sourceSentenceIds: sampleUnits.slice(0, 3).map((unit) => unit.id),
      abstractText:
        'Trust formation and multilingual drafting friction jointly shape research progression.',
      tag: 'abstract',
      confidence: 0.88,
    });

    const categoryMap = {};
    sampleArtifacts
      .filter((artifact) => artifact.type === 'category')
      .forEach((artifact) => {
        if (!categoryMap[artifact.tag]) categoryMap[artifact.tag] = [];
        categoryMap[artifact.tag].push(...artifact.sourceSentenceIds);
      });
    Object.keys(categoryMap).forEach((key) => {
      categoryMap[key] = [...new Set(categoryMap[key])];
    });

    const evidenceLinks = [
      ...new Set(sampleArtifacts.flatMap((artifact) => artifact.sourceSentenceIds)),
    ];

    const theoryDraft = [
      'Theoretical Background Draft',
      '',
      '1. core-concept: trust formation + multilingual friction',
      '2. methodology: feedback cadence and triangulation strategy',
      '3. limitation: convenience sampling and regional bias',
      '',
      'Evidence Snapshots',
      ...sampleUnits.slice(0, 6).map((unit) => `- [${unit.id}] ${truncate(unit.translatedText, 92)}`),
    ].join('\n');

    const sampleQuestions = [
      {
        id: makeId('rq'),
        text: 'How does mentor feedback cadence moderate methodological consistency in multilingual teams?',
      },
      {
        id: makeId('rq'),
        text: 'Which mechanisms link coding memo transparency to inter-rater agreement?',
      },
      {
        id: makeId('rq'),
        text: 'What mixed-method design best validates trust formation dynamics across institutions?',
      },
    ];

    const selectedQuestionIds = [sampleQuestions[0].id, sampleQuestions[2].id];
    const selectedRQs = sampleQuestions.filter((q) => selectedQuestionIds.includes(q.id));
    const methodologyDraft = [
      'Methodology Draft',
      '',
      'Selected Research Questions',
      ...selectedRQs.map((q) => `- ${q.text}`),
      '',
      'Template: mixed',
      'Required Data Sources: interview, survey, institutional archive',
      '',
      'Analytic Plan',
      'Step1 thematic coding -> Step2 quantized codebook -> Step3 triangulation regression.',
      '',
      'Validity Checks',
      'inter-rater reliability, member checking, cross-source consistency.',
      '',
      `Evidence Links (${evidenceLinks.length})`,
      ...evidenceLinks.slice(0, 8).map((id) => `- ${id}`),
    ].join('\n');

    const extractBranchId = `n-extract-${makeId('branch')}`;
    const theoryBranchId = `n-theory-${makeId('branch')}`;
    const questionBranchId = `n-question-${makeId('branch')}`;
    const methodBranchId = `n-method-${makeId('branch')}`;

    const branchNodes = [
      {
        id: extractBranchId,
        x: 980,
        y: 430,
        icon: 'BoxSelect',
        label: 'Sentence Extract Parallel Branch',
        desc: 'Alternative extraction channel',
        type: 'extract',
        status: 'completed',
      },
      {
        id: theoryBranchId,
        x: 1290,
        y: 430,
        icon: 'BrainCircuit',
        label: 'Theory Builder Branch',
        desc: 'Competing explanatory frame',
        type: 'theory',
        status: 'completed',
      },
      {
        id: questionBranchId,
        x: 1600,
        y: 430,
        icon: 'Search',
        label: 'RQ Generator Branch',
        desc: 'Alternative question stream',
        type: 'question',
        status: 'completed',
      },
      {
        id: methodBranchId,
        x: 1910,
        y: 430,
        icon: 'GitBranch',
        label: 'Methodology Branch',
        desc: 'Comparative method path',
        type: 'methodology',
        status: 'ready',
      },
    ];

    const branchEdges = [
      ...INITIAL_EDGES,
      { id: makeId('edge'), from: NODE_IDS.NORM, to: extractBranchId, label: 'parallel-units', mode: 'vertical' },
      { id: makeId('edge'), from: NODE_IDS.EXTRACT, to: theoryBranchId, label: 'alt-theory', mode: 'parallel' },
      { id: makeId('edge'), from: extractBranchId, to: NODE_IDS.THEORY, label: 'merge-up', mode: 'parallel' },
      { id: makeId('edge'), from: theoryBranchId, to: NODE_IDS.QUESTION, label: 'alt-rq-feed', mode: 'parallel' },
      { id: makeId('edge'), from: NODE_IDS.THEORY, to: questionBranchId, label: 'secondary-stream', mode: 'parallel' },
      { id: makeId('edge'), from: questionBranchId, to: NODE_IDS.METHOD, label: 'rq-merge', mode: 'parallel' },
      { id: makeId('edge'), from: NODE_IDS.QUESTION, to: methodBranchId, label: 'vertical-method', mode: 'vertical' },
      { id: makeId('edge'), from: questionBranchId, to: methodBranchId, label: 'parallel-method', mode: 'parallel' },
    ];

    setNodes([...INITIAL_NODES, ...branchNodes]);
    setEdges(branchEdges);
    setReferenceForm((prev) => ({
      ...prev,
      sourceType: 'upload',
      sourceUrl: '',
      manualText: rawText,
      title: 'Sample Workflow: Node-based Research Assistant',
      authors: 'Lee, Kim, Park',
      year: '2025',
      doi: '10.1234/sample.workflow.2025.001',
    }));
    setReferenceDocument({
      id: refId,
      projectId: apiConfig.projectId,
      sourceType: 'upload',
      sourceUrl: '',
      fileHash: makeId('hash'),
      title: 'Sample Workflow: Node-based Research Assistant',
      authors: 'Lee, Kim, Park',
      year: '2025',
      journal: 'Journal of Research Workflow Systems',
      doi: '10.1234/sample.workflow.2025.001',
      rawText,
      extractedAt: new Date().toISOString(),
      languageDetected: 'en',
      recommendationCitation:
        'Lee, Kim, Park (2025). Sample Workflow: Node-based Research Assistant.',
    });
    setTranslatedText(rawText);
    setSentenceUnits(sampleUnits);
    setSentenceArtifacts(sampleArtifacts);
    setSelectedSentenceIds(sampleUnits.slice(0, 2).map((unit) => unit.id));
    setSentenceViewMode('highlight');
    setTheoryBackground({
      id: makeId('theory'),
      nodeId: NODE_IDS.THEORY,
      concepts: Object.keys(categoryMap),
      categoryMap,
      evidenceLinks,
      draftText: theoryDraft,
      revisionHistory: [
        { id: makeId('rev'), at: new Date().toISOString(), by: 'sample', note: 'sample bootstrap' },
      ],
    });
    setResearchQuestionDraft({
      id: makeId('rqdraft'),
      nodeId: NODE_IDS.QUESTION,
      questions: sampleQuestions,
      selectedQuestionIds,
      rationaleRefs: evidenceLinks.slice(0, 5),
      theorySupportIds: evidenceLinks.slice(0, 5),
    });
    setRqTab('review');
    setMethodologyContext((prev) => ({
      ...prev,
      id: makeId('method'),
      selectedRQs,
      methodTemplateType: 'mixed',
      requiredDataSources: 'interview, survey, archive',
      analyticPlan: 'thematic coding -> triangulation -> explanatory modeling',
      validityChecks: 'inter-rater reliability + member checking + robustness checks',
      draftText: methodologyDraft,
      riskLog: [
        'Regional sampling bias remains possible.',
        'Citation translation drift must be manually audited.',
      ],
    }));
    setNodeExecutionState({
      [NODE_IDS.REF]: { ok: true, message: 'sample loaded', at: new Date().toISOString() },
      [NODE_IDS.RAW]: { ok: true, message: 'sample loaded', at: new Date().toISOString() },
      [NODE_IDS.NORM]: { ok: true, message: 'sample loaded', at: new Date().toISOString() },
      [NODE_IDS.EXTRACT]: { ok: true, message: 'sample loaded', at: new Date().toISOString() },
      [NODE_IDS.THEORY]: { ok: true, message: 'sample loaded', at: new Date().toISOString() },
      [NODE_IDS.QUESTION]: { ok: true, message: 'sample loaded', at: new Date().toISOString() },
      [NODE_IDS.METHOD]: { ok: true, message: 'sample loaded', at: new Date().toISOString() },
      [extractBranchId]: { ok: true, message: 'sample loaded', at: new Date().toISOString() },
      [theoryBranchId]: { ok: true, message: 'sample loaded', at: new Date().toISOString() },
      [questionBranchId]: { ok: true, message: 'sample loaded', at: new Date().toISOString() },
      [methodBranchId]: { ok: false, message: 'ready', at: new Date().toISOString() },
    });
    setWorkflowBuilder({
      templateType: 'extract',
      placement: 'parallel',
      fromId: NODE_IDS.EXTRACT,
      toId: theoryBranchId,
      edgeMode: 'parallel',
      edgeLabel: '',
    });
    setSelectedNodeId(NODE_IDS.METHOD);
    showToast('Sample workflow loaded: parallel/vertical/multi edges are ready.');
  };

  const getSentenceCategory = (sentenceId) =>
    (artifactBySentence[sentenceId]?.category || []).slice(-1)[0]?.tag || 'uncategorized';

  const getSentenceHighlightColor = (sentenceId) =>
    (artifactBySentence[sentenceId]?.highlight || []).slice(-1)[0]?.tag || '';

  const isSentenceHighlighted = (sentenceId) => Boolean((artifactBySentence[sentenceId]?.highlight || []).length);

  const visibleSentences = useMemo(() => {
    if (sentenceViewMode === 'highlight') {
      return sentenceUnits.filter((s) => isSentenceHighlighted(s.id));
    }
    return sentenceUnits;
  }, [sentenceUnits, sentenceViewMode, artifactBySentence]);

  const removeArtifactsByTypeAndSentence = useCallback((type, sentenceId) => {
    setSentenceArtifacts((prev) =>
      prev.filter(
        (a) => !(a.type === type && a.sourceSentenceIds.length === 1 && a.sourceSentenceIds[0] === sentenceId),
      ),
    );
  }, []);

  const setHighlight = (sentenceId, colorTag) => {
    removeArtifactsByTypeAndSentence('highlight', sentenceId);
    setSentenceArtifacts((prev) => [
      ...prev,
      {
        id: makeId('artifact'),
        nodeId: NODE_IDS.EXTRACT,
        type: 'highlight',
        sourceSentenceIds: [sentenceId],
        abstractText: '',
        tag: colorTag,
        confidence: 1,
      },
    ]);
  };

  const toggleLineHighlight = (sentenceId) => {
    if (isSentenceHighlighted(sentenceId)) {
      removeArtifactsByTypeAndSentence('highlight', sentenceId);
      return;
    }
    setHighlight(sentenceId, highlightColor);
  };

  const highlightSelectedByBox = () => {
    if (!selectedSentenceIds.length) {
      showToast('Select sentence blocks first.');
      return;
    }
    selectedSentenceIds.forEach((sid) => setHighlight(sid, highlightColor));
    showToast(`Box highlight applied: ${selectedSentenceIds.length} sentence(s).`);
  };

  const setCategoryForSentence = (sentenceId, category) => {
    removeArtifactsByTypeAndSentence('category', sentenceId);
    setSentenceArtifacts((prev) => [
      ...prev,
      {
        id: makeId('artifact'),
        nodeId: NODE_IDS.EXTRACT,
        type: 'category',
        sourceSentenceIds: [sentenceId],
        abstractText: '',
        tag: category,
        confidence: 0.9,
      },
    ]);
  };

  const moveSelectedToCategory = () => {
    if (!selectedSentenceIds.length) {
      showToast('Select sentence blocks first.');
      return;
    }
    selectedSentenceIds.forEach((sid) => setCategoryForSentence(sid, categoryBucket));
    showToast(`Category moved: ${categoryBucket}`);
  };

  const splitSentenceUnit = (sentenceId) => {
    const target = sentenceUnits.find((s) => s.id === sentenceId);
    if (!target) return;

    const parts = target.translatedText
      .split(/[,;]\s*/)
      .map((s) => s.trim())
      .filter((s) => s.length > 1);

    if (parts.length < 2) {
      showToast('Split requires at least two parts.');
      return;
    }

    const index = sentenceUnits.findIndex((s) => s.id === sentenceId);
    const nextUnits = [...sentenceUnits];
    const replacements = parts.map((part, i) => ({
      id: makeId('sentence'),
      docId: target.docId,
      nodeId: NODE_IDS.EXTRACT,
      paragraphId: target.paragraphId,
      index: target.index + i / 10,
      rawText: part,
      translatedText: part,
      startOffset: target.startOffset,
      endOffset: target.startOffset + part.length,
      citationSpan: extractCitation(part),
      highlighted: false,
      note: '',
    }));

    nextUnits.splice(index, 1, ...replacements);
    setSentenceUnits(resetSentenceOrder(nextUnits));
    setSentenceArtifacts((prev) => prev.filter((a) => !a.sourceSentenceIds.includes(sentenceId)));
    setSelectedSentenceIds((prev) => prev.filter((id) => id !== sentenceId));
    showToast('Sentence split applied.');
  };

  const mergeSelectedSentences = () => {
    if (selectedSentenceIds.length < 2) {
      showToast('Merge requires at least two selected sentences.');
      return;
    }

    const selected = sentenceUnits
      .filter((s) => selectedSentenceIds.includes(s.id))
      .sort((a, b) => a.index - b.index);

    const anchor = selected[0];
    const firstIdx = sentenceUnits.findIndex((s) => s.id === anchor.id);

    const merged = {
      id: makeId('sentence'),
      docId: anchor.docId,
      nodeId: NODE_IDS.EXTRACT,
      paragraphId: anchor.paragraphId,
      index: anchor.index,
      rawText: selected.map((s) => s.rawText).join(' '),
      translatedText: selected.map((s) => s.translatedText).join(' '),
      startOffset: Math.min(...selected.map((s) => s.startOffset || 0)),
      endOffset: Math.max(...selected.map((s) => s.endOffset || 0)),
      citationSpan: selected.map((s) => s.citationSpan).filter(Boolean).join('; '),
      highlighted: false,
      note: `merged:${selected.map((s) => s.index + 1).join(',')}`,
    };

    const next = sentenceUnits.filter((s) => !selectedSentenceIds.includes(s.id));
    next.splice(firstIdx, 0, merged);
    setSentenceUnits(resetSentenceOrder(next));

    setSentenceArtifacts((prev) => [
      ...prev,
      {
        id: makeId('artifact'),
        nodeId: NODE_IDS.EXTRACT,
        type: 'merged',
        sourceSentenceIds: [...selectedSentenceIds],
        abstractText: merged.translatedText,
        tag: 'merged',
        confidence: 0.88,
      },
    ]);

    setSelectedSentenceIds([]);
    showToast('Sentence merge applied.');
  };

  const abstractSelectedSentences = () => {
    if (!selectedSentenceIds.length) {
      showToast('Select sentence blocks first.');
      return;
    }

    const text = sentenceUnits
      .filter((s) => selectedSentenceIds.includes(s.id))
      .map((s) => s.translatedText)
      .join(' ')
      .split(/\s+/)
      .slice(0, 40)
      .join(' ');

    setSentenceArtifacts((prev) => [
      ...prev,
      {
        id: makeId('artifact'),
        nodeId: NODE_IDS.EXTRACT,
        type: 'abstract',
        sourceSentenceIds: [...selectedSentenceIds],
        abstractText: text,
        tag: 'abstract',
        confidence: 0.86,
      },
    ]);

    showToast('Abstract artifact created.');
  };

  const addSnippetFromSelected = () => {
    if (!selectedSentenceIds.length) {
      showToast('Select sentence blocks first.');
      return;
    }

    const text = sentenceUnits
      .filter((s) => selectedSentenceIds.includes(s.id))
      .map((s) => s.translatedText)
      .join(' ');

    setSentenceArtifacts((prev) => [
      ...prev,
      {
        id: makeId('artifact'),
        nodeId: NODE_IDS.EXTRACT,
        type: 'snippet',
        sourceSentenceIds: [...selectedSentenceIds],
        abstractText: truncate(text, 180),
        tag: 'snippet',
        confidence: 0.9,
      },
    ]);

    showToast('Snippet artifact created.');
  };

  const runReferenceInput = async () => {
    const executionNodeId = selectedNode?.type === 'reference' ? selectedNode.id : NODE_IDS.REF;
    const result = await runReferenceInputExecutor({
      referenceForm,
      apiConfig,
      apiCall,
      createRuntimeToken,
      nodeIds: NODE_IDS,
    });
    if (!result.ok) {
      markNodeExecution(executionNodeId, false, result.message);
      showToast(result.message);
      return false;
    }

    setReferenceDocument(result.referenceDocument);
    setTranslatedText('');
    setSentenceUnits([]);
    setSentenceArtifacts([]);
    setSelectedSentenceIds([]);
    setTheoryBackground(null);
    setRqTab('auto');
    setManualQuestionInput('');
    setResearchQuestionDraft(createInitialResearchQuestionDraft(NODE_IDS.QUESTION));
    setMethodologyContext((prev) => ({ ...prev, selectedRQs: [], draftText: '', riskLog: [] }));
    setSelectedNodeId(result.nextNodeId || NODE_IDS.RAW);
    markNodeExecution(executionNodeId, true, result.message);
    showToast(result.message);
    return true;
  };

  const runRawTranslate = async () => {
    const executionNodeId = selectedNode?.type === 'translate' ? selectedNode.id : NODE_IDS.RAW;
    const result = await runRawTranslateExecutor({
      referenceDocument,
      apiConfig,
      apiCall,
      createRuntimeToken,
      nodeIds: NODE_IDS,
    });
    if (!result.ok) {
      markNodeExecution(executionNodeId, false, result.message);
      showToast(result.message);
      return false;
    }

    setTranslatedText(result.translatedText);
    setSelectedNodeId(result.nextNodeId || NODE_IDS.NORM);
    markNodeExecution(executionNodeId, true, result.message);
    showToast(result.message);
    return true;
  };

  const runSentenceNormalization = async () => {
    const executionNodeId = selectedNode?.type === 'normalize' ? selectedNode.id : NODE_IDS.NORM;
    const result = await runSentenceNormalizationExecutor({
      translatedText,
      referenceDocument,
      apiCall,
      createRuntimeToken,
      nodeIds: NODE_IDS,
    });
    if (!result.ok) {
      markNodeExecution(executionNodeId, false, result.message);
      showToast(result.message);
      return false;
    }

    setSentenceUnits(result.sentenceUnits);
    setSentenceArtifacts([]);
    setSelectedSentenceIds([]);
    setSelectedNodeId(result.nextNodeId || NODE_IDS.EXTRACT);
    markNodeExecution(executionNodeId, true, result.message);
    showToast(result.message);
    return true;
  };

  const runExtractNode = async () => {
    const executionNodeId = selectedNode?.type === 'extract' ? selectedNode.id : NODE_IDS.EXTRACT;
    const result = await runExtractExecutor({
      sentenceUnits,
      sentenceArtifacts,
      categoryBucket,
      apiCall,
      createRuntimeToken,
      nodeIds: NODE_IDS,
    });
    if (!result.ok) {
      markNodeExecution(executionNodeId, false, result.message);
      showToast(result.message);
      return false;
    }

    if (result.bootstrapArtifacts?.length) {
      setSentenceArtifacts((prev) => [...prev, ...result.bootstrapArtifacts]);
    }
    markNodeExecution(executionNodeId, true, result.message);
    showToast(result.message);
    return true;
  };

  const buildTheoryBackground = async () => {
    const executionNodeId = selectedNode?.type === 'theory' ? selectedNode.id : NODE_IDS.THEORY;
    const result = await buildTheoryBackgroundExecutor({
      sentenceArtifacts,
      sentenceUnits,
      apiCall,
      createRuntimeToken,
      nodeIds: NODE_IDS,
    });
    if (!result.ok) {
      markNodeExecution(executionNodeId, false, result.message);
      showToast(result.message);
      return false;
    }

    setTheoryBackground(result.theoryBackground);
    setSelectedNodeId(result.nextNodeId || NODE_IDS.QUESTION);
    markNodeExecution(executionNodeId, true, result.message);
    showToast(result.message);
    return true;
  };

  const buildAutoQuestions = async () => {
    const executionNodeId = selectedNode?.type === 'question' ? selectedNode.id : NODE_IDS.QUESTION;
    const result = await buildAutoQuestionsExecutor({
      theoryBackground,
      apiCall,
      createRuntimeToken,
      nodeIds: NODE_IDS,
    });
    if (!result.ok) {
      markNodeExecution(executionNodeId, false, result.message);
      showToast(result.message);
      return false;
    }

    setResearchQuestionDraft(result.researchQuestionDraft);
    setRqTab(result.nextTab || 'review');
    markNodeExecution(executionNodeId, true, result.message);
    showToast(result.message);
    return true;
  };

  const approveSelectedQuestions = () => {
    const executionNodeId = selectedNode?.type === 'question' ? selectedNode.id : NODE_IDS.QUESTION;
    if (!researchQuestionDraft.selectedQuestionIds.length) {
      showToast('Select at least one research question.');
      return false;
    }

    const selectedRQs = researchQuestionDraft.questions.filter((q) =>
      researchQuestionDraft.selectedQuestionIds.includes(q.id),
    );

    setMethodologyContext((prev) => ({ ...prev, selectedRQs }));
    setSelectedNodeId(NODE_IDS.METHOD);
    markNodeExecution(executionNodeId, true, 'Research question fixed. Methodology node entered.');
    showToast('Research question fixed. Methodology node entered.');
    return true;
  };

  const buildMethodology = async () => {
    const executionNodeId = selectedNode?.type === 'methodology' ? selectedNode.id : NODE_IDS.METHOD;
    const result = await buildMethodologyExecutor({
      readyMethod: status.readyMethod,
      researchQuestionDraft,
      theoryBackground,
      methodologyContext,
      evidenceCount,
      apiCall,
      createRuntimeToken,
      nodeIds: NODE_IDS,
    });
    if (!result.ok) {
      markNodeExecution(executionNodeId, false, result.message);
      showToast(result.message);
      return false;
    }

    setMethodologyContext(result.methodologyContext);
    markNodeExecution(executionNodeId, true, result.message);
    showToast(result.message);
    return true;
  };

  const runSelectedNode = async () => {
    if (!selectedNodeId || !selectedNode || running) return false;
    if (selectedNode.type === 'reference') return runReferenceInput();
    if (selectedNode.type === 'translate') return runRawTranslate();
    if (selectedNode.type === 'normalize') return runSentenceNormalization();
    if (selectedNode.type === 'extract') return runExtractNode();
    if (selectedNode.type === 'theory') return buildTheoryBackground();
    if (selectedNode.type === 'question') {
      if (!researchQuestionDraft.questions.length) return buildAutoQuestions();
      showToast('Question list exists. Use review tab to approve.');
      return true;
    }
    if (selectedNode.type === 'methodology') return buildMethodology();
    return false;
  };

  const runAndCloseTool = async () => {
    const ok = await runSelectedNode();
    if (ok) closeToolAndSave();
  };

  const renderEdges = () => {
    const NODE_WIDTH = 260;
    const NODE_HEIGHT = 120;

    return edges.map((edge) => {
      const from = nodes.find((n) => n.id === edge.from);
      const to = nodes.find((n) => n.id === edge.to);
      if (!from || !to) return null;

      const siblings = edges.filter((e) => e.from === edge.from && e.to === edge.to);
      const siblingIndex = siblings.findIndex((e) => e.id === edge.id);
      const siblingOffset = (siblingIndex - (siblings.length - 1) / 2) * 22;
      const active = selectedNodeId === edge.from || selectedNodeId === edge.to;
      const mode = edge.mode || 'horizontal';

      let x1 = from.x + NODE_WIDTH;
      let y1 = from.y + NODE_HEIGHT / 2;
      let x2 = to.x;
      let y2 = to.y + NODE_HEIGHT / 2;
      let path = '';

      if (mode === 'vertical') {
        x1 = from.x + NODE_WIDTH / 2 + siblingOffset;
        y1 = from.y + NODE_HEIGHT;
        x2 = to.x + NODE_WIDTH / 2 + siblingOffset;
        y2 = to.y;
        const dy = y2 - y1;
        const c1y = y1 + dy / 2;
        const c2y = y2 - dy / 2;
        path = `M ${x1} ${y1} C ${x1} ${c1y}, ${x2} ${c2y}, ${x2} ${y2}`;
      } else {
        y1 += siblingOffset;
        y2 += siblingOffset;
        const dx = x2 - x1;
        const c1 = x1 + dx / 2;
        const c2 = x2 - dx / 2;
        path = `M ${x1} ${y1} C ${c1} ${y1}, ${c2} ${y2}, ${x2} ${y2}`;
      }

      return (
        <g key={edge.id}>
          <path
            d={path}
            fill="none"
            stroke={active ? '#3b82f6' : '#cbd5e1'}
            strokeWidth="3"
            strokeDasharray={isCompleted(edge.from) ? '6,6' : 'none'}
            className={isCompleted(edge.from) ? 'animate-[dash_1s_linear_infinite]' : ''}
          />
          <text
            x={(x1 + x2) / 2}
            y={mode === 'vertical' ? (y1 + y2) / 2 - 10 : y1 - 10}
            fill={active ? '#1d4ed8' : '#64748b'}
            fontSize="11"
            textAnchor="middle"
            className="font-semibold"
          >
            {edge.label}
          </text>
        </g>
      );
    });
  };

  const renderNodeWorkspace = () => {
    if (!selectedNodeId) return <div className="text-sm text-slate-500">Select a node on canvas.</div>;

    if (selectedNodeType === 'reference') {
      return (
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <label className="text-xs font-medium text-slate-600">
              Source Type
              <select
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm"
                value={referenceForm.sourceType}
                onChange={(e) => setReferenceForm((p) => ({ ...p, sourceType: e.target.value }))}
              >
                <option value="upload">upload</option>
                <option value="url">url</option>
              </select>
            </label>
            <label className="text-xs font-medium text-slate-600">
              Work Language
              <select
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm"
                value={apiConfig.targetLanguage}
                onChange={(e) => setApiConfig((p) => ({ ...p, targetLanguage: e.target.value }))}
              >
                <option value="en">English</option>
                <option value="ko">Korean</option>
              </select>
            </label>
            <label className="text-xs font-medium text-slate-600">
              API Mode
              <select
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm"
                value={apiConfig.mode}
                onChange={(e) => setApiConfig((p) => ({ ...p, mode: e.target.value }))}
              >
                <option value="mock">mock</option>
                <option value="real">real</option>
              </select>
            </label>
            <label className="text-xs font-medium text-slate-600">
              Provider
              <select
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm"
                value={apiConfig.provider}
                onChange={(e) => setApiConfig((p) => ({ ...p, provider: e.target.value }))}
              >
                {API_PROVIDERS.map((provider) => (
                  <option key={provider}>{provider}</option>
                ))}
              </select>
            </label>
            <label className="text-xs font-medium text-slate-600">
              Model
              <input
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm"
                value={apiConfig.model}
                onChange={(e) => setApiConfig((p) => ({ ...p, model: e.target.value }))}
              />
            </label>
          </div>

          <label className="text-xs font-medium text-slate-600">
            Personal API Key (runtime only)
            <input
              type="password"
              className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm"
              value={apiConfig.apiKey}
              onChange={(e) => setApiConfig((p) => ({ ...p, apiKey: e.target.value }))}
              placeholder="sk-..."
            />
          </label>

          {referenceForm.sourceType === 'upload' ? (
            <label className="text-xs font-medium text-slate-600">
              Upload (PDF/DOCX/TXT)
              <input
                type="file"
                accept=".txt,.pdf,.docx,.doc,.md"
                className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm"
                onChange={(e) => setReferenceForm((p) => ({ ...p, file: e.target.files?.[0] || null }))}
              />
            </label>
          ) : (
            <label className="text-xs font-medium text-slate-600">
              Source URL
              <input
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm"
                value={referenceForm.sourceUrl}
                onChange={(e) => setReferenceForm((p) => ({ ...p, sourceUrl: e.target.value }))}
                placeholder="https://..."
              />
            </label>
          )}

          <label className="text-xs font-medium text-slate-600">
            Manual Text (fallback)
            <textarea
              rows={4}
              className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm"
              value={referenceForm.manualText}
              onChange={(e) => setReferenceForm((p) => ({ ...p, manualText: e.target.value }))}
            />
          </label>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <input className="rounded-md border border-slate-300 bg-white px-2 py-2 text-sm" placeholder="title" value={referenceForm.title} onChange={(e) => setReferenceForm((p) => ({ ...p, title: e.target.value }))} />
            <input className="rounded-md border border-slate-300 bg-white px-2 py-2 text-sm" placeholder="authors" value={referenceForm.authors} onChange={(e) => setReferenceForm((p) => ({ ...p, authors: e.target.value }))} />
            <input className="rounded-md border border-slate-300 bg-white px-2 py-2 text-sm" placeholder="year" value={referenceForm.year} onChange={(e) => setReferenceForm((p) => ({ ...p, year: e.target.value }))} />
            <input className="rounded-md border border-slate-300 bg-white px-2 py-2 text-sm" placeholder="doi" value={referenceForm.doi} onChange={(e) => setReferenceForm((p) => ({ ...p, doi: e.target.value }))} />
          </div>

          <button onClick={runReferenceInput} disabled={running} className="rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:bg-slate-400">Run Reference Input Node</button>

          {referenceDocument ? (
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
              <div className="font-semibold text-slate-800">{referenceDocument.title}</div>
              <div>{referenceDocument.authors || 'Unknown'} ({referenceDocument.year || 'n.d.'})</div>
              <div>DOI: {referenceDocument.doi || '-'}</div>
              <div>Detected: {referenceDocument.languageDetected}</div>
            </div>
          ) : null}
        </div>
      );
    }

    if (selectedNodeType === 'translate') {
      return (
        <div className="space-y-3">
          <button onClick={runRawTranslate} disabled={!isReady(selectedNodeId || NODE_IDS.RAW) || running} className="rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:bg-slate-400">Run Raw Translate Node</button>
          <textarea rows={8} className="w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm" readOnly value={translatedText || referenceDocument?.rawText || ''} />
          <div className="text-xs text-slate-500">Preservation rule: citations/equations/author tokens are kept unchanged in MVP mock.</div>
        </div>
      );
    }

    if (selectedNodeType === 'normalize') {
      return (
        <div className="space-y-3">
          <button onClick={runSentenceNormalization} disabled={!isReady(selectedNodeId || NODE_IDS.NORM) || running} className="rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:bg-slate-400">Run Sentence Normalization Node</button>
          <div className="text-xs text-slate-500">Sentence units: {sentenceUnits.length}</div>
          <div className="max-h-64 space-y-2 overflow-auto rounded-md border border-slate-200 bg-white p-2 text-xs">
            {sentenceUnits.map((s) => (
              <div key={s.id} className="rounded border border-slate-200 p-2">[{s.index + 1}] {truncate(s.translatedText, 110)}</div>
            ))}
            {!sentenceUnits.length ? <div className="text-slate-500">No sentence units</div> : null}
          </div>
        </div>
      );
    }

    if (selectedNodeType === 'extract') {
      return (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <select value={sentenceViewMode} onChange={(e) => setSentenceViewMode(e.target.value)} className="rounded-md border border-slate-300 bg-white px-2 py-2 text-sm">
              <option value="raw">raw</option>
              <option value="translated">translated</option>
              <option value="highlight">highlight</option>
            </select>
            <select value={highlightColor} onChange={(e) => setHighlightColor(e.target.value)} className="rounded-md border border-slate-300 bg-white px-2 py-2 text-sm">
              <option value="amber">amber</option>
              <option value="cyan">cyan</option>
              <option value="emerald">emerald</option>
              <option value="violet">violet</option>
            </select>
            <select value={categoryBucket} onChange={(e) => setCategoryBucket(e.target.value)} className="rounded-md border border-slate-300 bg-white px-2 py-2 text-sm">
              {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <button onClick={highlightSelectedByBox} className="rounded-md bg-amber-600 px-2 py-2 text-xs font-semibold text-white hover:bg-amber-700">Box Highlight</button>
            <button onClick={moveSelectedToCategory} className="rounded-md bg-emerald-600 px-2 py-2 text-xs font-semibold text-white hover:bg-emerald-700">Move Category</button>
            <button onClick={mergeSelectedSentences} className="rounded-md bg-sky-600 px-2 py-2 text-xs font-semibold text-white hover:bg-sky-700">Merge</button>
            <button onClick={abstractSelectedSentences} className="rounded-md bg-violet-600 px-2 py-2 text-xs font-semibold text-white hover:bg-violet-700">Abstract</button>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <button onClick={addSnippetFromSelected} className="rounded-md bg-slate-700 px-2 py-2 text-xs font-semibold text-white hover:bg-slate-800">Snippet</button>
            <button onClick={runExtractNode} disabled={!isReady(selectedNodeId || NODE_IDS.EXTRACT) || running} className="rounded-md bg-indigo-600 px-2 py-2 text-xs font-semibold text-white hover:bg-indigo-700 disabled:bg-slate-400">Sync Extract Node</button>
            <button onClick={buildTheoryBackground} disabled={!isReady(selectedNodeId || NODE_IDS.THEORY) || running} className="rounded-md bg-teal-600 px-2 py-2 text-xs font-semibold text-white hover:bg-teal-700 disabled:bg-slate-400">Build Theory</button>
          </div>

          <div className="text-xs text-slate-500">Sentence blocks: {visibleSentences.length} | Selected: {selectedSentenceIds.length} | Artifacts: {sentenceArtifacts.length}</div>

          <div className="max-h-80 space-y-2 overflow-auto rounded-md border border-slate-200 bg-white p-2">
            {visibleSentences.map((s) => {
              const highlighted = isSentenceHighlighted(s.id);
              const color = getSentenceHighlightColor(s.id);
              const category = getSentenceCategory(s.id);
              const text = sentenceViewMode === 'raw' ? s.rawText : s.translatedText;
              return (
                <div key={s.id} className={`rounded-md border p-2 text-sm ${highlighted ? 'border-amber-300 bg-amber-50' : 'border-slate-200 bg-white'}`}>
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs">
                    <label className="flex items-center gap-2">
                      <input type="checkbox" checked={selectedSentenceIds.includes(s.id)} onChange={() => setSelectedSentenceIds((prev) => (prev.includes(s.id) ? prev.filter((id) => id !== s.id) : [...prev, s.id]))} />
                      <span>#{s.index + 1}</span>
                    </label>
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-slate-100 px-2 py-0.5">{category}</span>
                      {color ? <span className="rounded bg-slate-800 px-2 py-0.5 text-white">{color}</span> : null}
                      <button onClick={() => toggleLineHighlight(s.id)} className="rounded bg-cyan-700 px-2 py-1 text-white">line</button>
                      <button onClick={() => splitSentenceUnit(s.id)} className="rounded bg-emerald-700 px-2 py-1 text-white">split</button>
                      <button onClick={() => setCategoryForSentence(s.id, categoryBucket)} className="rounded bg-indigo-700 px-2 py-1 text-white">cat</button>
                    </div>
                  </div>
                  <p className="text-slate-700">{text}</p>
                </div>
              );
            })}
            {!visibleSentences.length ? <div className="text-xs text-slate-500">No sentence block available.</div> : null}
          </div>
        </div>
      );
    }

    if (selectedNodeType === 'theory') {
      const categoryMap = theoryBackground?.categoryMap || {};
      return (
        <div className="space-y-3">
          <button onClick={buildTheoryBackground} disabled={!isReady(selectedNodeId || NODE_IDS.THEORY) || running} className="rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:bg-slate-400">Run Theory Builder Node</button>
          {theoryBackground ? (
            <>
              <div className="text-xs text-slate-500">Category tree + evidence snapshot output</div>
              <div className="max-h-40 space-y-2 overflow-auto rounded-md border border-slate-200 bg-white p-2 text-xs">
                {Object.keys(categoryMap).map((key) => (
                  <div key={key} className="rounded border border-slate-200 bg-slate-50 p-2">
                    <div className="font-semibold text-slate-700">{key}</div>
                    <div className="text-slate-500">evidence links: {(categoryMap[key] || []).length}</div>
                  </div>
                ))}
                {!Object.keys(categoryMap).length ? <div className="text-slate-500">No category nodes</div> : null}
              </div>
              <textarea rows={10} className="w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm" value={theoryBackground.draftText} onChange={(e) => setTheoryBackground((p) => (p ? { ...p, draftText: e.target.value } : p))} />
            </>
          ) : (
            <div className="text-sm text-slate-500">Run Extract node and create artifacts first.</div>
          )}
        </div>
      );
    }

    if (selectedNodeType === 'question') {
      return (
        <div className="space-y-3">
          <div className="inline-flex rounded-md border border-slate-200 bg-white p-1 text-xs">
            <button onClick={() => setRqTab('auto')} className={`rounded px-2 py-1 ${rqTab === 'auto' ? 'bg-indigo-600 text-white' : 'text-slate-600'}`}>auto</button>
            <button onClick={() => setRqTab('manual')} className={`rounded px-2 py-1 ${rqTab === 'manual' ? 'bg-indigo-600 text-white' : 'text-slate-600'}`}>manual</button>
            <button onClick={() => setRqTab('review')} className={`rounded px-2 py-1 ${rqTab === 'review' ? 'bg-indigo-600 text-white' : 'text-slate-600'}`}>review</button>
          </div>

          {rqTab === 'auto' ? (
            <div className="space-y-2">
              <button onClick={buildAutoQuestions} disabled={!isReady(selectedNodeId || NODE_IDS.QUESTION) || running} className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:bg-slate-400">Auto Generate 3-5 Questions</button>
              <div className="text-xs text-slate-500">Evidence links: {evidenceCount}</div>
            </div>
          ) : null}

          {rqTab === 'manual' ? (
            <div className="space-y-2">
              <textarea rows={5} className="w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm" value={manualQuestionInput} onChange={(e) => setManualQuestionInput(e.target.value)} placeholder="one question per line" />
              <button
                onClick={() => {
                  const rows = manualQuestionInput.split('\n').map((x) => x.trim()).filter(Boolean).map((text) => ({ id: makeId('rq'), text }));
                  if (!rows.length) {
                    showToast('Enter manual questions first.');
                    return;
                  }
                  setResearchQuestionDraft((prev) => ({ ...prev, id: prev.id || makeId('rqdraft'), questions: [...prev.questions, ...rows] }));
                  setManualQuestionInput('');
                  showToast(`Added ${rows.length} manual question(s).`);
                }}
                className="rounded-md bg-slate-700 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800"
              >
                Add Manual
              </button>
            </div>
          ) : null}

          {rqTab === 'review' ? (
            <div className="space-y-2">
              <div className="text-xs text-slate-500">Candidates: {researchQuestionDraft.questions.length}</div>
              <div className="max-h-64 space-y-2 overflow-auto rounded-md border border-slate-200 bg-white p-2 text-sm">
                {researchQuestionDraft.questions.map((q) => (
                  <label key={q.id} className="flex items-start gap-2 rounded border border-slate-200 p-2">
                    <input
                      type="checkbox"
                      checked={researchQuestionDraft.selectedQuestionIds.includes(q.id)}
                      onChange={() =>
                        setResearchQuestionDraft((prev) => ({
                          ...prev,
                          selectedQuestionIds: prev.selectedQuestionIds.includes(q.id)
                            ? prev.selectedQuestionIds.filter((id) => id !== q.id)
                            : [...prev.selectedQuestionIds, q.id],
                        }))
                      }
                    />
                    <span>{q.text}</span>
                  </label>
                ))}
                {!researchQuestionDraft.questions.length ? <div className="text-xs text-slate-500">No candidate questions.</div> : null}
              </div>
              <button onClick={approveSelectedQuestions} className="rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700">Approve Selected</button>
            </div>
          ) : null}
        </div>
      );
    }

    if (selectedNodeType === 'methodology') {
      return (
        <div className="space-y-3">
          <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
            Lock condition: approved question + category artifacts + evidence links {'>='} 3
            <div>Approved questions: {approvedCount}</div>
            <div>Category artifacts: {categoryArtifactCount}</div>
            <div>Evidence links: {evidenceCount}</div>
            <div>Lock: {locks.methodology.locked ? locks.methodology.reasons.join(' | ') : 'unlocked'}</div>
          </div>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <label className="text-xs font-medium text-slate-600">
              Method Template
              <select className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm" value={methodologyContext.methodTemplateType} onChange={(e) => setMethodologyContext((p) => ({ ...p, methodTemplateType: e.target.value }))}>
                {METHOD_TEMPLATES.map((tpl) => <option key={tpl}>{tpl}</option>)}
              </select>
            </label>
            <label className="text-xs font-medium text-slate-600">
              Required Data Sources
              <input className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm" value={methodologyContext.requiredDataSources} onChange={(e) => setMethodologyContext((p) => ({ ...p, requiredDataSources: e.target.value }))} placeholder="interview/survey/archive..." />
            </label>
          </div>

          <textarea rows={3} className="w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm" value={methodologyContext.analyticPlan} onChange={(e) => setMethodologyContext((p) => ({ ...p, analyticPlan: e.target.value }))} placeholder="analytic plan" />
          <textarea rows={3} className="w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm" value={methodologyContext.validityChecks} onChange={(e) => setMethodologyContext((p) => ({ ...p, validityChecks: e.target.value }))} placeholder="validity checks" />

          <button onClick={buildMethodology} disabled={locks.methodology.locked || running} className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:bg-slate-400">Run Methodology Node</button>

          <textarea rows={10} className="w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm" value={methodologyContext.draftText} onChange={(e) => setMethodologyContext((p) => ({ ...p, draftText: e.target.value }))} />
        </div>
      );
    }

    return <div className="text-sm text-slate-500">No workspace content.</div>;
  };

  if (viewMode === 'tool-focus' && activeToolNode) {
    const ActiveIcon = ICON_MAP[activeToolNode.icon] || Settings;
    return (
      <div className="flex h-screen w-full flex-col overflow-hidden bg-slate-900 text-slate-100">
        <style>{`@keyframes slideDown { from { transform: translate(-50%, -90%); opacity: 0; } to { transform: translate(-50%, 0); opacity: 1; } } @keyframes dash { to { stroke-dashoffset: -10; } }`}</style>

        {toast ? (
          <div className="absolute left-1/2 top-5 z-50 -translate-x-1/2 animate-[slideDown_0.3s_ease-out] rounded-full border border-slate-500 bg-slate-800 px-5 py-2 text-sm shadow-lg">
            <div className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-300" />{toast}</div>
          </div>
        ) : null}

        <div className="h-14 border-b border-slate-700 bg-slate-800 px-4">
          <div className="flex h-full items-center justify-between">
            <div className="flex min-w-0 items-center gap-3">
              <button onClick={() => { setViewMode('canvas'); setActiveToolNodeId(null); }} className="inline-flex items-center gap-2 rounded-md bg-slate-700 px-3 py-1.5 text-xs font-semibold hover:bg-slate-600"><ArrowLeft className="h-4 w-4" />Back To Canvas</button>
              <div className="h-4 w-px bg-slate-600" />
              <div className="flex min-w-0 items-center gap-2">
                <div className="rounded-md bg-indigo-500/15 p-2 text-indigo-300"><ActiveIcon className="h-4 w-4" /></div>
                <div className="min-w-0"><div className="truncate text-sm font-bold">{activeToolNode.label}</div><div className="truncate text-xs text-slate-400">{activeToolNode.desc}</div></div>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="rounded-md border border-emerald-400/30 bg-emerald-500/10 px-2 py-1 text-emerald-300">{getStatusLabel(activeToolNode.id)}</span>
              <button onClick={runSelectedNode} disabled={running} className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-white hover:bg-indigo-700 disabled:bg-slate-600"><Play className="h-3.5 w-3.5" />Run Node</button>
            </div>
          </div>
        </div>

        <div className="flex flex-1 items-center justify-center overflow-hidden bg-slate-900 p-6">
          <div className="flex h-full w-full max-w-[1500px] flex-col overflow-hidden rounded-xl border border-slate-700 bg-white shadow-2xl">
            <div className="h-14 border-b border-slate-200 px-6"><div className="flex h-full items-center gap-2 text-slate-800"><Network className="h-5 w-5 text-indigo-600" /><span className="font-bold tracking-tight">Paper Assistant Focus Workspace</span></div></div>

            <div className="flex flex-1 overflow-hidden">
              <div className="w-[430px] shrink-0 border-r border-slate-200 bg-slate-50 p-5">
                <div className="h-full overflow-y-auto rounded-lg border border-slate-200 bg-white p-3">
                  <h3 className="mb-2 text-sm font-bold text-slate-800">Node Controls</h3>
                  {renderNodeWorkspace()}
                </div>
              </div>

              <div className="relative flex-1 overflow-hidden bg-white p-6">
                <div className="absolute inset-0 opacity-[0.03]" style={{ backgroundImage: 'radial-gradient(#0f172a 1px, transparent 1px)', backgroundSize: '24px 24px' }} />
                <div className="relative z-10 h-full rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-4">
                  <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700"><Activity className="h-3.5 w-3.5" />Focused run surface for {activeToolNode.label}</div>
                  <div className="grid h-[calc(100%-32px)] grid-cols-1 gap-3 lg:grid-cols-[1.2fr_1fr]">
                    <div className="rounded-lg border border-slate-200 bg-white p-3"><div className="mb-2 text-sm font-bold text-slate-800">Pipeline Context</div><svg className="h-[92%] w-full" viewBox="0 0 2400 520" preserveAspectRatio="xMinYMin meet">{renderEdges()}</svg></div>
                    <div className="rounded-lg border border-slate-200 bg-white p-3"><div className="mb-2 text-sm font-bold text-slate-800">Recent API Calls</div><div className="max-h-[92%] space-y-2 overflow-auto text-xs">{apiLog.length ? apiLog.map((log) => <div key={log.id} className="rounded border border-slate-200 bg-slate-50 p-2"><div className="font-semibold text-slate-700">{log.endpoint}</div><div className="text-slate-500">{toLocalTime(log.at)}</div></div>) : <div className="text-slate-500">No logs yet.</div>}</div></div>
                  </div>
                </div>
              </div>
            </div>

            <div className="border-t border-emerald-200 bg-emerald-50 p-4"><button onClick={runAndCloseTool} disabled={running} className="w-full rounded-md bg-emerald-600 px-3 py-2 text-sm font-bold text-white hover:bg-emerald-700 disabled:bg-slate-400">Commit Result And Close</button></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-full overflow-hidden bg-slate-50 font-sans text-slate-800">
      <style>{`@keyframes slideDown { from { transform: translate(-50%, -90%); opacity: 0; } to { transform: translate(-50%, 0); opacity: 1; } } @keyframes dash { to { stroke-dashoffset: -10; } }`}</style>

      {toast ? (
        <div className="absolute left-1/2 top-6 z-50 -translate-x-1/2 animate-[slideDown_0.3s_ease-out] rounded-full bg-slate-800 px-5 py-2 text-sm text-white shadow-2xl">
          <div className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-300" />{toast}</div>
        </div>
      ) : null}

      <div className="z-10 flex w-16 flex-col items-center gap-6 border-r border-slate-200 bg-white py-4 shadow-sm">
        <button className="rounded-xl bg-indigo-600 p-2.5 text-white shadow-md"><Layers className="h-6 w-6" /></button>
        <div className="flex w-full flex-col gap-3 px-2">
          <button onClick={() => setSelectedNodeId(NODE_IDS.REF)} className="flex justify-center rounded-xl p-3 text-slate-400 transition hover:bg-slate-100 hover:text-indigo-600"><Database className="h-5 w-5" /></button>
          <button onClick={() => setSelectedNodeId(NODE_IDS.EXTRACT)} className="flex justify-center rounded-xl p-3 text-slate-400 transition hover:bg-slate-100 hover:text-indigo-600"><BoxSelect className="h-5 w-5" /></button>
          <button onClick={() => setSelectedNodeId(NODE_IDS.THEORY)} className="flex justify-center rounded-xl p-3 text-slate-400 transition hover:bg-slate-100 hover:text-indigo-600"><BrainCircuit className="h-5 w-5" /></button>
          <div className="mx-auto my-1 h-px w-8 bg-slate-200" />
          <button onClick={() => openToolView(selectedNode || nodes[0])} disabled={!selectedNode} className="group relative flex justify-center rounded-xl border border-orange-100 bg-orange-50 p-3 text-orange-600 shadow-sm transition disabled:opacity-50"><Maximize2 className="h-5 w-5" /></button>
          <button onClick={() => setShowPanel((v) => !v)} className="flex justify-center rounded-xl p-3 text-slate-400 transition hover:bg-slate-100 hover:text-indigo-600"><Settings className="h-5 w-5" /></button>
        </div>
      </div>

      <div className="relative flex-1 overflow-auto bg-[#f8fafc]" style={{ backgroundImage: 'radial-gradient(#cbd5e1 1px, transparent 1px)', backgroundSize: '24px 24px' }} onClick={() => setSelectedNodeId(null)}>
        <div className="absolute right-4 top-4 z-10 flex flex-wrap gap-2">
          <button onClick={loadSampleWorkflow} className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-md transition hover:bg-emerald-700"><Activity className="h-4 w-4" />Load Sample Workflow</button>
          <button onClick={runSelectedNode} disabled={running || !selectedNodeId} className="inline-flex items-center gap-2 rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-md transition hover:bg-indigo-700 disabled:bg-slate-400"><Play className="h-4 w-4" />{running ? `Running: ${runningEndpoint}` : 'Run Selected Node'}</button>
          <button onClick={() => openToolView(selectedNode || nodes[0])} disabled={!selectedNode} className="inline-flex items-center gap-2 rounded-md bg-orange-500 px-4 py-2 text-sm font-semibold text-white shadow-md transition hover:bg-orange-600 disabled:bg-slate-400"><ExternalLink className="h-4 w-4" />Tool Focus</button>
        </div>

        <svg className="pointer-events-none absolute left-0 top-0 h-[1000px] w-[2400px]">{renderEdges()}</svg>

        {nodes.map((node) => {
          const Icon = ICON_MAP[node.icon] || Settings;
          const selected = selectedNodeId === node.id;
          const complete = isCompleted(node.id);
          const ready = isReady(node.id);

          return (
            <div key={node.id} className={`absolute w-[260px] cursor-pointer rounded-xl border bg-white shadow-sm transition-all ${selected ? 'z-20 border-indigo-500 ring-4 ring-indigo-100 shadow-xl' : 'z-10 border-slate-200 hover:border-slate-300 hover:shadow-md'}`} style={{ left: node.x, top: node.y }} onMouseDown={(e) => handleMouseDown(e, node.id)} onClick={(e) => { e.stopPropagation(); setSelectedNodeId(node.id); }}>
              {complete ? <div className="absolute -right-3 -top-3 rounded-full border-2 border-white bg-emerald-500 p-1 text-white shadow-md"><CheckCircle2 className="h-4 w-4" /></div> : null}
              <div className="flex items-center justify-between rounded-t-xl border-b border-slate-100 bg-white p-3">
                <div className="flex items-center gap-2.5"><div className={`rounded-lg p-2 ${complete ? 'bg-emerald-100 text-emerald-600' : ready ? 'bg-blue-100 text-blue-600' : 'bg-slate-100 text-slate-500'}`}><Icon className="h-4 w-4" /></div><div className="text-sm font-bold tracking-tight text-slate-800">{node.label}</div></div>
                <span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase ${complete ? 'bg-emerald-50 text-emerald-700' : ready ? 'bg-indigo-50 text-indigo-700' : 'bg-slate-100 text-slate-500'}`}>{getStatusLabel(node.id)}</span>
              </div>
              <div className="rounded-b-xl bg-slate-50/60 p-3">
                <div className="mb-2 text-xs font-medium text-slate-500">{node.desc}</div>
                <div className="rounded-lg border border-slate-200 bg-white p-2.5 shadow-sm">
                  <div className="mb-2 flex items-center gap-2 rounded bg-slate-50 px-2 py-1 text-[10px] font-mono text-slate-500"><Terminal className="h-3 w-3" />{node.id}</div>
                  <button onClick={(e) => { e.stopPropagation(); openToolView(node); }} disabled={!ready} className={`flex w-full items-center justify-center gap-1.5 rounded-md py-2 text-xs font-semibold transition ${complete ? 'border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100' : ready ? 'bg-orange-500 text-white hover:bg-orange-600' : 'cursor-not-allowed bg-slate-200 text-slate-500'}`}>{complete ? 'Focus (Completed)' : 'Open Focus Mode'}</button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className={`z-20 flex flex-col border-l border-slate-200 bg-white shadow-2xl transition-all duration-300 ${selectedNode && showPanel ? 'w-[430px]' : 'w-0 overflow-hidden border-none'}`}>
        {selectedNode && showPanel ? (
          <>
            <div className="flex h-14 items-center justify-between border-b border-slate-200 bg-slate-50 px-4"><h2 className="flex items-center gap-2 text-sm font-bold text-slate-800"><Settings className="h-4 w-4 text-slate-500" />Node Properties</h2><button onClick={() => setSelectedNodeId(null)} className="rounded-md border border-slate-200 bg-white p-1 text-slate-400 hover:bg-slate-50 hover:text-slate-600"><X className="h-4 w-4" /></button></div>
            <div className="flex-1 space-y-4 overflow-y-auto p-5">
              <div><label className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400">Node Name</label><input readOnly value={selectedNode.label} className="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm" /></div>
              <div className="grid grid-cols-2 gap-2"><button onClick={runSelectedNode} disabled={running} className="rounded-md bg-indigo-600 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-700 disabled:bg-slate-400">Run Node</button><button onClick={() => openToolView(selectedNode)} disabled={!isReady(selectedNode.id)} className="rounded-md bg-orange-500 px-3 py-2 text-xs font-semibold text-white hover:bg-orange-600 disabled:bg-slate-400">Focus Mode</button></div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">{renderNodeWorkspace()}</div>
              <div className="rounded-xl border border-slate-200 bg-white p-4"><h4 className="mb-2 text-sm font-bold text-slate-800">Pipeline Status</h4><div className="space-y-2 text-xs">{nodes.map((n) => <button key={n.id} onClick={() => setSelectedNodeId(n.id)} className={`w-full rounded-lg border px-3 py-2 text-left ${isCompleted(n.id) ? 'border-emerald-300 bg-emerald-50' : isReady(n.id) ? 'border-indigo-300 bg-indigo-50' : 'border-slate-200 bg-slate-50'}`}><div className="font-semibold text-slate-700">{n.label}</div><div className="text-slate-500">{getStatusLabel(n.id)}</div></button>)}</div></div>
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <h4 className="mb-2 text-sm font-bold text-slate-800">Workflow Builder</h4>
                <div className="space-y-2 text-xs">
                  <div className="grid grid-cols-2 gap-2">
                    <label className="text-slate-600">
                      Node Template
                      <select className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-xs" value={workflowBuilder.templateType} onChange={(e) => setWorkflowBuilder((prev) => ({ ...prev, templateType: e.target.value }))}>
                        {NODE_TEMPLATES.map((template) => (
                          <option key={template.type} value={template.type}>{template.type}</option>
                        ))}
                      </select>
                    </label>
                    <label className="text-slate-600">
                      Placement
                      <select className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-xs" value={workflowBuilder.placement} onChange={(e) => setWorkflowBuilder((prev) => ({ ...prev, placement: e.target.value }))}>
                        <option value="parallel">parallel</option>
                        <option value="vertical">vertical</option>
                        <option value="horizontal">horizontal</option>
                      </select>
                    </label>
                  </div>
                  <button onClick={addNodeFromBuilder} className="w-full rounded-md bg-slate-800 px-2 py-2 font-semibold text-white hover:bg-slate-900">Create Node</button>

                  <div className="grid grid-cols-2 gap-2">
                    <label className="text-slate-600">
                      From
                      <select className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-xs" value={workflowBuilder.fromId} onChange={(e) => setWorkflowBuilder((prev) => ({ ...prev, fromId: e.target.value }))}>
                        {nodes.map((node) => (
                          <option key={node.id} value={node.id}>{truncate(node.label, 28)}</option>
                        ))}
                      </select>
                    </label>
                    <label className="text-slate-600">
                      To
                      <select className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-xs" value={workflowBuilder.toId} onChange={(e) => setWorkflowBuilder((prev) => ({ ...prev, toId: e.target.value }))}>
                        {nodes.map((node) => (
                          <option key={node.id} value={node.id}>{truncate(node.label, 28)}</option>
                        ))}
                      </select>
                    </label>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <label className="text-slate-600">
                      Edge Mode
                      <select className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-xs" value={workflowBuilder.edgeMode} onChange={(e) => setWorkflowBuilder((prev) => ({ ...prev, edgeMode: e.target.value }))}>
                        <option value="horizontal">horizontal</option>
                        <option value="vertical">vertical</option>
                        <option value="parallel">parallel</option>
                      </select>
                    </label>
                    <label className="text-slate-600">
                      Label
                      <input className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-xs" value={workflowBuilder.edgeLabel} onChange={(e) => setWorkflowBuilder((prev) => ({ ...prev, edgeLabel: e.target.value }))} placeholder="optional" />
                    </label>
                  </div>

                  <button onClick={connectBuilderNodes} className="w-full rounded-md bg-indigo-600 px-2 py-2 font-semibold text-white hover:bg-indigo-700">Connect Nodes</button>
                  <div className="rounded border border-slate-200 bg-slate-50 px-2 py-1.5 text-slate-600">Total nodes: {nodes.length} | Total connections: {edges.length}</div>
                </div>
              </div>

              <div className="rounded-xl border border-slate-200 bg-white p-4"><h4 className="mb-2 text-sm font-bold text-slate-800">API Call Log</h4><div className="max-h-44 space-y-2 overflow-auto text-xs">{apiLog.length ? apiLog.map((l) => <div key={l.id} className="rounded border border-slate-200 bg-slate-50 p-2"><div className="font-semibold text-slate-700">{l.endpoint}</div><div className="text-slate-500">{toLocalTime(l.at)}</div></div>) : <div className="text-slate-500">No logs yet.</div>}</div></div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
