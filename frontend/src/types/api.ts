export type HealthResponse = Record<string, string>;

export type WorkflowResponse = {
  success: boolean;
  message: string;
  run_id: string;
  candidate_name?: string | null;
  recipient_email?: string | null;
  company?: string | null;
  role?: string | null;
  pdf_path?: string | null;
  pdf_download_url?: string | null;
  outputs?: Record<string, string>;
  agent1_output?: Record<string, unknown>;
  agent2_output?: Record<string, unknown>;
  agent3_output?: Record<string, unknown>;
};

/** Shape returned by GET /downloads/{run_id} */
export type DownloadFile = {
  /** e.g. "interview_pack.pdf", "agent1_output.json" */
  filename: string;
  /** Public URL to fetch/download the file */
  url: string;
  /** MIME type, e.g. "application/pdf" or "application/json" */
  content_type?: string | null;
  /** File size in bytes, if provided */
  size_bytes?: number | null;
};

export type DownloadResponse = {
  run_id: string;
  /** List of downloadable files for this run */
  files?: DownloadFile[] | null;
  /** Direct PDF download URL (may be top-level instead of inside files[]) */
  pdf_url?: string | null;
  /** Any additional metadata the backend returns */
  [key: string]: unknown;
};

export type WorkflowFormState = {
  resume: File | null;
  jd: File | null;
  interviewRounds: string[];
  customRound: string;
  answerLength: 'answer_small' | 'answer_medium' | 'answer_large';
  company: string;
  role: string;
  sendEmail: boolean;
  toEmail: string;
};
