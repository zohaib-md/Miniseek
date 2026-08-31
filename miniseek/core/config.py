from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple

@dataclass
class Config:
    """
    Central configuration for MiniSeek.
    Token budget and model parameters are configurable for empirical benchmarking.
    """
    # LLM & Context Budget
    # Experimental default: 500 tokens (tested for benchmarking: 250, 500, 750, 1000)
    max_prompt_tokens: int = 500
    model_name: str = "qwen2.5:1.5b"
    ollama_host: str = "http://127.0.0.1:11434"

    # Semantic Categorization Allowed Set (includes explicit model abstentions)
    allowed_categories: Tuple[str, ...] = (
        "Documents",
        "Receipts_Invoices",
        "Media_Images",
        "Code",
        "Archives_Data",
        "UNCATEGORIZED",
        "NEEDS_REVIEW"
    )

    # File Janitor Scanning Settings
    max_preview_chars: int = 150
    hash_chunk_size: int = 64 * 1024  # 64 KB streaming buffer for hashing

    # History & History Directory
    history_dir_name: str = ".miniseek/history"

DEFAULT_CONFIG = Config()
