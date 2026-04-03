"""AgentShift local agent registry with drift detection.

Stores registered agent snapshots in ~/.agentshift/registry.json and provides
commands to register, list, diff (drift detection), and export agents.

Implements D28.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DEFAULT_REGISTRY_DIR = Path.home() / ".agentshift"
_REGISTRY_FILE = "registry.json"


# ---------------------------------------------------------------------------
# Registry data model
# ---------------------------------------------------------------------------


class RegistryEntry:
    """A single registered agent snapshot."""

    def __init__(
        self,
        name: str,
        source_path: str,
        platform: str,
        ir_snapshot: dict[str, Any],
        registered_at: str,
        content_hash: str,
    ) -> None:
        self.name = name
        self.source_path = source_path
        self.platform = platform
        self.ir_snapshot = ir_snapshot
        self.registered_at = registered_at
        self.content_hash = content_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source_path": self.source_path,
            "platform": self.platform,
            "ir_snapshot": self.ir_snapshot,
            "registered_at": self.registered_at,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RegistryEntry:
        return cls(
            name=data["name"],
            source_path=data["source_path"],
            platform=data["platform"],
            ir_snapshot=data["ir_snapshot"],
            registered_at=data["registered_at"],
            content_hash=data["content_hash"],
        )


# ---------------------------------------------------------------------------
# Registry operations
# ---------------------------------------------------------------------------


class Registry:
    """Local agent registry backed by a JSON file."""

    def __init__(self, registry_dir: Path | None = None) -> None:
        self.registry_dir = registry_dir or _DEFAULT_REGISTRY_DIR
        self.registry_file = self.registry_dir / _REGISTRY_FILE
        self._entries: dict[str, RegistryEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load registry from disk."""
        if not self.registry_file.exists():
            self._entries = {}
            return
        try:
            data = json.loads(self.registry_file.read_text(encoding="utf-8"))
            self._entries = {
                name: RegistryEntry.from_dict(entry)
                for name, entry in data.get("agents", {}).items()
            }
        except (json.JSONDecodeError, KeyError, TypeError):
            self._entries = {}

    def _save(self) -> None:
        """Persist registry to disk."""
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.0",
            "agents": {name: entry.to_dict() for name, entry in self._entries.items()},
        }
        self.registry_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def register(
        self,
        name: str,
        source_path: str,
        platform: str,
        ir_dict: dict[str, Any],
    ) -> RegistryEntry:
        """Register or update an agent in the registry."""
        content_hash = _hash_ir(ir_dict)
        entry = RegistryEntry(
            name=name,
            source_path=source_path,
            platform=platform,
            ir_snapshot=ir_dict,
            registered_at=datetime.now(UTC).isoformat(),
            content_hash=content_hash,
        )
        self._entries[name] = entry
        self._save()
        return entry

    def list_agents(self) -> list[RegistryEntry]:
        """Return all registered agents."""
        return list(self._entries.values())

    def get(self, name: str) -> RegistryEntry | None:
        """Get a specific agent by name."""
        return self._entries.get(name)

    def remove(self, name: str) -> bool:
        """Remove an agent from the registry. Returns True if found."""
        if name in self._entries:
            del self._entries[name]
            self._save()
            return True
        return False

    def diff(self, name: str, current_ir_dict: dict[str, Any]) -> DriftReport:
        """Compare current agent state against registered snapshot."""
        entry = self._entries.get(name)
        if entry is None:
            return DriftReport(
                name=name,
                registered=False,
                has_drift=False,
                changes=[],
            )

        current_hash = _hash_ir(current_ir_dict)
        if current_hash == entry.content_hash:
            return DriftReport(
                name=name,
                registered=True,
                has_drift=False,
                changes=[],
            )

        changes = _compute_changes(entry.ir_snapshot, current_ir_dict)
        return DriftReport(
            name=name,
            registered=True,
            has_drift=True,
            changes=changes,
        )

    def export(self, format: str = "json") -> str:
        """Export the full registry."""
        data = {
            "version": "1.0",
            "exported_at": datetime.now(UTC).isoformat(),
            "agent_count": len(self._entries),
            "agents": {name: entry.to_dict() for name, entry in self._entries.items()},
        }
        return json.dumps(data, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


class DriftReport:
    """Result of comparing current agent state against registered snapshot."""

    def __init__(
        self,
        name: str,
        registered: bool,
        has_drift: bool,
        changes: list[DriftChange],
    ) -> None:
        self.name = name
        self.registered = registered
        self.has_drift = has_drift
        self.changes = changes


class DriftChange:
    """A single field-level change detected during drift comparison."""

    def __init__(
        self,
        field: str,
        kind: str,  # "added", "removed", "modified"
        old_value: Any = None,
        new_value: Any = None,
    ) -> None:
        self.field = field
        self.kind = kind
        self.old_value = old_value
        self.new_value = new_value

    def __repr__(self) -> str:
        return f"DriftChange({self.field!r}, {self.kind!r})"


def _hash_ir(ir_dict: dict[str, Any]) -> str:
    """Compute a content hash of an IR dict for change detection."""
    # Normalize by sorting keys and removing volatile fields
    stable = {k: v for k, v in ir_dict.items() if k not in ("metadata",)}
    canonical = json.dumps(stable, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _compute_changes(
    old: dict[str, Any],
    new: dict[str, Any],
    prefix: str = "",
) -> list[DriftChange]:
    """Recursively compute field-level changes between two IR dicts."""
    changes: list[DriftChange] = []

    all_keys = set(old.keys()) | set(new.keys())
    # Skip metadata — it changes between parses
    skip_keys = {"metadata"}

    for key in sorted(all_keys):
        if key in skip_keys:
            continue
        path = f"{prefix}.{key}" if prefix else key

        if key not in old:
            changes.append(DriftChange(field=path, kind="added", new_value=new[key]))
        elif key not in new:
            changes.append(DriftChange(field=path, kind="removed", old_value=old[key]))
        elif old[key] != new[key]:
            old_val = old[key]
            new_val = new[key]
            if isinstance(old_val, dict) and isinstance(new_val, dict):
                changes.extend(_compute_changes(old_val, new_val, prefix=path))
            elif isinstance(old_val, list) and isinstance(new_val, list):
                if len(old_val) != len(new_val):
                    changes.append(
                        DriftChange(
                            field=f"{path} (count)",
                            kind="modified",
                            old_value=len(old_val),
                            new_value=len(new_val),
                        )
                    )
                else:
                    for i, (a, b) in enumerate(zip(old_val, new_val, strict=False)):
                        if a != b:
                            if isinstance(a, dict) and isinstance(b, dict):
                                changes.extend(_compute_changes(a, b, prefix=f"{path}[{i}]"))
                            else:
                                changes.append(
                                    DriftChange(
                                        field=f"{path}[{i}]",
                                        kind="modified",
                                        old_value=a,
                                        new_value=b,
                                    )
                                )
            else:
                changes.append(
                    DriftChange(field=path, kind="modified", old_value=old_val, new_value=new_val)
                )

    return changes
