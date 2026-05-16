const DEFAULT_API_BASE_URL = 'http://localhost:8080';

export const API_BASE_URL =
    import.meta.env.VITE_API_BASE_URL?.trim() || DEFAULT_API_BASE_URL;

export const getApiUrl = (path: string) =>
    `${API_BASE_URL.replace(/\/$/, '')}/${path.replace(/^\//, '')}`;
