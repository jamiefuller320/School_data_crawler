/**
 * TypeScript mirror of qualitative capture sidecars for Comparison-tool integration.
 * Copy or import into `src/lib/types.ts` when wiring the UI.
 */

export type QualitativeSourceType =
  | "school-website"
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
  signals: QualitativeSignal[];
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
