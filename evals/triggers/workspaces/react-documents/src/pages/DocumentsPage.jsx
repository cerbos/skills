import { useEffect, useState } from "react";
import DocumentList from "../components/DocumentList.jsx";

export default function DocumentsPage() {
  const [documents, setDocuments] = useState([]);

  useEffect(() => {
    fetch("/api/documents").then((r) => r.json()).then(setDocuments);
  }, []);

  async function remove(id) {
    await fetch(`/api/documents/${id}`, { method: "DELETE" });
    setDocuments((docs) => docs.filter((d) => d.id !== id));
  }

  async function removeAll() {
    await Promise.all(documents.map((d) => fetch(`/api/documents/${d.id}`, { method: "DELETE" })));
    setDocuments([]);
  }

  return <DocumentList documents={documents} onDelete={remove} onDeleteAll={removeAll} />;
}
