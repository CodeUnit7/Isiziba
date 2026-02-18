export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;
export const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL;

if (!API_BASE_URL || !WS_BASE_URL) {
    if (typeof window !== 'undefined') {
        console.error('❌ NEXT_PUBLIC_API_URL or NEXT_PUBLIC_WS_URL environment variables are not set.');
    }
}
export const CURRENCY = process.env.NEXT_PUBLIC_CURRENCY || 'USDC';

export const getApiUrl = (path: string) => `${API_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`;
export const getWsUrl = (path: string) => `${WS_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`;
