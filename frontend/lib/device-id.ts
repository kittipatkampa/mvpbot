const DEVICE_ID_KEY = "mvpbot_device_id";
const ACTIVE_DEVICE_ID_KEY = "mvpbot_active_device_id";
const TEST_USERS_KEY = "mvpbot_test_users";

function newUuid(): string {
  return typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export function getOrCreateDeviceId(): string {
  if (typeof window === "undefined") return ""; // SSR guard
  let id = localStorage.getItem(DEVICE_ID_KEY);
  if (!id) {
    id = newUuid();
    localStorage.setItem(DEVICE_ID_KEY, id);
  }
  return id;
}

// ---------------------------------------------------------------------------
// Multi-user test helpers
// ---------------------------------------------------------------------------

export type TestUser = {
  name: string;
  deviceId: string;
};

export function listTestUsers(): TestUser[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(TEST_USERS_KEY);
    return raw ? (JSON.parse(raw) as TestUser[]) : [];
  } catch {
    return [];
  }
}

export function addTestUser(name: string): TestUser {
  const users = listTestUsers();
  const existing = users.find(
    (u) => u.name.toLowerCase() === name.trim().toLowerCase(),
  );
  if (existing) return existing;
  const user: TestUser = { name: name.trim(), deviceId: newUuid() };
  localStorage.setItem(TEST_USERS_KEY, JSON.stringify([...users, user]));
  return user;
}

export function removeTestUser(deviceId: string): void {
  if (typeof window === "undefined") return;
  const users = listTestUsers().filter((u) => u.deviceId !== deviceId);
  localStorage.setItem(TEST_USERS_KEY, JSON.stringify(users));
  // If we just removed the active user, fall back to the default
  if (getActiveDeviceId() === deviceId) {
    localStorage.removeItem(ACTIVE_DEVICE_ID_KEY);
  }
}

/**
 * Returns the currently active device ID.
 * Falls back to the legacy single-user key so existing sessions are unaffected.
 */
export function getActiveDeviceId(): string {
  if (typeof window === "undefined") return "";
  return (
    localStorage.getItem(ACTIVE_DEVICE_ID_KEY) || getOrCreateDeviceId()
  );
}

export function setActiveDeviceId(deviceId: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(ACTIVE_DEVICE_ID_KEY, deviceId);
}

/** Name of the currently active test user, or null if using the default device. */
export function getActiveUserName(): string | null {
  if (typeof window === "undefined") return null;
  const activeId = localStorage.getItem(ACTIVE_DEVICE_ID_KEY);
  if (!activeId) return null;
  const user = listTestUsers().find((u) => u.deviceId === activeId);
  return user?.name ?? null;
}
