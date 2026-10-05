import { api, type Document, type User } from "./api.ts";

type Props = {
  user: User;
  documents: Document[];
  onChanged: () => void;
  onError: (message: string) => void;
};

export function DocumentList({ user, documents, onChanged, onError }: Props) {
  async function rename(doc: Document) {
    const title = window.prompt("New title", doc.title);
    if (!title) return;
    try {
      await api.renameDocument(doc.id, title);
      onChanged();
    } catch (e) {
      onError((e as Error).message);
    }
  }

  async function remove(doc: Document) {
    if (!window.confirm(`Delete "${doc.title}"?`)) return;
    try {
      await api.deleteDocument(doc.id);
      onChanged();
    } catch (e) {
      onError((e as Error).message);
    }
  }

  return (
    <table>
      <thead>
        <tr>
          <th>Title</th>
          <th>Owner</th>
          <th>Department</th>
          <th>Status</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {documents.map((doc) => (
          <tr key={doc.id}>
            <td>{doc.title}</td>
            <td>{doc.owner}</td>
            <td>{doc.department}</td>
            <td>{doc.status}</td>
            <td className="actions">
              {/* Mirrors the document policy so we don't need a round trip. */}
              {(user.roles.includes("admin") || doc.owner === user.id) && (
                <button onClick={() => rename(doc)}>Edit</button>
              )}
              {(user.roles.includes("admin") || (doc.owner === user.id && doc.status === "draft")) && (
                <button onClick={() => remove(doc)}>Delete</button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
