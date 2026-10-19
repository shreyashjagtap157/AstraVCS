import { AstraDaemonWorkspaceApi } from './daemon.js'

export interface PlatformInfo { os: string; arch: string; debug: boolean; appVersion: string }
export interface DaemonSession { url: string; token: string; pid: number; version: number; productVersion: string }

interface TauriInternals { invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> }
declare global { interface Window { __TAURI_INTERNALS__?: TauriInternals } }

function invoke<T>(cmd: string, args: Record<string, unknown> = {}): Promise<T> {
  const internals = typeof window === 'undefined' ? undefined : window.__TAURI_INTERNALS__
  if (!internals) throw new Error('not running inside the Tauri desktop runtime')
  return internals.invoke<T>(cmd, args)
}

export const isTauri = (): boolean => typeof window !== 'undefined' && Boolean(window.__TAURI_INTERNALS__)
export const platformInfo = (): Promise<PlatformInfo> => invoke<PlatformInfo>('platform_info')
export const discoverDaemonSession = (repoRoot: string): Promise<DaemonSession> => invoke<DaemonSession>('discover_daemon_session', { repoRoot })
export const readDaemonSession = (sessionPath: string): Promise<DaemonSession> => invoke<DaemonSession>('read_daemon_session', { sessionPath })
export const revealPath = (path: string): Promise<void> => invoke<void>('reveal_path', { path })
export const daemonClient = (session: DaemonSession): AstraDaemonWorkspaceApi => new AstraDaemonWorkspaceApi(session.url, session.token)
