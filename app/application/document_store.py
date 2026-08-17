"""Persistent document knowledge base for chat context."""

from __future__ import annotations

import json
import logging
import math
import re
import shutil
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO

from app.config.settings import Settings

logger = logging.getLogger("enterprise_mcp_host")


@dataclass(frozen=True)
class DocumentChunk:
    """Searchable document text chunk."""

    document_id: str
    filename: str
    text: str
    score: float = 0.0


class DocumentStore:
    """Stores uploaded documents and retrieves relevant excerpts."""

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}

    def __init__(self, settings: Settings) -> None:
        self.root = settings.knowledge_base_dir
        self.upload_dir = self.root / "uploads"
        self.index_path = self.root / "index.json"
        self.vector_db_path = self.root / "vectors.sqlite3"
        self.embedding_model_name = settings.embedding_model_name
        self.ollama_base_url = settings.ollama_base_url or "http://127.0.0.1:11434"
        self.chunk_size = settings.document_chunk_size
        self.overlap = settings.document_chunk_overlap
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._embeddings_model: Any | None = None
        self._embeddings_lock = threading.Lock()
        self._ensure_schema()
        logger.info(
            "Initialized DocumentStore with root=%s, vector_db=%s, chunk_size=%s, overlap=%s, ollama_base_url=%s",
            self.root,
            self.vector_db_path,
            self.chunk_size,
            self.overlap,
            self.ollama_base_url,
        )

    def list_documents(self) -> list[dict[str, object]]:
        """Return uploaded document metadata."""
        documents = self._load_index().get("documents", [])
        logger.info("Listing %d uploaded documents.", len(documents))
        return documents

    def add_document(self, filename: str, file_obj: BinaryIO) -> dict[str, object]:
        """Persist an uploaded document and add extracted text to the index."""
        logger.info("Adding document %s.", filename)
        safe_name = self._safe_filename(filename)
        extension = Path(safe_name).suffix.lower()
        if extension not in self.SUPPORTED_EXTENSIONS:
            allowed = ", ".join(sorted(self.SUPPORTED_EXTENSIONS))
            logger.error("Unsupported document type: %s", extension)
            raise ValueError(f"Unsupported document type. Allowed: {allowed}")

        document_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        stored_name = f"{document_id}_{safe_name}"
        stored_path = self.upload_dir / stored_name
        with stored_path.open("wb") as handle:
            shutil.copyfileobj(file_obj, handle)
        logger.info("Saved uploaded document to %s.", stored_path)

        text = self._extract_text(stored_path)
        chunks = self._chunk_text(text)
        if not chunks:
            stored_path.unlink(missing_ok=True)
            logger.error("No readable text found in %s.", stored_path)
            raise ValueError("No readable text was found in the uploaded document.")

        index = self._load_index()
        document = {
            "id": document_id,
            "filename": safe_name,
            "stored_name": stored_name,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "chunk_count": len(chunks),
        }
        try:
            self._add_vectors(document_id, safe_name, chunks)
        except Exception:
            stored_path.unlink(missing_ok=True)
            self._delete_vectors(document_id)
            logger.exception("Failed to add vectors for document %s.", document_id)
            raise

        index["documents"].append(document)
        self._save_index(index)
        logger.info(
            "Document %s added with %d chunks.",
            document_id,
            len(chunks),
        )
        return document

    def embed_query(self, query: str) -> list[float]:
        """Return an embedding vector for semantic search and caching."""
        return self._embed_query(query)

    def search(self, query: str, limit: int = 4) -> list[DocumentChunk]:
        """Return document chunks using vector similarity search."""
        logger.info("Searching document store for query: %s", query)
        if not query.strip():
            logger.warning("Empty search query provided.")
            return []

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT document_id, filename, chunk_text, embedding
                FROM document_vectors
                """
            ).fetchall()
        if not rows:
            logger.info("No document vectors found for search.")
            return []

        query_vector = self._embed_query(query)
        scored = []
        for document_id, filename, text, embedding_json in rows:
            embedding = json.loads(embedding_json)
            score = self._cosine_similarity(query_vector, embedding)
            if score > 0:
                scored.append(
                    DocumentChunk(
                        document_id=str(document_id),
                        filename=str(filename),
                        text=text,
                        score=score,
                    )
                )
        scored.sort(key=lambda chunk: chunk.score, reverse=True)
        logger.info("Search returned %d matching chunks.", min(len(scored), limit))
        return scored[:limit]

    def _ensure_schema(self) -> None:
        logger.info("Ensuring document store schema exists.")
        self.root.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS document_vectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_text TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_document_vectors_document
                ON document_vectors(document_id)
                """
            )
        logger.info("Document store schema validated.")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.vector_db_path)
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _add_vectors(
        self,
        document_id: str,
        filename: str,
        chunks: list[str],
    ) -> None:
        logger.info("Embedding %d chunks for document %s.", len(chunks), document_id)
        embeddings = self._embed_documents(chunks)
        created_at = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                document_id,
                filename,
                index,
                chunk,
                json.dumps(embedding),
                created_at,
            )
            for index, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO document_vectors (
                    document_id,
                    filename,
                    chunk_index,
                    chunk_text,
                    embedding,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        logger.info("Inserted %d document vector rows for document %s.", len(rows), document_id)

    def _delete_vectors(self, document_id: str) -> None:
        logger.info("Deleting vectors for document %s.", document_id)
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM document_vectors WHERE document_id = ?",
                (document_id,),
            )

    def _embed_documents(self, texts: list[str]) -> list[list[float]]:
        with self._embeddings_lock:
            return self._embeddings().embed_documents(texts)

    def _embed_query(self, query: str) -> list[float]:
        logger.info("Generating embedding for query.")
        with self._embeddings_lock:
            return self._embeddings().embed_query(query)

    def _embeddings(self) -> Any:
        if self._embeddings_model is None:
            logger.info(
                "Creating Ollama embeddings model %s with base_url=%s.",
                self.embedding_model_name,
                self.ollama_base_url,
            )
            try:
                from langchain_ollama import OllamaEmbeddings
            except ImportError as exc:
                logger.exception("Failed to import langchain_ollama for embeddings.")
                raise RuntimeError(
                    "Install langchain-ollama to use document embeddings."
                ) from exc
            self._embeddings_model = OllamaEmbeddings(
                model=self.embedding_model_name,
                base_url=self.ollama_base_url,
            )
        else:
            logger.info("Reusing cached embeddings model %s.", self.embedding_model_name)
        return self._embeddings_model

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)

    def _extract_text(self, path: Path) -> str:
        extension = path.suffix.lower()
        if extension == ".pdf":
            return self._extract_pdf(path)
        if extension in {".docx", ".doc"}:
            return self._extract_docx(path)
        return path.read_text(encoding="utf-8", errors="ignore")

    def _extract_pdf(self, path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("Install pypdf to upload PDF files.") from exc

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def _extract_docx(self, path: Path) -> str:
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("Install python-docx to upload Word documents.") from exc

        document = Document(str(path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)

    def _chunk_text(self, text: str) -> list[str]:
        cleaned = re.sub(r"\s+", " ", text).strip()
        if not cleaned:
            return []
        chunks = []
        start = 0
        while start < len(cleaned):
            chunks.append(cleaned[start : start + self.chunk_size])
            start += self.chunk_size - self.overlap
        return chunks

    def _safe_filename(self, filename: str) -> str:
        name = Path(filename).name
        return re.sub(r"[^A-Za-z0-9._-]", "_", name) or "document"

    def _load_index(self) -> dict[str, list[dict[str, object]]]:
        if not self.index_path.exists():
            logger.info("Document index file not found; starting with empty index.")
            return {"documents": []}
        with self.index_path.open("r", encoding="utf-8") as handle:
            index = json.load(handle)
        index.setdefault("documents", [])
        logger.info("Loaded document index with %d documents.", len(index["documents"]))
        return index

    def _save_index(self, index: dict[str, list[dict[str, object]]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.index_path.open("w", encoding="utf-8") as handle:
            json.dump(index, handle, indent=2)
        logger.info("Saved document index with %d documents.", len(index.get("documents", [])))
