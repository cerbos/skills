export type User = {
  id: string;
  name: string;
  roles: string[];
  department: string;
};

export type Document = {
  id: string;
  title: string;
  owner: string;
  department: string;
  status: "draft" | "published";
};

// Demo sign-in: the API identifies the caller by this header. In production the
// gateway sets it from the session cookie.
let currentUserId = "alice";

export function setCurrentUserId(id: string) {
  currentUserId = id;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": currentUserId,
      ...init.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error ?? `${response.status} ${response.statusText}`);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const api = {
  me: () => request<User>("/api/me"),
  users: () => request<Pick<User, "id" | "name">[]>("/api/users"),
  listDocuments: () => request<Document[]>("/api/documents"),
  renameDocument: (id: string, title: string) =>
    request<Document>(`/api/documents/${id}`, {
      method: "PUT",
      body: JSON.stringify({ title }),
    }),
  deleteDocument: (id: string) =>
    request<void>(`/api/documents/${id}`, { method: "DELETE" }),
};
