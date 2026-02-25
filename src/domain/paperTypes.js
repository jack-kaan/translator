/**
 * @typedef {Object} ReferenceDocument
 * @property {string} id
 * @property {string} projectId
 * @property {'upload'|'url'} sourceType
 * @property {string} sourceUrl
 * @property {string} fileHash
 * @property {string} title
 * @property {string} authors
 * @property {string} year
 * @property {string} journal
 * @property {string} doi
 * @property {string} rawText
 * @property {string} extractedAt
 * @property {string} languageDetected
 */

/**
 * @typedef {Object} SentenceUnit
 * @property {string} id
 * @property {string} docId
 * @property {string} nodeId
 * @property {string} paragraphId
 * @property {number} index
 * @property {string} rawText
 * @property {string} translatedText
 * @property {number} startOffset
 * @property {number} endOffset
 * @property {string} citationSpan
 * @property {boolean} highlighted
 * @property {string} note
 */

/**
 * @typedef {Object} SentenceArtifact
 * @property {string} id
 * @property {string} nodeId
 * @property {'highlight'|'snippet'|'abstract'|'category'|'merged'} type
 * @property {string[]} sourceSentenceIds
 * @property {string} abstractText
 * @property {string} tag
 * @property {number} confidence
 */

/**
 * @typedef {Object} TheoryBackground
 * @property {string} id
 * @property {string} nodeId
 * @property {string[]} concepts
 * @property {Object.<string, string[]>} categoryMap
 * @property {string[]} evidenceLinks
 * @property {string} draftText
 * @property {Array<{id:string,at:string,by:string,note:string}>} revisionHistory
 */

/**
 * @typedef {Object} ResearchQuestionDraft
 * @property {string|null} id
 * @property {string} nodeId
 * @property {Array<{id:string,text:string}>} questions
 * @property {string[]} selectedQuestionIds
 * @property {string[]} rationaleRefs
 * @property {string[]} theorySupportIds
 */

/**
 * @typedef {Object} MethodologyContext
 * @property {string|null} id
 * @property {string} nodeId
 * @property {Array<{id:string,text:string}>} selectedRQs
 * @property {string} methodTemplateType
 * @property {string} requiredDataSources
 * @property {string} analyticPlan
 * @property {string} validityChecks
 * @property {string[]} riskLog
 * @property {string} draftText
 */

export {};
