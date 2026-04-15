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
