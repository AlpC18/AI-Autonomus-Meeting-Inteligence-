# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Project Recall engine: audio, diarization, memory, and actions.

Each subpackage owns exactly one responsibility and must not import the
internals of another.
"""

import os

# Models (speech, embeddings, speakers) are downloaded on first use. The Hugging
# Face default of 10 s per request times out on slower connections for the
# ~1 GB embedding model, so the first start would fail; set before any import of
# huggingface_hub reads it, and only when the user has not chosen a value.
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "30")
