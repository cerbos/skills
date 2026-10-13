import { currentUser } from "../session.js";

export default function DocumentList({ documents, onDelete, onDeleteAll }) {
  return (
    <div>
      <div className="toolbar">
        <h1>Documents</h1>
        <button onClick={onDeleteAll}>Delete all</button>
      </div>
      <ul>
        {documents.map((doc) => (
          <li key={doc.id}>
            <span>{doc.title}</span>
            <small>owner: {doc.ownerId === currentUser.id ? "you" : doc.ownerName}</small>
            <a href={`/documents/${doc.id}/edit`}><button>Edit</button></a>
            <button onClick={() => onDelete(doc.id)}>Delete</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
