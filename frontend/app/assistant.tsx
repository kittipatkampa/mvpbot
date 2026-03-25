"use client";

import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { useRemoteThreadListRuntime } from "@assistant-ui/react";
import { useMemo, useState } from "react";
import { Thread } from "@/components/assistant-ui/thread";
import { ThreadListSidebar } from "@/components/assistant-ui/threadlist-sidebar";
import { Separator } from "@/components/ui/separator";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from "@/components/ui/breadcrumb";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { createFastAPIAdapter } from "@/lib/fastapi-remote-adapter";
import { useFastAPIThreadRuntime } from "@/lib/fastapi-thread-runtime";

export const Assistant = () => {
  const [search, setSearch] = useState("");
  const adapter = useMemo(() => createFastAPIAdapter(search), [search]);

  const runtime = useRemoteThreadListRuntime({
    runtimeHook: function FastAPIThreadRuntimeHook() {
      return useFastAPIThreadRuntime();
    },
    adapter,
    allowNesting: true,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <SidebarProvider>
        <div className="flex h-dvh w-full pr-0.5">
          <ThreadListSidebar search={search} onSearchChange={setSearch} />
          <SidebarInset>
            <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
              <SidebarTrigger />
              <Separator orientation="vertical" className="mr-2 h-4" />
              <Breadcrumb>
                <BreadcrumbList>
                  <BreadcrumbItem>
                    <BreadcrumbPage>MVP Assistant (LangGraph + FastAPI)</BreadcrumbPage>
                  </BreadcrumbItem>
                </BreadcrumbList>
              </Breadcrumb>
            </header>
            <div className="flex-1 overflow-hidden">
              <Thread />
            </div>
          </SidebarInset>
        </div>
      </SidebarProvider>
    </AssistantRuntimeProvider>
  );
};
