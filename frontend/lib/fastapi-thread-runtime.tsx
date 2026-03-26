"use client";

import { useAui, useExternalStoreRuntime } from "@assistant-ui/react";
import type { AppendMessage, ThreadMessageLike } from "@assistant-ui/react";
import type { StartRunConfig } from "@assistant-ui/core";
import { useAuiState } from "@assistant-ui/store";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_BASE, getMessages, postChatStream } from "@/lib/api";
import type { ApiMessage } from "@/lib/api";

function appendMessageToText(message: AppendMessage): string {
  const c = message.content;
  if (typeof c === "string") return c;
  const textParts = c.filter(
    (p): p is { type: "text"; text: string } => p.type === "text",
  );
  return textParts.map((p) => p.text).join("\n\n");
}

function textFromThreadLike(m: ThreadMessageLike): string {
  const c = m.content;
  if (typeof c === "string") return c;
  const textParts = c.filter(
    (p): p is { type: "text"; text: string } => p.type === "text",
  );
  return textParts.map((p) => p.text).join("\n\n");
}

function apiMessageToThreadLike(m: ApiMessage): ThreadMessageLike {
  if (m.role === "user") {
    return {
      role: "user",
      content: [{ type: "text", text: m.content }],
      id: m.id,
    };
  }
  const parts: { type: "reasoning" | "text"; text: string }[] = [];
  if (m.reasoning) parts.push({ type: "reasoning", text: m.reasoning });
  parts.push({ type: "text", text: m.content });
  return {
    role: "assistant",
    content: parts,
    id: m.id,
  } satisfies ThreadMessageLike;
}

async function* parseSSE(
  stream: ReadableStream<Uint8Array> | null,
): AsyncGenerator<Record<string, unknown>> {
  if (!stream) return;
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = buffer.replace(/\r\n/g, "\n");
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      for (const line of block.split("\n")) {
        if (line.startsWith("data: ")) {
          const raw = line.slice(6);
          try {
            yield JSON.parse(raw) as Record<string, unknown>;
          } catch {
            /* ignore */
          }
        }
      }
    }
  }
  // Trailing event without final blank line
  for (const line of buffer.split("\n")) {
    if (line.startsWith("data: ")) {
      const raw = line.slice(6);
      try {
        yield JSON.parse(raw) as Record<string, unknown>;
      } catch {
        /* ignore */
      }
    }
  }
}

/**
 * Per-thread external store: loads messages from FastAPI, streams SSE for new replies.
 */
export function useFastAPIThreadRuntime() {
  const aui = useAui();
  const remoteId = useAuiState((s) => s.threadListItem.remoteId);
  const remoteIdRef = useRef(remoteId);
  remoteIdRef.current = remoteId;

  const [messages, setMessages] = useState<readonly ThreadMessageLike[]>([]);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  const [isRunning, setIsRunning] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  // Tracks whether we're in the middle of sending the first message on a new thread.
  // When true, we skip the getMessages fetch that fires when remoteId changes, to
  // avoid overwriting the optimistic user+assistant messages we already set.
  const skipNextLoadRef = useRef(false);

  useEffect(() => {
    if (!remoteId) {
      setMessages([]);
      return;
    }
    if (skipNextLoadRef.current) {
      skipNextLoadRef.current = false;
      return;
    }
    let cancelled = false;
    setIsLoading(true);
    void getMessages(remoteId)
      .then((rows) => {
        if (cancelled) return;
        setMessages(rows.map(apiMessageToThreadLike));
      })
      .catch(() => {
        if (!cancelled) setMessages([]);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [remoteId]);

  const streamAssistantReply = useCallback(
    async (
      tid: string,
      userText: string,
      assistantId: string,
      options: { regenerate: boolean; onAbortTrim: (prev: readonly ThreadMessageLike[]) => readonly ThreadMessageLike[] },
    ) => {
      setIsRunning(true);
      abortRef.current = new AbortController();

      try {
        const res = await postChatStream(
          tid,
          userText,
          abortRef.current.signal,
          { regenerate: options.regenerate },
        );
        if (!res.ok) {
          throw new Error(`Chat failed: ${res.status}`);
        }
        let reasoning = "";
        let answer = "";
        for await (const ev of parseSSE(res.body)) {
          const type = ev.type as string | undefined;
          if (type === "reasoning") {
            reasoning += String((ev as { content?: string }).content ?? "");
          } else if (type === "token") {
            answer += String((ev as { content?: string }).content ?? "");
          } else if (type === "error") {
            throw new Error(String((ev as { message?: string }).message ?? "error"));
          } else if (type === "done") {
            break;
          }
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.role === "assistant" && last.id === assistantId) {
              const parts: { type: "reasoning" | "text"; text: string }[] = [];
              if (reasoning) parts.push({ type: "reasoning", text: reasoning });
              parts.push({ type: "text", text: answer });
              next[next.length - 1] = {
                ...last,
                content: parts,
              };
            }
            return next;
          });
        }
      } catch (e) {
        if ((e as Error).name === "AbortError") {
          setMessages((prev) => options.onAbortTrim(prev));
          return;
        }
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last?.role === "assistant" && last.id === assistantId) {
            next[next.length - 1] = {
              ...last,
              content: [{ type: "text", text: `Error: ${(e as Error).message}` }],
            };
          }
          return next;
        });
      } finally {
        setIsRunning(false);
        abortRef.current = null;
      }
    },
    [],
  );

  const handleOutgoing = useCallback(async (message: AppendMessage) => {
    const text = appendMessageToText(message);
    if (!text.trim()) return;

    let tid =
      remoteIdRef.current ?? aui.threadListItem().getState().remoteId ?? undefined;
    if (!tid) {
      const item = aui.threadListItem().getState();
      if (item.status === "new") {
        try {
          skipNextLoadRef.current = true;
          const result = await aui.threadListItem().initialize();
          tid = result.remoteId;
        } catch (e) {
          skipNextLoadRef.current = false;
          setMessages((prev) => [
            ...prev,
            {
              role: "user",
              content: [{ type: "text", text: text.trim() }],
            },
            {
              role: "assistant",
              content: [
                {
                  type: "text",
                  text: `Could not create thread: ${(e as Error).message}. Check that the backend is running (${API_BASE}).`,
                },
              ],
              id: `err-${Date.now()}`,
            },
          ]);
          return;
        }
      }
    }
    if (!tid) {
      return;
    }
    remoteIdRef.current = tid;

    const userLike: ThreadMessageLike = {
      role: "user",
      content: [{ type: "text", text: text.trim() }],
      id: `user-${Date.now()}`,
    };
    const assistantId = `asst-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      userLike,
      {
        role: "assistant",
        content: [
          { type: "reasoning", text: "" },
          { type: "text", text: "" },
        ],
        id: assistantId,
      },
    ]);
    await streamAssistantReply(tid, text.trim(), assistantId, {
      regenerate: false,
      onAbortTrim: (prev) => prev.slice(0, -2),
    });
  }, [aui, streamAssistantReply]);

  const onNew = useCallback(
    (m: AppendMessage) => handleOutgoing(m),
    [handleOutgoing],
  );
  const onEdit = useCallback(
    (m: AppendMessage) => handleOutgoing(m),
    [handleOutgoing],
  );

  const onCancel = useCallback(async () => {
    abortRef.current?.abort();
  }, []);

  const onReload = useCallback(
    async (parentId: string | null, _config: StartRunConfig) => {
      const tid =
        remoteIdRef.current ?? aui.threadListItem().getState().remoteId ?? undefined;
      if (!tid || parentId == null) return;

      const prev = messagesRef.current;
      const idx = prev.findIndex((m) => m.id === parentId);
      if (idx === -1) return;
      const userMsg = prev[idx];
      if (userMsg.role !== "user") return;
      const userText = textFromThreadLike(userMsg);
      if (!userText.trim()) return;

      const base = prev.slice(0, idx + 1);
      const assistantId = `asst-${Date.now()}`;
      setMessages([
        ...base,
        {
          role: "assistant",
          content: [
            { type: "reasoning", text: "" },
            { type: "text", text: "" },
          ],
          id: assistantId,
        },
      ]);
      await streamAssistantReply(tid, userText.trim(), assistantId, {
        regenerate: true,
        onAbortTrim: (p) => p.slice(0, -1),
      });
    },
    [aui, streamAssistantReply],
  );

  const store = useMemo(
    () => ({
      messages,
      isRunning,
      isLoading,
      setMessages,
      onNew,
      onEdit,
      onReload,
      onCancel,
      convertMessage: (m: ThreadMessageLike) => m,
      unstable_capabilities: { copy: true } as const,
    }),
    [messages, isRunning, isLoading, onNew, onEdit, onReload, onCancel],
  );

  return useExternalStoreRuntime(store);
}
