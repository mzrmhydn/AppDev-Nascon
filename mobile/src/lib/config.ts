// App settings stored in SQLite: server address (spec §8.1 — must be editable in-app) and mock mode.
import { kvGet, kvSet } from './db';

export const DEFAULT_SERVER = 'http://10.0.2.2:8080'; // Android emulator → host laptop

export function getServer(): string {
  return kvGet('server_url') ?? DEFAULT_SERVER;
}

/** Saves a cleaned-up address (adds http://, strips trailing slash). Returns the saved value. */
export function setServer(raw: string): string {
  let v = raw.trim();
  if (!/^https?:\/\//i.test(v)) v = 'http://' + v;
  v = v.replace(/\/+$/, '');
  kvSet('server_url', v);
  return v;
}

/** Mock mode = the app answers from built-in sample data (used while the backend was being built). */
export function getMock(): boolean {
  return kvGet('mock_mode') === '1';
}

export function setMock(on: boolean) {
  kvSet('mock_mode', on ? '1' : '0');
}

export function wsUrl(path: string): string {
  return getServer().replace(/^http/i, 'ws') + path;
}
