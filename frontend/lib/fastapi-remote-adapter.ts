import type { RemoteThreadListAdapter } from "@assistant-ui/react";
import {
  createThread,
  deleteThread,
  getThread,
  listThreads,
  patchThread,
} from "@/lib/api";

/**
 * assistant-ui RemoteThreadListAdapter backed by the FastAPI service.
 */
export function createFastAPIAdapter(searchQuery: string): RemoteThreadListAdapter {
  return {
    async list() {
      const rows = await listThreads(searchQuery || undefined, true);
      return {
        threads: rows.map((t) => ({
          status: t.archived ? "archived" : "regular",
          remoteId: t.id,
          title: t.title,
          externalId: undefined,
        })),
      };
    },

    async rename(remoteId, newTitle) {
      await patchThread(remoteId, { title: newTitle });
    },

    async archive(remoteId) {
      await patchThread(remoteId, { archived: true });
    },

    async unarchive(remoteId) {
      await patchThread(remoteId, { archived: false });
    },

    async delete(remoteId) {
      await deleteThread(remoteId);
    },

    async initialize(threadId) {
      const id = await createThread(threadId);
      return { remoteId: id, externalId: undefined };
    },

    async generateTitle() {
      return Promise.resolve(new ReadableStream() as unknown as ReadableStream);
    },

    async fetch(threadId) {
      const t = await getThread(threadId);
      return {
        status: t.archived ? "archived" : "regular",
        remoteId: t.id,
        title: t.title,
        externalId: undefined,
      };
    },
  };
}
