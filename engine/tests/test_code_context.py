# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Code context: indexing a checkout and naming the files a statement is about."""

from pathlib import Path

from recall.context.code import CodeContext, CodeIndex
from recall.transcript import Segment


def said(text: str) -> Segment:
    return Segment("system", 0.0, 1.0, text, (), "Ana")


def checkout(root: Path) -> Path:
    files = {
        "services/payment/checkout.py": "import paddle\n\nclass CheckoutController:\n    pass\n",
        "services/payment/refunds.py": "from paddle import Refund\n\ndef issue_refund():\n    pass\n",
        "services/payment/webhooks.ts": "import { verify } from 'paddle-sdk';\nexport function handlePaddleWebhook() {}\n",
        "web/meeting/page.tsx": "export function MeetingPage() {}\n",
        "web/meeting/time.ts": "export function formatTime() {}\n",
        "node_modules/paddle/index.js": "function paddle() {}\n",
        "assets/logo.png": "\x89PNG",
    }
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="latin-1")  # "\x89PNG" is the first byte of a real PNG
    return root


def test_index_skips_vendored_and_binary_files(tmp_path: Path) -> None:
    index = CodeIndex.build([checkout(tmp_path)])
    paths = {file.path for file in index.files}
    assert "services/payment/checkout.py" in paths
    assert not any(path.startswith("node_modules") or path.endswith(".png") for path in paths)


def test_a_statement_about_a_library_names_the_files_using_it(tmp_path: Path) -> None:
    index = CodeIndex.build([checkout(tmp_path)])

    match = index.match("Should we move the payments off Paddle this quarter?")

    assert match is not None
    assert "paddle" in match.topics
    assert {file.path for file in match.files} == {
        "services/payment/checkout.py",
        "services/payment/refunds.py",
        "services/payment/webhooks.ts",
    }


def test_everyday_words_do_not_match(tmp_path: Path) -> None:
    index = CodeIndex.build([checkout(tmp_path)])
    assert index.match("Let's find a time for the next meeting") is None
    assert index.match("ok") is None


def test_each_topic_is_announced_once_per_meeting(tmp_path: Path) -> None:
    context = CodeContext(CodeIndex.build([checkout(tmp_path)]))

    (hint,) = context.watch(said("The refund flow is broken"))
    assert hint["kind"] == "code" and "services/payment/refunds.py" in hint["details"]
    assert context.watch(said("Again, refunds are broken")) == []
    assert context.finish() is None
    assert len(context.watch(said("refund again"))) == 1  # a new meeting
