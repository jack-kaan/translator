import {
  detectLanguage,
  extractCitation,
  extractTextFromUpload,
  hashText,
  inferMetadata,
  makeId,
  splitSentences,
  stripHtml,
  truncate,
} from '../core/utils.js';
import { createInitialResearchQuestionDraft } from '../state/paperStore.js';

const ok = (message, payload = {}) => ({ ok: true, message, ...payload });
const fail = (message) => ({ ok: false, message });

const checkBlockedPage = (text = '') => /login|sign in|access denied|captcha|forbidden/i.test(text);

export const runReferenceInputExecutor = async ({
  referenceForm,
  apiConfig,
  apiCall,
  createRuntimeToken,
  nodeIds,
}) => {
  const hasUpload = referenceForm.sourceType === 'upload' && referenceForm.file;
  const hasUrl = referenceForm.sourceType === 'url' && referenceForm.sourceUrl.trim();
  const hasManual = referenceForm.manualText.trim().length > 0;

  if (!hasUpload && !hasUrl && !hasManual) {
    return fail('Upload file, provide URL, or paste manual text first.');
  }

  const created = await apiCall('POST /api/projects/{projectId}/references', {
    projectId: apiConfig.projectId,
    provider: apiConfig.provider,
    runtimeToken: createRuntimeToken(),
  });
  if (!created.ok) return fail('Reference source initialization API failed.');

  let rawText = '';
  const notices = [];

  if (hasUpload) {
    const name = referenceForm.file.name || '';
    const uploaded = await extractTextFromUpload(referenceForm.file);
    rawText = uploaded.text || '';
    if (uploaded.mode !== 'text') {
      notices.push('Binary upload fallback used. Connect backend extractor for full fidelity.');
    }

    const uploadedResponse = await apiCall('POST /api/projects/{projectId}/references/{refId}/upload', {
      filename: name,
      runtimeToken: createRuntimeToken(),
    });
    if (!uploadedResponse.ok) notices.push('Upload endpoint call failed, local parse only.');
  }

  if (!rawText && hasUrl) {
    try {
      const response = await fetch(referenceForm.sourceUrl, { cache: 'no-cache' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const contentType = response.headers.get('content-type') || '';
      const body = await response.text();
      if (checkBlockedPage(body)) throw new Error('blocked page');

      rawText = contentType.includes('text/html') ? stripHtml(body) : body;
      const fetched = await apiCall('POST /api/projects/{projectId}/references/{refId}/fetch-url', {
        sourceUrl: referenceForm.sourceUrl,
        runtimeToken: createRuntimeToken(),
      });
      if (!fetched.ok) notices.push('URL fetch endpoint call failed, local parse only.');
    } catch (_error) {
      notices.push('URL fetch failed. Use upload/manual fallback.');
    }
  }

  if (hasManual) {
    rawText = `${rawText}\n\n${referenceForm.manualText}`.trim();
  }

  if (!rawText.trim()) {
    return fail('No readable text extracted.');
  }

  const meta = inferMetadata(rawText);
  const doc = {
    id: makeId('ref'),
    projectId: apiConfig.projectId,
    sourceType: referenceForm.sourceType,
    sourceUrl: referenceForm.sourceUrl,
    fileHash: hashText(rawText),
    title: referenceForm.title || meta.title,
    authors: referenceForm.authors || meta.authors,
    year: referenceForm.year || meta.year,
    journal: referenceForm.journal || meta.journal,
    doi: referenceForm.doi || meta.doi,
    rawText,
    extractedAt: new Date().toISOString(),
    languageDetected: detectLanguage(rawText),
    recommendationCitation: `${(referenceForm.authors || meta.authors || 'Unknown').trim()} (${referenceForm.year || meta.year || 'n.d.'}). ${referenceForm.title || meta.title}`,
  };

  const message = notices.length
    ? `Reference Input Node completed. ${notices.join(' ')}`
    : 'Reference Input Node completed.';
  return ok(message, {
    referenceDocument: doc,
    nextNodeId: nodeIds.RAW,
  });
};

export const runRawTranslateExecutor = async ({
  referenceDocument,
  apiConfig,
  apiCall,
  createRuntimeToken,
  nodeIds,
}) => {
  if (!referenceDocument) {
    return fail('Reference document is required first.');
  }

  const translated = await apiCall('POST /api/references/{refId}/translate', {
    refId: referenceDocument.id,
    targetLanguage: apiConfig.targetLanguage,
    provider: apiConfig.provider,
    runtimeToken: createRuntimeToken(),
  });
  if (!translated.ok) return fail('Raw translation API failed.');

  return ok('Raw Translate Node completed.', {
    translatedText: referenceDocument.rawText,
    nextNodeId: nodeIds.NORM,
  });
};

export const runSentenceNormalizationExecutor = async ({
  translatedText,
  referenceDocument,
  apiCall,
  createRuntimeToken,
  nodeIds,
}) => {
  const source = translatedText || referenceDocument?.rawText || '';
  if (!source.trim()) {
    return fail('No source text to normalize.');
  }

  const extracted = await apiCall('POST /api/references/{refId}/sentences/extract', {
    refId: referenceDocument?.id,
    runtimeToken: createRuntimeToken(),
  });
  if (!extracted.ok) return fail('Sentence extraction API failed.');

  let cursor = 0;
  const units = splitSentences(source).map((sentence, idx) => {
    const start = source.indexOf(sentence, cursor);
    const safeStart = start >= 0 ? start : cursor;
    const safeEnd = safeStart + sentence.length;
    cursor = safeEnd;

    return {
      id: makeId('sentence'),
      docId: referenceDocument?.id || 'n/a',
      nodeId: nodeIds.NORM,
      paragraphId: `p-${Math.floor(idx / 8)}`,
      index: idx,
      rawText: sentence,
      translatedText: sentence,
      startOffset: safeStart,
      endOffset: safeEnd,
      citationSpan: extractCitation(sentence),
      highlighted: false,
      note: '',
    };
  });

  if (!units.length) return fail('No sentence units extracted.');

  return ok(`Sentence Normalization Node completed (${units.length} units).`, {
    sentenceUnits: units,
    nextNodeId: nodeIds.EXTRACT,
  });
};

export const runExtractExecutor = async ({
  sentenceUnits,
  sentenceArtifacts,
  categoryBucket,
  apiCall,
  createRuntimeToken,
  nodeIds,
}) => {
  if (!sentenceUnits.length) {
    return fail('Run Sentence Normalization first.');
  }

  const synced = await apiCall('POST /api/projects/{projectId}/nodes/{nodeId}/sentences/highlight', {
    nodeId: nodeIds.EXTRACT,
    runtimeToken: createRuntimeToken(),
  });
  if (!synced.ok) return fail('Extract/highlight sync API failed.');

  if (sentenceArtifacts.length) {
    return ok('Extract node synced with current artifact edits.', { bootstrapArtifacts: [] });
  }

  const targets = sentenceUnits.slice(0, Math.min(3, sentenceUnits.length));
  const bootstrapArtifacts = targets.flatMap((s) => [
    {
      id: makeId('artifact'),
      nodeId: nodeIds.EXTRACT,
      type: 'highlight',
      sourceSentenceIds: [s.id],
      abstractText: '',
      tag: 'amber',
      confidence: 1,
    },
    {
      id: makeId('artifact'),
      nodeId: nodeIds.EXTRACT,
      type: 'category',
      sourceSentenceIds: [s.id],
      abstractText: '',
      tag: categoryBucket,
      confidence: 0.9,
    },
  ]);

  return ok(`Extract artifacts bootstrapped from ${targets.length} sentence block(s).`, {
    bootstrapArtifacts,
  });
};

export const buildTheoryBackgroundExecutor = async ({
  sentenceArtifacts,
  sentenceUnits,
  apiCall,
  createRuntimeToken,
  nodeIds,
}) => {
  if (!sentenceArtifacts.length) {
    return fail('Need extract artifacts before theory build.');
  }

  const built = await apiCall('POST /api/projects/{projectId}/nodes/{nodeId}/theory/build', {
    nodeId: nodeIds.THEORY,
    runtimeToken: createRuntimeToken(),
  });
  if (!built.ok) return fail('Theory builder API failed.');

  const categoryMap = {};
  sentenceArtifacts
    .filter((a) => a.type === 'category')
    .forEach((a) => {
      const key = a.tag || 'uncategorized';
      if (!categoryMap[key]) categoryMap[key] = [];
      categoryMap[key].push(...a.sourceSentenceIds);
    });

  Object.keys(categoryMap).forEach((key) => {
    categoryMap[key] = [...new Set(categoryMap[key])];
  });

  const evidenceLinks = [
    ...new Set(
      sentenceArtifacts
        .filter((a) => ['highlight', 'snippet', 'abstract', 'category', 'merged'].includes(a.type))
        .flatMap((a) => a.sourceSentenceIds),
    ),
  ];

  const concepts = Object.keys(categoryMap);
  const evidenceSnapshots = evidenceLinks.slice(0, 8).map((sid) => {
    const row = sentenceUnits.find((s) => s.id === sid);
    return row ? `- [${sid}] ${truncate(row.translatedText, 90)}` : `- [${sid}]`;
  });

  const draftText = [
    'Theoretical Background Draft',
    '',
    ...concepts.map((c, i) => `${i + 1}. ${c} (${(categoryMap[c] || []).length} evidence sentence(s))`),
    '',
    'Evidence Snapshots',
    ...evidenceSnapshots,
  ].join('\n');

  return ok('Theoretical Background Builder Node completed.', {
    theoryBackground: {
      id: makeId('theory'),
      nodeId: nodeIds.THEORY,
      concepts,
      categoryMap,
      evidenceLinks,
      draftText,
      revisionHistory: [
        {
          id: makeId('rev'),
          at: new Date().toISOString(),
          by: 'system',
          note: 'auto build',
        },
      ],
    },
    nextNodeId: nodeIds.QUESTION,
  });
};

export const buildAutoQuestionsExecutor = async ({
  theoryBackground,
  apiCall,
  createRuntimeToken,
  nodeIds,
}) => {
  if (!theoryBackground) {
    return fail('Need theory background first.');
  }

  const generated = await apiCall('POST /api/projects/{projectId}/nodes/{nodeId}/research-questions', {
    nodeId: nodeIds.QUESTION,
    runtimeToken: createRuntimeToken(),
  });
  if (!generated.ok) return fail('Research-question generation API failed.');

  const base = (theoryBackground.concepts || []).slice(0, 4);
  const questions =
    base.length > 0
      ? base.map((concept, idx) => ({
          id: makeId('rq'),
          text: `${idx + 1}. How does ${concept} explain the core research phenomenon?`,
        }))
      : [
          {
            id: makeId('rq'),
            text: '1. What conceptual mechanism best explains the target phenomenon?',
          },
        ];

  if (questions.length < 3) {
    questions.push({
      id: makeId('rq'),
      text: '2. Which contextual factors moderate the observed relationships?',
    });
    questions.push({
      id: makeId('rq'),
      text: '3. What evidence is required to validate the proposed explanation?',
    });
  }

  questions.push({
    id: makeId('rq'),
    text: `${questions.length + 1}. Which methodology is most defensible for testing the above assumptions?`,
  });

  const finalList = questions.slice(0, 5);
  const nextDraft = {
    ...createInitialResearchQuestionDraft(nodeIds.QUESTION),
    id: makeId('rqdraft'),
    questions: finalList,
    rationaleRefs: (theoryBackground.evidenceLinks || []).slice(0, 5),
    theorySupportIds: (theoryBackground.evidenceLinks || []).slice(0, 5),
  };

  return ok('Research Question Generator Node created 3-5 candidates.', {
    researchQuestionDraft: nextDraft,
    nextTab: 'review',
  });
};

export const buildMethodologyExecutor = async ({
  readyMethod,
  researchQuestionDraft,
  theoryBackground,
  methodologyContext,
  evidenceCount,
  apiCall,
  createRuntimeToken,
  nodeIds,
}) => {
  if (!readyMethod) {
    return fail('Methodology node locked. Need approved RQ + category artifacts + evidence links >= 3.');
  }

  const seeded = await apiCall('POST /api/projects/{projectId}/nodes/{nodeId}/methodology/seed', {
    nodeId: nodeIds.METHOD,
    runtimeToken: createRuntimeToken(),
  });
  if (!seeded.ok) return fail('Methodology seed API failed.');

  const selectedRQs = (researchQuestionDraft.questions || []).filter((q) =>
    (researchQuestionDraft.selectedQuestionIds || []).includes(q.id),
  );

  const draft = [
    'Methodology Draft',
    '',
    'Selected Research Questions',
    ...selectedRQs.map((q) => `- ${q.text}`),
    '',
    `Template: ${methodologyContext.methodTemplateType}`,
    `Required Data Sources: ${methodologyContext.requiredDataSources || '(pending)'}`,
    '',
    'Analytic Plan',
    methodologyContext.analyticPlan || '(pending)',
    '',
    'Validity Checks',
    methodologyContext.validityChecks || '(pending)',
    '',
    `Evidence Links (${evidenceCount})`,
    ...(theoryBackground?.evidenceLinks || []).slice(0, 10).map((id) => `- ${id}`),
  ].join('\n');

  return ok('Methodology Node completed.', {
    methodologyContext: {
      ...methodologyContext,
      id: makeId('method'),
      selectedRQs,
      draftText: draft,
      riskLog: [
        'Verify traceability from evidence to selected method.',
        'Check data access constraints and sample bias risks.',
        'Validate internal/external validity checks before final writeup.',
      ],
    },
  });
};
