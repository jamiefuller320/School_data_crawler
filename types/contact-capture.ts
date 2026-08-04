/**
 * TypeScript mirror of contact capture sidecars for Comparison-tool integration.
 */

export type ContactRole =
  | "headteacher"
  | "senco"
  | "office"
  | "admissions"
  | "safeguarding"
  | "governor"
  | "other";

export type ContactSourceType =
  | "gias"
  | "dfe-index"
  | "school-website"
  | "school-document"
  | "other";

export interface ContactEntry {
  role: ContactRole;
  sourceType: ContactSourceType;
  sourceUrl: string;
  capturedAt: string;
  name?: string | null;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  town?: string | null;
  postcode?: string | null;
  label?: string | null;
}

export interface ContactCaptureRecord {
  urn: string;
  name: string;
  assessedAt: string;
  engineVersion: string;
  contacts: ContactEntry[];
  captureNotes?: string[];
}

export interface ContactCaptureIndex {
  generatedAt: string;
  engineVersion: string;
  schoolCount: number;
  records: ContactCaptureRecord[];
  stats?: Record<string, unknown>;
}

/** Optional extension fields on SchoolRecord when merged. */
export interface ContactCaptureFields {
  contactCapture?: ContactCaptureRecord | null;
  contactCaptureEnrichedAt?: string | null;
}
