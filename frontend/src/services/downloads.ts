/**
 * Downloads service
 *
 * Wraps the GET /downloads/{run_id} endpoint.
 * Equivalent curl:
 *   curl -X GET 'http://127.0.0.1:8000/downloads/{run_id}' -H 'accept: application/json'
 */
import { API_BASE_URL } from '../lib/api';
import type { DownloadResponse } from '../types/api';

/**
 * Fetch the downloadable artefacts for a completed workflow run.
 *
 * @param runId - The run ID returned by the workflow endpoint (e.g. "20260511_185209")
 * @returns Parsed DownloadResponse from the backend
 * @throws Error with a human-readable message if the request fails
 */
export async function getDownloads(runId: string): Promise<DownloadResponse> {
  if (!runId || !runId.trim()) {
    throw new Error('A valid run ID is required to fetch downloads.');
  }

  const url = `${API_BASE_URL}/downloads/${encodeURIComponent(runId.trim())}`;

  const response = await fetch(url, {
    method: 'GET',
    headers: { accept: 'application/json' },
  });

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = payload?.detail || payload?.message || 'Failed to fetch downloads';
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }

  return payload as DownloadResponse;
}
