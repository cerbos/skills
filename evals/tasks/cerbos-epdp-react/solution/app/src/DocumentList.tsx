import { useCheckResource } from "@cerbos/react";
import { api, type Document } from "./api.ts";

type Props = {
  documents: Document[];
  onChanged: () => void;
  onError: (message: string) => void;
};

export function DocumentList({ documents, onChanged, onError }: Props) {
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
              <DocumentActions doc={doc} onEdit={() => rename(doc)} onDelete={() => remove(doc)} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

type ActionsProps = {
  doc: Document;
  onEdit: () => void;
  onDelete: () => void;
};

// Renders only the buttons the embedded PDP allows, with the same resource
// attributes the API sends. Nothing renders while the bundle loads or if the
// check fails; the API enforces either way.
function DocumentActions({ doc, onEdit, onDelete }: ActionsProps) {
  const check = useCheckResource({
    resource: {
      kind: "document",
      id: doc.id,
      attr: { owner: doc.owner, department: doc.department, status: doc.status },
    },
    actions: ["edit", "delete"],
  });

  if (check.isLoading || check.error || !check.data) return null;

  return (
    <>
      {check.data.isAllowed("edit") && <button onClick={onEdit}>Edit</button>}
      {check.data.isAllowed("delete") && <button onClick={onDelete}>Delete</button>}
    </>
  );
}
