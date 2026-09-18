from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Iterable

from stnp_editor.diagnostics import Diagnostic
from stnp_editor.errors import GenerationError

MANIFEST_NAME = ".stnp-manifest.json"
MANIFEST_VERSION = 1


def load_manifest(root: Path, diagnostics: list[Diagnostic] | None = None) -> dict[str, str]:
    """读取生成清单；清单损坏不再阻断生成，改为可选上报 warning 诊断。

    调用方未提供 ``diagnostics`` 收集器时退回静默忽略（例如发射器内部调用），
    以保证损坏的清单只影响陈旧文件清理，不影响本次生成。
    """
    path = root / MANIFEST_NAME
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        if diagnostics is not None:
            diagnostics.append(
                Diagnostic(
                    code="E4011",
                    level="warning",
                    message=f"生成清单损坏，已忽略: {MANIFEST_NAME}",
                    file=str(path),
                )
            )
        return {}
    if not isinstance(data, dict) or data.get("version") != MANIFEST_VERSION:
        return {}
    out: dict[str, str] = {}
    for item in data.get("files", []):
        if not isinstance(item, dict):
            continue
        rel = item.get("path")
        kind = item.get("kind")
        if isinstance(rel, str) and isinstance(kind, str) and _safe_rel(rel):
            out[rel] = kind
    return out


def write_manifest(root: Path, entries: dict[str, str]) -> None:
    payload = {
        "version": MANIFEST_VERSION,
        "files": [{"path": rel, "kind": entries[rel]} for rel in sorted(entries)],
    }
    try:
        (root / MANIFEST_NAME).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except OSError as exc:
        raise GenerationError("E4011", message=f"生成清单写出失败: {MANIFEST_NAME}") from exc


def cleanup_stale(root: Path, old: dict[str, str], current: Iterable[str]) -> None:
    current_set = set(current)
    for rel, kind in old.items():
        if rel in current_set or not _safe_rel(rel):
            continue
        path = root / rel
        if not path.exists():
            continue
        if kind == "implementation":
            _move_to_orphan(root, rel, path)
        elif path.is_file() or path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
    _prune_empty_dirs(root)


def _move_to_orphan(root: Path, rel: str, path: Path) -> None:
    relative = Path(rel)
    try:
        tail = relative.relative_to("Implementation")
    except ValueError:
        tail = Path(relative.name)
    dest = root / "Implementation" / "_orphaned" / tail
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        stem, suffix, index = dest.stem, dest.suffix, 1
        while True:
            candidate = dest.with_name(f"{stem}.{index}{suffix}")
            if not candidate.exists():
                dest = candidate
                break
            index += 1
    shutil.move(str(path), str(dest))


def _safe_rel(rel: str) -> bool:
    p = Path(rel)
    return bool(rel) and not p.is_absolute() and all(part not in ("", ".", "..") for part in p.parts)


def _prune_empty_dirs(root: Path) -> None:
    protected = {root, root / "Implementation", root / "Implementation" / "_orphaned"}
    dirs = sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True)
    for path in dirs:
        if path in protected or "_orphaned" in path.parts:
            continue
        try:
            path.rmdir()
        except OSError:
            pass
