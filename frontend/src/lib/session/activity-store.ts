// Session-scoped activity index — safe IDs and metadata only.
// Persisted to sessionStorage; cleared on logout.

import { useCallback, useEffect, useState } from "react";

export type ActivityKind = "document" | "job" | "batch";

export type ActivityItem = {
  kind: ActivityKind;
  id: string;
  createdAt: number;
  label?: string;
  documentId?: string;
  privacyMode?: string;
  status?: string;
  downloaded?: boolean;
};

const KEY = "medvault.activity";

function read(): ActivityItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as ActivityItem[]) : [];
  } catch {
    return [];
  }
}

function write(items: ActivityItem[]) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(items));
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new Event("medvault:activity"));
}

export const activityStore = {
  all: read,
  add(item: ActivityItem) {
    const items = read();
    const idx = items.findIndex((i) => i.kind === item.kind && i.id === item.id);
    if (idx >= 0) items[idx] = { ...items[idx], ...item };
    else items.unshift(item);
    write(items.slice(0, 200));
  },
  update(kind: ActivityKind, id: string, patch: Partial<ActivityItem>) {
    const items = read();
    const idx = items.findIndex((i) => i.kind === kind && i.id === id);
    if (idx >= 0) {
      items[idx] = { ...items[idx], ...patch };
      write(items);
    }
  },
  clear() {
    sessionStorage.removeItem(KEY);
    window.dispatchEvent(new Event("medvault:activity"));
  },
};

export function useActivity() {
  const [items, setItems] = useState<ActivityItem[]>([]);
  useEffect(() => {
    setItems(read());
    const h = () => setItems(read());
    window.addEventListener("medvault:activity", h);
    return () => window.removeEventListener("medvault:activity", h);
  }, []);
  const add = useCallback((i: ActivityItem) => activityStore.add(i), []);
  const update = useCallback(
    (k: ActivityKind, id: string, p: Partial<ActivityItem>) => activityStore.update(k, id, p),
    [],
  );
  return { items, add, update };
}
