from pathlib import Path
from pyunslop.ruff import run_ruff
from collections.abc import Iterable, Iterator


def directory_files(path: Path) -> list[Path]:
    """Reject ambiguous Ruff file lists instead of misreading newline-containing names."""
    output = run_ruff("check", "--show-files", "--", str(path))
    candidates = [Path(line) for line in output.removesuffix("\n").split("\n")] if output else []
    parents: set[Path] = set()

    # Validate every record, including non-Python files, before filtering the list.
    for candidate in candidates:
        if not candidate.is_absolute() or not candidate.is_file():
            raise RuntimeError("Ambiguous Ruff file list; newline-containing paths are unsupported")

        # A truncated name may coincide with a real file, so also check its siblings.
        parent = candidate.parent
        if parent not in parents:
            if any("\n" in entry.name or "\r" in entry.name for entry in parent.iterdir()):
                raise RuntimeError("Newline-containing paths are unsupported")
            parents.add(parent)

    # Ruff may also discover notebooks, stubs, and configuration files.
    return [candidate for candidate in candidates if candidate.suffix == ".py"]


def find_python_files(paths: Iterable[Path]) -> Iterator[Path]:
    """Discover Python source using Ruff's exclusions and Git ignore handling.

    Explicit files bypass directory exclusions. Missing paths raise OSError.
    """
    seen: set[Path] = set()
    scanned: set[Path] = set()
    for path in paths:
        # Explicit roots must be representable in Ruff's line-delimited file list.
        if "\n" in str(path) or "\r" in str(path):
            raise RuntimeError("Newline-containing paths are unsupported")
        if not path.exists():
            raise FileNotFoundError(f"{path}: path not found")

        # Explicit files bypass ignore rules, as they do on Ruff's CLI.
        if path.is_file():
            candidates = [path] if path.suffix == ".py" else []
        elif path.is_dir():
            # Cache directory identities without changing explicit-file bypasses.
            root = path.resolve()
            if root in scanned:
                continue
            candidates = directory_files(path)
            scanned.add(root)
        else:
            # Pipes and devices must not be passed to a scanner that may open them.
            raise OSError(f"{path}: expected a regular file or directory")

        # Preserve explicit path spelling and use project-relative paths for scans.
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)

            # Directory discovery returns absolute paths even for relative roots.
            if not path.is_absolute() and candidate.is_absolute():
                candidate = candidate.relative_to(Path.cwd())
            yield candidate
