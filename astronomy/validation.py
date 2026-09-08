"""Validation helpers for external astronomy resources."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .catalogs import DEFAULT_MAX_STAR_RECORDS, iter_star_catalog_chunks
from .config import DE441KernelConfig, default_star_catalog_path

_REQUIRED_TARGETS = (10, 199, 299, 301, 399, 499, 599, 699, 799, 899, 999)


@dataclass(frozen=True)
class KernelValidationResult:
    """Validation report for a DE441 SPK kernel path."""

    path: str
    valid: bool
    exists: bool
    readable: bool
    segment_count: int = 0
    coverage_start_jd: Optional[float] = None
    coverage_end_jd: Optional[float] = None
    available_targets: Tuple[int, ...] = ()
    missing_targets: Tuple[int, ...] = ()
    messages: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class CatalogValidationResult:
    """Validation report for an external star catalog."""

    path: str
    valid: bool
    exists: bool
    readable: bool
    detected_format: str = ""
    star_count: int = 0
    messages: List[str] = field(default_factory=list)


def resolve_de441_kernel_path(path: Optional[str] = None) -> str:
    if path:
        return path
    return DE441KernelConfig.from_env().path


def resolve_star_catalog_path(path: Optional[str] = None) -> str:
    if path:
        return path
    return default_star_catalog_path()


def _open_validation_kernel(path: str):
    from jplephem.spk import SPK

    return SPK.open(path)


def validate_de441_kernel_file(path: Optional[str] = None) -> KernelValidationResult:
    resolved = resolve_de441_kernel_path(path)
    if not resolved:
        return KernelValidationResult(
            path="",
            valid=False,
            exists=False,
            readable=False,
            messages=["DE441 kernel path is not configured."],
        )

    if not os.path.isfile(resolved):
        return KernelValidationResult(
            path=resolved,
            valid=False,
            exists=False,
            readable=False,
            messages=[f"DE441 kernel file not found: {resolved}"],
        )

    try:
        kernel = _open_validation_kernel(resolved)
    except Exception as exc:
        return KernelValidationResult(
            path=resolved,
            valid=False,
            exists=True,
            readable=False,
            messages=[f"Failed to open DE441 kernel: {exc}"],
        )

    with kernel:
        segments = list(kernel.segments)
        targets = tuple(sorted({segment.target for segment in segments}))
        missing = tuple(target for target in _REQUIRED_TARGETS if target not in targets)
        start_jd = min((segment.start_jd for segment in segments), default=None)
        end_jd = max((segment.end_jd for segment in segments), default=None)
        messages = []
        if missing:
            messages.append(
                "Kernel is missing required targets: " + ", ".join(str(target) for target in missing)
            )
        if not resolved.lower().endswith(".bsp"):
            messages.append("Kernel path does not use a .bsp extension.")
        return KernelValidationResult(
            path=resolved,
            valid=not missing,
            exists=True,
            readable=True,
            segment_count=len(segments),
            coverage_start_jd=start_jd,
            coverage_end_jd=end_jd,
            available_targets=targets,
            missing_targets=missing,
            messages=messages or ["DE441 kernel validated."],
        )


def validate_star_catalog_file(
    path: Optional[str],
    catalog_format: Optional[str] = None,
    chunk_size: int = 1024,
    max_records: int = DEFAULT_MAX_STAR_RECORDS,
) -> CatalogValidationResult:
    """Validate a real external star catalog file."""
    resolved = resolve_star_catalog_path(path)
    if not resolved:
        return CatalogValidationResult(
            path="",
            valid=False,
            exists=False,
            readable=False,
            messages=["Star catalog path is not configured."],
        )
    if not os.path.isfile(resolved):
        return CatalogValidationResult(
            path=resolved,
            valid=False,
            exists=False,
            readable=False,
            messages=[f"Star catalog file not found: {resolved}"],
        )

    try:
        star_count = 0
        first_chunk = True
        for chunk in iter_star_catalog_chunks(
            resolved,
            catalog_format=catalog_format,
            chunk_size=chunk_size,
        ):
            star_count += len(chunk)
            if first_chunk and not chunk:
                raise ValueError("Catalog contains no star records.")
            first_chunk = False
            if star_count > max_records:
                raise ValueError(
                    f"Catalog exceeds the curated bright-star limit of {max_records} records."
                )
    except Exception as exc:
        return CatalogValidationResult(
            path=resolved,
            valid=False,
            exists=True,
            readable=False,
            detected_format=(catalog_format or ""),
            messages=[f"Failed to parse star catalog: {exc}"],
        )

    return CatalogValidationResult(
        path=resolved,
        valid=star_count > 0,
        exists=True,
        readable=True,
        detected_format=(catalog_format or os.path.splitext(resolved)[1].lstrip(".")),
        star_count=star_count,
        messages=[
            "Star catalog validated for bright-star helper use."
            if star_count > 0
            else "Catalog contains no stars."
        ],
    )
