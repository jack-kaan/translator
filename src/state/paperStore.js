export const createInitialResearchQuestionDraft = (nodeId = 'n-rq-generator') => ({
  id: null,
  nodeId,
  questions: [],
  selectedQuestionIds: [],
  rationaleRefs: [],
  theorySupportIds: [],
});

export const createInitialMethodologyContext = (
  nodeId = 'n-methodology',
  methodTemplateType = 'qualitative',
) => ({
  id: null,
  nodeId,
  selectedRQs: [],
  methodTemplateType,
  requiredDataSources: '',
  analyticPlan: '',
  validityChecks: '',
  riskLog: [],
  draftText: '',
});

export const createArtifactIndex = (artifacts = []) => {
  const map = {};
  artifacts.forEach((artifact) => {
    (artifact.sourceSentenceIds || []).forEach((sentenceId) => {
      if (!map[sentenceId]) map[sentenceId] = {};
      if (!map[sentenceId][artifact.type]) map[sentenceId][artifact.type] = [];
      map[sentenceId][artifact.type].push(artifact);
    });
  });
  return map;
};

export const computePipelineStatus = ({
  nodeIds,
  referenceDocument,
  translatedText,
  sentenceUnits,
  sentenceArtifacts,
  theoryBackground,
  researchQuestionDraft,
  methodologyContext,
}) => {
  const approvedCount = (researchQuestionDraft?.selectedQuestionIds || []).length;
  const evidenceCount = (theoryBackground?.evidenceLinks || []).length;
  const categoryArtifactCount = (sentenceArtifacts || []).filter((a) => a.type === 'category').length;

  const completed = {
    [nodeIds.REF]: Boolean(referenceDocument?.rawText),
    [nodeIds.RAW]: Boolean(translatedText),
    [nodeIds.NORM]: (sentenceUnits || []).length > 0,
    [nodeIds.EXTRACT]: (sentenceArtifacts || []).length > 0,
    [nodeIds.THEORY]: Boolean(theoryBackground?.draftText),
    [nodeIds.QUESTION]: (researchQuestionDraft?.questions || []).length > 0,
    [nodeIds.METHOD]: Boolean(methodologyContext?.draftText),
  };

  const readyMethod = approvedCount > 0 && evidenceCount >= 3 && categoryArtifactCount > 0;

  const ready = {
    [nodeIds.REF]: true,
    [nodeIds.RAW]: completed[nodeIds.REF],
    [nodeIds.NORM]: completed[nodeIds.RAW] || completed[nodeIds.REF],
    [nodeIds.EXTRACT]: completed[nodeIds.NORM],
    [nodeIds.THEORY]: completed[nodeIds.EXTRACT],
    [nodeIds.QUESTION]: completed[nodeIds.THEORY],
    [nodeIds.METHOD]: readyMethod,
  };

  return {
    completed,
    ready,
    readyMethod,
    counters: {
      approvedCount,
      evidenceCount,
      categoryArtifactCount,
    },
  };
};

export const createLocksState = ({
  readyMethod,
  approvedCount,
  evidenceCount,
  categoryArtifactCount,
}) => {
  const reasons = [];
  if (approvedCount < 1) reasons.push('Need at least one approved research question');
  if (categoryArtifactCount < 1) reasons.push('Need categorized sentence artifacts');
  if (evidenceCount < 3) reasons.push('Need 3+ evidence links');

  return {
    methodology: {
      locked: !readyMethod,
      reasons,
    },
  };
};
