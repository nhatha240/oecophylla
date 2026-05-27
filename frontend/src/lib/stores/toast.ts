import { writable } from 'svelte/store';

type ToastState = {
  id: number;
  message: string;
} | null;

const store = writable<ToastState>(null);

let nextToastId = 1;

export const toast = {
  subscribe: store.subscribe
};

export function showToast(message: string): void {
  store.set({ id: nextToastId++, message });
}

export function clearToast(): void {
  store.set(null);
}
