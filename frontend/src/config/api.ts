export const API_BASE_URL = '/api/backend';

export const getApiUrl = (path: string) =>
    `${API_BASE_URL.replace(/\/$/, '')}/${path.replace(/^\//, '')}`;
