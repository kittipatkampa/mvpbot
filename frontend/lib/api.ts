const API_BASE =
  typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL
    ? process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, "")
    : "http://localhost:8000";

export type ApiMessage = {
  id: string;
  role: string;
  content: string;
  reasoning: string | null;
  created_at: string;
};

export type ApiThread = {
  id: string;
  title: string;
  updated_at: string;
  archived: boolean;
};

export async function createThread(clientId?: string): Promise<string> {
  const r = await fetch(`${API_BASE}/api/threads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(clientId ? { id: clientId } : {}),
  });
  if (r.status === 409 && clientId) return clientId;
  if (!r.ok) throw new Error(`createThread: ${r.status}`);
  const j = (await r.json()) as { thread_id: string };
  return j.thread_id;
}

export async function listThreads(
  q?: string,
  includeArchived = true,
): Promise<ApiThread[]> {
  const u = new URL(`${API_BASE}/api/threads`);
  if (q) u.searchParams.set("q", q);
  if (includeArchived) u.searchParams.set("include_archived", "true");
  const r = await fetch(u.toString());
  if (!r.ok) throw new Error(`listThreads: ${r.status}`);
  return r.json();
}

export async function getThread(threadId: string): Promise<ApiThread> {
  const r = await fetch(`${API_BASE}/api/threads/${threadId}`);
  if (!r.ok) throw new Error(`getThread: ${r.status}`);
  return r.json();
}

export async function patchThread(
  threadId: string,
  body: { title?: string; archived?: boolean },
): Promise<void> {
  const r = await fetch(`${API_BASE}/api/threads/${threadId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`patchThread: ${r.status}`);
}

export async function deleteThread(threadId: string): Promise<void> {
  const r = await fetch(`${API_BASE}/api/threads/${threadId}`, {
    method: "DELETE",
  });
  if (!r.ok) throw new Error(`deleteThread: ${r.status}`);
}

export async function getMessages(threadId: string): Promise<ApiMessage[]> {
  const r = await fetch(`${API_BASE}/api/threads/${threadId}/messages`);
  if (!r.ok) throw new Error(`getMessages: ${r.status}`);
  return r.json();
}

export async function postChatStream(
  threadId: string,
  message: string,
  signal?: AbortSignal,
  options?: { regenerate?: boolean },
): Promise<Response> {
  return fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      thread_id: threadId,
      message,
      regenerate: options?.regenerate ?? false,
    }),
    signal,
  });
}

export { API_BASE };
