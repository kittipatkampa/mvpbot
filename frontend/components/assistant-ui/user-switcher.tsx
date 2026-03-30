"use client";

import * as React from "react";
import { Check, ChevronDown, Plus, Trash2, UserRound } from "lucide-react";
import {
  addTestUser,
  getActiveDeviceId,
  getActiveUserName,
  listTestUsers,
  removeTestUser,
  setActiveDeviceId,
  type TestUser,
} from "@/lib/device-id";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export function UserSwitcher() {
  const [open, setOpen] = React.useState(false);
  const [users, setUsers] = React.useState<TestUser[]>([]);
  const [activeName, setActiveName] = React.useState<string | null>(null);
  const [newName, setNewName] = React.useState("");
  const panelRef = React.useRef<HTMLDivElement>(null);

  // Hydrate from localStorage on mount (client-only)
  React.useEffect(() => {
    setUsers(listTestUsers());
    setActiveName(getActiveUserName());
  }, []);

  // Close panel when clicking outside
  React.useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  function switchUser(user: TestUser) {
    setActiveDeviceId(user.deviceId);
    setActiveName(user.name);
    setOpen(false);
    window.location.reload();
  }

  function switchToDefault() {
    localStorage.removeItem("mvpbot_active_device_id");
    setActiveName(null);
    setOpen(false);
    window.location.reload();
  }

  function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = newName.trim();
    if (!trimmed) return;
    const user = addTestUser(trimmed);
    setUsers(listTestUsers());
    setNewName("");
    switchUser(user);
  }

  function handleRemove(e: React.MouseEvent, deviceId: string) {
    e.stopPropagation();
    removeTestUser(deviceId);
    setUsers(listTestUsers());
    if (getActiveDeviceId() !== deviceId) return;
    // Removed the active user — reload as default
    setActiveName(null);
    window.location.reload();
  }

  const label = activeName ?? "Default user";

  return (
    <div ref={panelRef} className="relative w-full">
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-sm hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
      >
        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
          <UserRound className="size-4" />
        </div>
        <div className="flex min-w-0 flex-1 flex-col items-start gap-0.5 leading-none">
          <span className="text-xs text-muted-foreground">Testing as</span>
          <span className="max-w-[120px] truncate font-semibold">{label}</span>
        </div>
        <ChevronDown
          className={cn(
            "size-4 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-180",
          )}
        />
      </button>

      {/* Dropdown panel */}
      {open && (
        <div className="absolute bottom-full left-0 z-50 mb-1 w-full min-w-[200px] rounded-md border bg-popover p-1 shadow-md">
          {/* Default user row */}
          <button
            type="button"
            onClick={switchToDefault}
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground"
          >
            <Check
              className={cn(
                "size-3.5 shrink-0",
                activeName === null ? "opacity-100" : "opacity-0",
              )}
            />
            <span className="truncate">Default user</span>
          </button>

          {users.length > 0 && (
            <div className="my-1 h-px bg-border" />
          )}

          {/* Test user rows */}
          {users.map((u) => (
            <div
              key={u.deviceId}
              className="group flex items-center gap-1 rounded-sm hover:bg-accent hover:text-accent-foreground"
            >
              <button
                type="button"
                onClick={() => switchUser(u)}
                className="flex flex-1 items-center gap-2 px-2 py-1.5 text-sm"
              >
                <Check
                  className={cn(
                    "size-3.5 shrink-0",
                    activeName === u.name ? "opacity-100" : "opacity-0",
                  )}
                />
                <span className="truncate">{u.name}</span>
              </button>
              <button
                type="button"
                onClick={(e) => handleRemove(e, u.deviceId)}
                title="Remove user"
                className="mr-1 rounded p-1 opacity-0 hover:text-destructive group-hover:opacity-100"
              >
                <Trash2 className="size-3.5" />
              </button>
            </div>
          ))}

          <div className="my-1 h-px bg-border" />

          {/* Add new user */}
          <form onSubmit={handleAdd} className="flex gap-1 px-1 py-1">
            <Input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="New user name…"
              className="h-7 text-xs"
            />
            <Button
              type="submit"
              size="icon"
              variant="ghost"
              className="size-7 shrink-0"
              disabled={!newName.trim()}
              title="Add user"
            >
              <Plus className="size-3.5" />
            </Button>
          </form>
        </div>
      )}
    </div>
  );
}
