# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""The tenant and project that own a piece of stored memory."""

import hashlib
import re
from dataclasses import dataclass

_ID_PATTERN = re.compile(r"[A-Za-z0-9_.-]{1,64}")


@dataclass(frozen=True, slots=True)
class TenantScope:
    """Identifies whose data is being stored or searched.

    Every memory operation requires one. IDs are 1-64 characters from
    ``A-Z a-z 0-9 _ . -``, so they are safe in file names and can never contain
    the separator used to derive :attr:`collection_name`.

    Raises:
        ValueError: on construction, if either ID is malformed.
    """

    tenant_id: str
    project_id: str

    def __post_init__(self) -> None:
        for field, value in (("tenant_id", self.tenant_id), ("project_id", self.project_id)):
            if not isinstance(value, str) or not _ID_PATTERN.fullmatch(value):
                raise ValueError(
                    f"{field} must be 1-64 characters of letters, digits, '_', '.' or '-', "
                    f"got {value!r}"
                )

    @property
    def collection_name(self) -> str:
        """Name of the vector collection that holds only this scope's data.

        Derived from a hash of both IDs joined by ``/`` (which no ID may
        contain), so two different scopes can never map to the same name.
        """
        digest = hashlib.sha256(f"{self.tenant_id}/{self.project_id}".encode()).hexdigest()
        return f"scope_{digest[:40]}"
