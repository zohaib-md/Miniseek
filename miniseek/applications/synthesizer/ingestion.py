import os
import csv
import io
import json
import re
import zlib
from enum import Enum
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from miniseek.core.security import PathSecurity, SecurityError

class DocumentType(str, Enum):
    CSV = "CSV"
    JSON = "JSON"
    TEXT = "TEXT"
    MARKDOWN = "MARKDOWN"
    PDF = "PDF"
    UNKNOWN = "UNKNOWN"

@dataclass
class IngestedDocument:
    """Standardized representation of an ingested document for expense extraction."""
    source_path: str
    file_name: str
    extension: str
    size_bytes: int
    doc_type: DocumentType
    content_text: str
    bounded_chunks: List[str] = field(default_factory=list)
    is_scanned_pdf: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["doc_type"] = self.doc_type.value
        return d

class DocumentIngestionEngine:
    """
    Deterministic document ingestion engine for the Expense Synthesizer.
    - Zero heavy dependencies (Pure Python 3.12 standard library).
    - Supports CSV, JSON, Plain Text, Markdown, and text-native PDFs.
    - Gracefully flags scanned/image-only PDFs as is_scanned_pdf=True.
    - Bounded context chunking to enforce prompt token budgets.
    """

    MAX_CHUNK_CHARS = 1500  # ~350-400 tokens per chunk

    @classmethod
    def detect_doc_type(cls, file_path: Path) -> DocumentType:
        """Determines the document type based on file extension and signature."""
        ext = file_path.suffix.lower()
        if ext == ".csv":
            return DocumentType.CSV
        elif ext == ".json":
            return DocumentType.JSON
        elif ext in (".md", ".markdown"):
            return DocumentType.MARKDOWN
        elif ext in (".txt", ".text", ".log"):
            return DocumentType.TEXT
        elif ext == ".pdf":
            return DocumentType.PDF
        return DocumentType.UNKNOWN

    @classmethod
    def ingest_file(
        cls,
        file_path: Union[str, Path],
        root_dir: Optional[Union[str, Path]] = None,
        max_chunk_chars: int = MAX_CHUNK_CHARS
    ) -> IngestedDocument:
        """
        Deterministically ingests and normalizes a single document.
        Validates path within root boundary if root_dir is provided.
        """
        path_obj = Path(file_path)

        # Boundary validation
        if root_dir is not None:
            try:
                canonical_root = PathSecurity.get_canonical_path(root_dir)
                path_obj = PathSecurity.validate_within_root(path_obj, canonical_root)
            except SecurityError as err:
                return IngestedDocument(
                    source_path=str(file_path),
                    file_name=path_obj.name,
                    extension=path_obj.suffix,
                    size_bytes=0,
                    doc_type=DocumentType.UNKNOWN,
                    content_text="",
                    error_message=f"Security violation: {err}"
                )

        if not path_obj.exists():
            return IngestedDocument(
                source_path=str(path_obj),
                file_name=path_obj.name,
                extension=path_obj.suffix,
                size_bytes=0,
                doc_type=DocumentType.UNKNOWN,
                content_text="",
                error_message=f"File not found: {path_obj}"
            )

        size_bytes = path_obj.stat().st_size
        doc_type = cls.detect_doc_type(path_obj)

        try:
            with open(path_obj, "rb") as f:
                raw_bytes = f.read()

            if doc_type == DocumentType.CSV:
                return cls._ingest_csv(path_obj, raw_bytes, size_bytes, max_chunk_chars)
            elif doc_type == DocumentType.JSON:
                return cls._ingest_json(path_obj, raw_bytes, size_bytes, max_chunk_chars)
            elif doc_type in (DocumentType.TEXT, DocumentType.MARKDOWN):
                return cls._ingest_text(path_obj, raw_bytes, size_bytes, doc_type, max_chunk_chars)
            elif doc_type == DocumentType.PDF:
                return cls._ingest_pdf(path_obj, raw_bytes, size_bytes, max_chunk_chars)
            else:
                # Attempt decoding as plain text fallback
                try:
                    text = raw_bytes.decode("utf-8", errors="replace").strip()
                    chunks = cls._chunk_text(text, max_chunk_chars)
                    return IngestedDocument(
                        source_path=str(path_obj),
                        file_name=path_obj.name,
                        extension=path_obj.suffix,
                        size_bytes=size_bytes,
                        doc_type=DocumentType.UNKNOWN,
                        content_text=text,
                        bounded_chunks=chunks
                    )
                except Exception as err:
                    return IngestedDocument(
                        source_path=str(path_obj),
                        file_name=path_obj.name,
                        extension=path_obj.suffix,
                        size_bytes=size_bytes,
                        doc_type=DocumentType.UNKNOWN,
                        content_text="",
                        error_message=f"Unable to decode file content: {err}"
                    )

        except Exception as err:
            return IngestedDocument(
                source_path=str(path_obj),
                file_name=path_obj.name,
                extension=path_obj.suffix,
                size_bytes=size_bytes,
                doc_type=doc_type,
                content_text="",
                error_message=f"Ingestion error: {err}"
            )

    @classmethod
    def _ingest_csv(
        cls,
        path: Path,
        raw_bytes: bytes,
        size_bytes: int,
        max_chunk_chars: int
    ) -> IngestedDocument:
        """Ingests a CSV document with header detection and structured row formatting."""
        decoded = raw_bytes.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(decoded))
        rows = list(reader)

        if not rows:
            return IngestedDocument(
                source_path=str(path),
                file_name=path.name,
                extension=path.suffix,
                size_bytes=size_bytes,
                doc_type=DocumentType.CSV,
                content_text="",
                bounded_chunks=[]
            )

        header = rows[0]
        data_rows = rows[1:]

        # Format as readable row-by-row lines for bounded extraction
        formatted_lines = [f"CSV Header: {', '.join(header)}"]
        for idx, row in enumerate(data_rows, start=1):
            row_items = [f"{h}: {val.strip()}" for h, val in zip(header, row) if val.strip()]
            formatted_lines.append(f"Row {idx}: {', '.join(row_items)}")

        content_text = "\n".join(formatted_lines)
        chunks = cls._chunk_text(content_text, max_chunk_chars)

        return IngestedDocument(
            source_path=str(path),
            file_name=path.name,
            extension=path.suffix,
            size_bytes=size_bytes,
            doc_type=DocumentType.CSV,
            content_text=content_text,
            bounded_chunks=chunks,
            metadata={"row_count": len(data_rows), "header": header}
        )

    @classmethod
    def _ingest_json(
        cls,
        path: Path,
        raw_bytes: bytes,
        size_bytes: int,
        max_chunk_chars: int
    ) -> IngestedDocument:
        """Ingests a JSON document (list of objects or single transaction dictionary)."""
        decoded = raw_bytes.decode("utf-8", errors="replace")
        try:
            data = json.loads(decoded)
            content_text = json.dumps(data, indent=2)
            chunks = cls._chunk_text(content_text, max_chunk_chars)
            count = len(data) if isinstance(data, list) else 1
            return IngestedDocument(
                source_path=str(path),
                file_name=path.name,
                extension=path.suffix,
                size_bytes=size_bytes,
                doc_type=DocumentType.JSON,
                content_text=content_text,
                bounded_chunks=chunks,
                metadata={"item_count": count}
            )
        except json.JSONDecodeError as err:
            return IngestedDocument(
                source_path=str(path),
                file_name=path.name,
                extension=path.suffix,
                size_bytes=size_bytes,
                doc_type=DocumentType.JSON,
                content_text=decoded,
                bounded_chunks=cls._chunk_text(decoded, max_chunk_chars),
                error_message=f"JSON decode warning: {err}"
            )

    @classmethod
    def _ingest_text(
        cls,
        path: Path,
        raw_bytes: bytes,
        size_bytes: int,
        doc_type: DocumentType,
        max_chunk_chars: int
    ) -> IngestedDocument:
        """Ingests plain text or Markdown documents."""
        text = raw_bytes.decode("utf-8", errors="replace").strip()
        chunks = cls._chunk_text(text, max_chunk_chars)
        return IngestedDocument(
            source_path=str(path),
            file_name=path.name,
            extension=path.suffix,
            size_bytes=size_bytes,
            doc_type=doc_type,
            content_text=text,
            bounded_chunks=chunks
        )

    @classmethod
    def _ingest_pdf(
        cls,
        path: Path,
        raw_bytes: bytes,
        size_bytes: int,
        max_chunk_chars: int
    ) -> IngestedDocument:
        """
        Pure-Python text extraction from native PDF files.
        Extracts uncompressed and FlateDecode compressed text streams.
        If no text stream is found or the PDF is image-only/scanned, flags is_scanned_pdf=True.
        """
        extracted_text_parts: List[str] = []

        # Find all stream ... endstream blocks
        stream_matches = re.finditer(b"stream\r?\n(.*?)\r?\nendstream", raw_bytes, re.DOTALL)
        for match in stream_matches:
            stream_data = match.group(1)

            # Try decompression (FlateDecode)
            decompressed = None
            try:
                decompressed = zlib.decompress(stream_data)
            except Exception:
                decompressed = stream_data  # Uncompressed stream

            if decompressed:
                # Extract text enclosed in parentheses ( ... ) Tj or [ ( ... ) ] TJ
                # e.g., (Invoice Total: $450) Tj
                text_matches = re.findall(rb"\((.*?)\)\s*Tj", decompressed)
                for tm in text_matches:
                    try:
                        decoded_str = tm.decode("latin1", errors="ignore")
                        cleaned = cls._clean_pdf_string(decoded_str)
                        if cleaned.strip():
                            extracted_text_parts.append(cleaned)
                    except Exception:
                        continue

                # Array TJ operator: [ (Invoice) 10 (Total) ] TJ
                array_matches = re.findall(rb"\[(.*?)\]\s*TJ", decompressed, re.DOTALL)
                for am in array_matches:
                    inner_texts = re.findall(rb"\((.*?)\)", am)
                    combined = " ".join(
                        cls._clean_pdf_string(t.decode("latin1", errors="ignore"))
                        for t in inner_texts
                    ).strip()
                    if combined:
                        extracted_text_parts.append(combined)

        # Also search for uncompressed BT ... ET text blocks directly in PDF bytes
        direct_matches = re.findall(rb"BT\s+(.*?)\s+ET", raw_bytes, re.DOTALL)
        for dm in direct_matches:
            inner_texts = re.findall(rb"\((.*?)\)\s*Tj", dm)
            for it in inner_texts:
                cleaned = cls._clean_pdf_string(it.decode("latin1", errors="ignore"))
                if cleaned.strip() and cleaned not in extracted_text_parts:
                    extracted_text_parts.append(cleaned)

        full_text = "\n".join(extracted_text_parts).strip()

        # Check if PDF contains text or is an image/scanned PDF
        is_scanned = False
        if not full_text:
            # Check if document contains Image XObjects
            has_images = b"/Subtype /Image" in raw_bytes or b"/Image" in raw_bytes
            is_scanned = True
            content = "[SCANNED / IMAGE-ONLY PDF: No native text stream detected. OCR required in future versions.]"
        else:
            content = full_text

        chunks = cls._chunk_text(content, max_chunk_chars)

        return IngestedDocument(
            source_path=str(path),
            file_name=path.name,
            extension=path.suffix,
            size_bytes=size_bytes,
            doc_type=DocumentType.PDF,
            content_text=content,
            bounded_chunks=chunks,
            is_scanned_pdf=is_scanned,
            metadata={"native_text_extracted": not is_scanned, "text_blocks_count": len(extracted_text_parts)}
        )

    @classmethod
    def _clean_pdf_string(cls, s: str) -> str:
        """Cleans PDF escape sequences in extracted literal strings."""
        s = s.replace(r"\n", "\n").replace(r"\r", "\r").replace(r"\t", "\t")
        s = s.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
        return s

    @classmethod
    def _chunk_text(cls, text: str, max_chunk_chars: int) -> List[str]:
        """Splits long document text into bounded, clean context chunks."""
        if not text:
            return []
        if len(text) <= max_chunk_chars:
            return [text]

        chunks = []
        lines = text.split("\n")
        current_chunk = []
        current_len = 0

        for line in lines:
            line_len = len(line) + 1
            if current_len + line_len > max_chunk_chars and current_chunk:
                chunks.append("\n".join(current_chunk).strip())
                current_chunk = [line]
                current_len = line_len
            else:
                current_chunk.append(line)
                current_len += line_len

        if current_chunk:
            chunks.append("\n".join(current_chunk).strip())

        return chunks
