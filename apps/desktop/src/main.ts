export interface DesktopConfiguration { serverUrl:string; repository?:string }
export function validateServerUrl(value:string):URL { const u=new URL(value); if(!['http:','https:'].includes(u.protocol))throw new Error('unsupported server URL'); return u }
export const platform=typeof navigator==='undefined'?'unknown':navigator.platform;
