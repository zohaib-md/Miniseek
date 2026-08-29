import os
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from miniseek.core.types import FileInfo, DuplicateGroup, ScanResult
from miniseek.core.config import Config, DEFAULT_CONFIG
from miniseek.core.security import PathSecurity

class FileScanner:
    """
    Deterministic File Scanner & Multi-Stage SHA-256 Deduplication Engine.
    - Traverses directory without following symlinked directories.
    - Skips symlinked files and reports them explicitly.
    - Extracts metadata and bounded preview text.
    - Groups candidates by size before streaming SHA-256 hashes.
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or DEFAULT_CONFIG

    def scan(self, directory: Union[str, Path], include_hidden: bool = False) -> ScanResult:
        """Performs a deterministic scan of directory and returns a verified ScanResult."""
        start_time = time.time()
        canonical_root = PathSecurity.get_canonical_path(directory)

        if not canonical_root.exists() or not canonical_root.is_dir():
            raise FileNotFoundError(f"Target directory does not exist or is not a directory: {directory}")

        files: List[FileInfo] = []
        skipped_symlinks: List[FileInfo] = []
        total_bytes = 0

        # Deterministic recursive walk without following directory symlinks
        for root, dirs, filenames in os.walk(canonical_root, followlinks=False):
            # Skip hidden directories if not requested
            if not include_hidden:
                dirs[:] = [d for d in dirs if not d.startswith(".") and not d.startswith(".miniseek")]

            for fname in filenames:
                if not include_hidden and fname.startswith("."):
                    continue

                full_path = Path(root) / fname
                rel_path = str(full_path.relative_to(canonical_root))

                # Check for symlink file
                if full_path.is_symlink():
                    try:
                        target = os.readlink(str(full_path))
                    except Exception:
                        target = None

                    symlink_info = FileInfo(
                        path=str(full_path),
                        relative_path=rel_path,
                        name=fname,
                        extension=full_path.suffix.lower(),
                        size_bytes=0,
                        mtime=0.0,
                        is_symlink=True,
                        symlink_target=target,
                        preview="(Symlink skipped)"
                    )
                    skipped_symlinks.append(symlink_info)
                    continue

                # Regular file processing
                try:
                    stat = full_path.stat()
                    size = stat.st_size
                    mtime = stat.st_mtime
                    total_bytes += size

                    preview = self._extract_preview(full_path)

                    file_info = FileInfo(
                        path=str(full_path),
                        relative_path=rel_path,
                        name=fname,
                        extension=full_path.suffix.lower(),
                        size_bytes=size,
                        mtime=mtime,
                        is_symlink=False,
                        preview=preview
                    )
                    files.append(file_info)
                except (OSError, PermissionError):
                    # Handle unreadable files safely
                    continue

        # Deterministic multi-stage duplicate detection
        duplicate_groups = self._detect_duplicates(files)

        elapsed = round(time.time() - start_time, 4)

        return ScanResult(
            root_path=str(canonical_root),
            total_files=len(files),
            total_bytes=total_bytes,
            files=files,
            skipped_symlinks=skipped_symlinks,
            duplicate_groups=duplicate_groups,
            scan_duration_sec=elapsed
        )

    def _extract_preview(self, file_path: Path) -> str:
        """Extracts bounded text preview for small model micro-task evidence."""
        # Only read text preview for text/code/document extensions
        binary_extensions = {".png", ".jpg", ".jpeg", ".gif", ".zip", ".tar", ".gz", ".pyc", ".pdf", ".exe", ".bin"}
        if file_path.suffix.lower() in binary_extensions:
            return f"({file_path.suffix.upper()} Binary File)"

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(self.config.max_preview_chars).strip()
                # Normalize newlines and whitespace for clean prompt presentation
                return " ".join(content.split())
        except Exception:
            return "(Unreadable content)"

    def _detect_duplicates(self, files: List[FileInfo]) -> List[DuplicateGroup]:
        """
        Multi-stage deterministic duplicate finder:
        1. Group by exact file size.
        2. Only compute SHA-256 for files that share a common size (>0 bytes).
        3. Group matching SHA-256 files into DuplicateGroups.
        """
        # Step 1: Candidate grouping by size
        size_buckets: Dict[int, List[FileInfo]] = {}
        for f in files:
            if f.size_bytes > 0:  # Ignore 0-byte empty files from duplicate groupings
                size_buckets.setdefault(f.size_bytes, []).append(f)

        candidates = [file_list for file_list in size_buckets.values() if len(file_list) > 1]

        # Step 2: Stream SHA-256 hash for size collision candidates
        hash_buckets: Dict[str, List[FileInfo]] = {}
        for group in candidates:
            for f in group:
                file_hash = self.compute_sha256(Path(f.path))
                if file_hash:
                    f.sha256 = file_hash
                    hash_buckets.setdefault(file_hash, []).append(f)

        # Step 3: Filter true duplicate groups (hash collision > 1)
        duplicate_groups: List[DuplicateGroup] = []
        for sha256_hash, dup_files in hash_buckets.items():
            if len(dup_files) > 1:
                duplicate_groups.append(
                    DuplicateGroup(
                        sha256=sha256_hash,
                        size_bytes=dup_files[0].size_bytes,
                        files=dup_files
                    )
                )

        return sorted(duplicate_groups, key=lambda dg: dg.wasted_bytes, reverse=True)

    def compute_sha256(self, file_path: Path) -> Optional[str]:
        """Computes full SHA-256 digest in buffered chunks."""
        try:
            hasher = hashlib.sha256()
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(self.config.hash_chunk_size)
                    if not chunk:
                        break
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return None
