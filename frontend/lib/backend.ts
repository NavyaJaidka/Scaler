export const BACKEND = (process.env.NEXT_PUBLIC_BACKEND_URL || "/api/backend").replace(/\/+$/, "");

export function backendPath(path: string) {
  return `${BACKEND}/${path.replace(/^\/+/, "")}`;
}