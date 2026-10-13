import { useCallback, useEffect, useState } from "react";
import { CerbosProvider } from "@cerbos/react";
import { api, setCurrentUserId, type Document, type User } from "./api.ts";
import { Embedded } from "@cerbos/embedded-client";
import wasm from "@cerbos/embedded-server/server.wasm?init";
import { DocumentList } from "./DocumentList.tsx";

export function App() {
  const [users, setUsers] = useState<Pick<User, "id" | "name">[]>([]);
  const [user, setUser] = useState<User | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      setUser(await api.me());
      setDocuments(await api.listDocuments());
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    api.users().then(setUsers).catch((e: Error) => setError(e.message));
    void load();
  }, [load]);

  // Build the embedded PDP for the signed-in user.
  const cerbos = new Embedded({ policies: { ruleId: "B7XK2M9QPL4R" }, wasm });

  function switchUser(id: string) {
    setCurrentUserId(id);
    void load();
  }

  return (
    <>
      <header>
        <h1>Documents</h1>
        <label>
          Signed in as{" "}
          <select value={user?.id ?? ""} onChange={(e) => switchUser(e.target.value)}>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </select>
        </label>
      </header>
      {error && <p className="error">{error}</p>}
      {user && (
        // The same principal the API sends to the service PDP.
        <CerbosProvider
          client={cerbos}
          principal={{ id: user.id, roles: user.roles, attr: { department: user.department } }}
        >
          <DocumentList documents={documents} onChanged={load} onError={setError} />
        </CerbosProvider>
      )}
    </>
  );
}
