/**
 * TypeScript mirror of qualitative capture sidecars for Comparison-tool integration.
 * Copy or import into `src/lib/types.ts` when wiring the UI.
 */

export type QualitativeSourceType =
  | "school-website"
  | "school-document"
  | "local-news"
  | "social-media"
  | "other";

export type QualitativeSubjectArea =
  | "curriculum"
  | "enrichment"
  | "ethos"
  | "behaviour"
  | "send"
  | "community";

/** Verifiable excerpt with footnote URL — mirrors InspectionQuote. */
export interface QualitativeSignal {
  text: string;
  sourceUrl: string;
  sourceType: QualitativeSourceType;
  capturedAt: string;
  pageTitle?: string | null;
  section?: string | null;
}

/** Value judgement for one subject area with supporting evidence. */
export interface SubjectAreaAssessment {
  area: QualitativeSubjectArea;
  /** 0–100 strength-of-evidence / richness score (not a league-table rank). */
  score: number;
  /** 0–1 confidence based on source diversity and excerpt quality. */
  confidence: number;
  summary: string;
  themes: string[];
  /** Concrete listable items: clubs, subjects, wraparound care, etc. */
  offerings?: string[];
  signals: QualitativeSignal[];
}

export type DocumentInventoryStatus =
  | "discovered"
  | "extracted"
  | "unsupported_format"
  | "failed"
  | "extract_failed"
  | "empty";

/** One downloadable file discovered on a school website. */
export interface DocumentInventoryItem {
  url: string;
  label: string;
  format: string;
  status: DocumentInventoryStatus;
  foundOn?: string;
  pageCount?: string;
  charCount?: string;
  listItems?: string;
}

/** Per-school qualitative capture sidecar (keyed by URN). */
export interface QualitativeCaptureRecord {
  urn: string;
  name: string;
  assessedAt: string;
  engineVersion: string;
  sourcesScanned: number;
  sourceTypes?: QualitativeSourceType[];
  areas: SubjectAreaAssessment[];
  captureNotes?: string[];
  documentsDiscovered?: number;
  documentsExtracted?: number;
  documentInventory?: DocumentInventoryItem[];
}

export interface QualitativeCaptureIndex {
  generatedAt: string;
  engineVersion: string;
  schoolCount: number;
  records: QualitativeCaptureRecord[];
  stats?: Record<string, unknown>;
}

/** Optional extension fields on SchoolRecord when merged. */
export interface QualitativeCaptureFields {
  qualitativeCapture?: QualitativeCaptureRecord | null;
  qualitativeCaptureEnrichedAt?: string | null;
}
