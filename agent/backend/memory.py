import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import uuid
from datetime import datetime

class MemoryStore:
    def __init__(self, persist_dir: str = "memory_db"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection("agent_memory")
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def _embed(self, text: str):
        return self.model.encode(text).tolist()

    def add_memory(self, text: str, mtype: str):
        mem_id = str(uuid.uuid4())
        metadata = {
            "type": mtype,
            "created_at": datetime.utcnow().isoformat()
        }
        self.collection.add(
            ids=[mem_id],
            documents=[text],
            metadatas=[metadata],
            embeddings=[self._embed(text)]
        )
        return mem_id

    def search(self, query: str, mtype: str | None = None, n_results: int = 5):
        where = {"type": mtype} if mtype else None
        results = self.collection.query(
            query_embeddings=[self._embed(query)],
            n_results=n_results,
            where=where
        )
        return results

    def delete(self, mem_id: str):
        self.collection.delete(ids=[mem_id])
