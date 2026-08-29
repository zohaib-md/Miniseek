import os
from pathlib import Path
from typing import Union

class SecurityError(PermissionError):
    """Raised when an operation violates filesystem sandbox boundaries or security invariants."""
    pass

class PathSecurity:
    """
    Enforces canonical path resolution and symlink sandbox boundaries.
    Invariant: MiniSeek may only mutate objects that resolve strictly within the approved root.
    """

    @staticmethod
    def get_canonical_path(path: Union[str, Path]) -> Path:
        """Resolves a path to its canonical, symlink-free absolute representation."""
        return Path(os.path.realpath(str(path)))

    @classmethod
    def validate_within_root(cls, target_path: Union[str, Path], root_dir: Union[str, Path]) -> Path:
        """
        Validates that target_path canonical resolution lies strictly within root_dir canonical resolution.
        Throws SecurityError on path escapes (e.g. `../`, absolute root escapes, or out-of-bounds symlinks).
        """
        canonical_root = cls.get_canonical_path(root_dir)
        canonical_target = cls.get_canonical_path(target_path)

        try:
            # relative_to will raise ValueError if canonical_target is not inside canonical_root
            canonical_target.relative_to(canonical_root)
            return canonical_target
        except ValueError:
            raise SecurityError(
                f"Security Violation: Target path '{target_path}' (canonical: '{canonical_target}') "
                f"escapes approved root boundary '{root_dir}' (canonical: '{canonical_root}')."
            )

    @classmethod
    def is_symlink_escaping_root(cls, symlink_path: Union[str, Path], root_dir: Union[str, Path]) -> bool:
        """Checks if a symlink file points to a target outside the approved root."""
        p = Path(symlink_path)
        if not p.is_symlink():
            return False
        
        try:
            cls.validate_within_root(p, root_dir)
            return False
        except SecurityError:
            return True
