import { browser } from '$app/environment';
import { get, writable } from 'svelte/store';
import { ApiException } from '$lib/api';
import {
  getNotificationUnreadCount,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead
} from '$lib/api/notifications';
import type { Notification } from '$lib/types';

type NotificationsState = {
  items: Notification[];
  unread: number;
  connected: boolean;
  loading: boolean;
  unavailable: boolean;
};

const store = writable<NotificationsState>({
  items: [],
  unread: 0,
  connected: false,
  loading: false,
  unavailable: false
});

let initialized = false;
let stream: EventSource | null = null;
let reconnectTimer: number | null = null;
let reconnectDelay = 1000;
let active = false;
let recovering = false;

function setDisconnected(unavailable = false): void {
  store.update((state) => ({ ...state, connected: false, unavailable }));
}

function isServiceUnavailable(error: unknown): boolean {
  return error instanceof ApiException && [404, 500, 502, 503].includes(error.status);
}

function clearReconnectTimer(): void {
  if (reconnectTimer !== null) {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

function scheduleReconnect(fetchImpl: typeof fetch): void {
  if (!browser || reconnectTimer !== null || !active) return;
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null;
    void openStream(fetchImpl);
  }, reconnectDelay);
  reconnectDelay = reconnectDelay === 1000 ? 2000 : reconnectDelay === 2000 ? 5000 : 10000;
}

function closeStream(): void {
  if (stream) {
    stream.close();
    stream = null;
  }
}

export const notifications = {
  subscribe: store.subscribe
};

export async function initNotifications(fetchImpl: typeof fetch = fetch): Promise<void> {
  if (!browser || initialized) return;
  initialized = true;
  store.update((state) => ({ ...state, loading: true }));

  try {
    const [list, unread] = await Promise.all([
      listNotifications(fetchImpl, { limit: 20 }),
      getNotificationUnreadCount(fetchImpl)
    ]);
    store.set({
      items: list.items,
      unread: unread.count,
      connected: false,
      loading: false,
      unavailable: false
    });
  } catch (error) {
    const unavailable = isServiceUnavailable(error);
    store.set({
      items: [],
      unread: 0,
      connected: false,
      loading: false,
      unavailable
    });
  }
}

async function probeNotifications(fetchImpl: typeof fetch): Promise<boolean> {
  try {
    await getNotificationUnreadCount(fetchImpl);
    store.update((state) => ({ ...state, unavailable: false }));
    return true;
  } catch (error) {
    if (isServiceUnavailable(error)) {
      setDisconnected(true);
      return false;
    }

    throw error;
  }
}

async function recoverStream(fetchImpl: typeof fetch): Promise<void> {
  if (recovering || !active) return;
  recovering = true;

  try {
    const ready = await probeNotifications(fetchImpl);
    if (!active || !ready) return;
    scheduleReconnect(fetchImpl);
  } catch {
    if (!active) return;
    scheduleReconnect(fetchImpl);
  } finally {
    recovering = false;
  }
}

async function openStream(fetchImpl: typeof fetch): Promise<void> {
  if (!browser || stream || !active) return;

  closeStream();
  stream = new EventSource('/api/v1/notifications/stream', { withCredentials: true } as EventSourceInit);

  stream.addEventListener('open', () => {
    reconnectDelay = 1000;
    store.update((state) => ({ ...state, connected: true, unavailable: false }));
  });

  stream.addEventListener('heartbeat', () => {});

  stream.addEventListener('notification', (event) => {
    try {
      const item = JSON.parse((event as MessageEvent).data) as Notification;
      store.update((state) => {
        if (state.items.some((existing) => existing.id === item.id)) return state;
        return {
          ...state,
          items: [item, ...state.items].slice(0, 20),
          unread: state.unread + (item.read ? 0 : 1)
        };
      });
    } catch {
      return;
    }
  });

  stream.addEventListener('error', () => {
    closeStream();
    setDisconnected(get(store).unavailable);
    void recoverStream(fetchImpl);
  });
}

function resetNotifications(): void {
  initialized = false;
  store.set({
    items: [],
    unread: 0,
    connected: false,
    loading: false,
    unavailable: false
  });
}

export function subscribeSSE(fetchImpl: typeof fetch = fetch): () => void {
  if (!browser || stream) return () => closeStream();
  active = true;

  if (!get(store).unavailable) {
    void openStream(fetchImpl);
  }

  return () => {
    active = false;
    recovering = false;
    clearReconnectTimer();
    closeStream();
    resetNotifications();
  };
}

export async function markNotificationAsRead(id: string, fetchImpl: typeof fetch = fetch): Promise<void> {
  await markNotificationRead(fetchImpl, id);

  if (!get(store).items.some((item) => item.id === id)) {
    const unread = await getNotificationUnreadCount(fetchImpl);
    store.update((state) => ({ ...state, unread: unread.count }));
    return;
  }

  store.update((state) => {
    const wasUnread = state.items.some((item) => item.id === id && !item.read);
    const items = state.items.map((item) => (item.id === id ? { ...item, read: true } : item));
    const unread = wasUnread ? Math.max(0, state.unread - 1) : state.unread;
    return { ...state, items, unread };
  });
}

export async function markAllNotificationsAsRead(fetchImpl: typeof fetch = fetch): Promise<void> {
  await markAllNotificationsRead(fetchImpl);

  store.update((state) => ({
    ...state,
    items: state.items.map((item) => ({ ...item, read: true })),
    unread: 0
  }));
}
