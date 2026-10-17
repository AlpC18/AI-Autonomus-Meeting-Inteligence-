# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Code context: which files of the team's codebase a live statement is about.

At start the engine indexes local checkouts (``RECALL_CODE_DIRS``): for
each source file, the words in its path, the names it defines and what it
imports. A statement naming a word that only a few files carry ("Paddle",
"refunds", "webhook") gets a hint listing those files. Nothing is read
from the network and file contents never leave the machine.
"""

import logging
import os
import re
import subprocess
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from recall.transcript import Segment

logger = logging.getLogger(__name__)


def _listing(text: str) -> frozenset[str]:
    """The whitespace-separated words of ``text`` (long word lists read better as text)."""
    return frozenset(text.split())


SOURCE_SUFFIXES = _listing(
    """.py .ts .tsx .js .jsx .mjs .rs .go .java .kt .swift .rb .php .cs .c .h .cpp .hpp .scala .sql
    .vue .svelte .proto .graphql .tf"""
)
SKIPPED_DIRS = _listing(
    "node_modules .git dist build target .venv venv __pycache__ vendor .next coverage"
)
MAX_FILES = 20_000
MAX_READ = 64_000
MAX_FILES_SHOWN = 5

_DEFINITION = re.compile(
    r"\b(?:def|class|function|fn|struct|interface|enum|trait|type|func|module)\s+([A-Za-z_]\w*)"
)
_IMPORT = re.compile(
    r"^\s*(?:import|from|use|require|#include|using)\b(.*)$", re.MULTILINE
)
_REQUIRE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")
_PARTS = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])")
_SPOKEN = re.compile(r"[^\W\d_]+")

# ponytail: a fixed list of everyday words; a word-frequency model would
# catch more, add one if hints fire on small talk.
EVERYDAY = _listing(
    """about after again agenda all also and another answer anything back because been before being
    best better between both call calls can cannot change check client clients code come could
    big customer customers date day days does doing done down each early email end even every
    everyone fast faster feature features feel find first fine from going good great have help
    here high how idea ideas into issue issues item items just keep know last later least less
    like line list little long look looks lot make many maybe mean meeting meetings more most
    move much must need next nice now number okay once only open other over page part people
    plan point problem project put question quick quite really right same see should show side
    since some something soon start still sure take talk task tasks team than thank thanks that
    the their them then there these they thing things think this those through time today
    tomorrow too track try under update user users very want week weeks well were what when
    where which while who why switch will with slow small work working would year yeah yes
    yesterday your"""
)


def _stem(word: str) -> str:
    word = word.lower()
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if (
        len(word) > 3
        and word.endswith("s")
        and not word.endswith(("ss", "os", "us", "is"))
    ):
        return word[:-1]
    return word


def _words(identifier: str) -> set[str]:
    """Lower-case stems of the parts of ``identifier`` (camelCase, snake_case, kebab-case)."""
    return {_stem(part) for part in _PARTS.findall(identifier) if len(part) >= 3}


@dataclass(frozen=True, slots=True)
class CodeFile:
    """One indexed source file, the words it is known by and those in its path."""

    path: str
    words: frozenset[str]
    named: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class CodeMatch:
    """The words of a statement found in the code, and the files carrying them (best first)."""

    topics: tuple[str, ...]
    files: tuple[CodeFile, ...]


def _listed(root: Path) -> list[str]:
    """Files of ``root`` as git tracks them, or a directory walk outside git."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            check=True,
            timeout=30,
        )
        return [
            name for name in result.stdout.decode(errors="replace").split("\0") if name
        ]
    except (OSError, subprocess.SubprocessError):
        names = []
        for directory, subdirs, files in os.walk(root):
            subdirs[:] = [name for name in subdirs if name not in SKIPPED_DIRS]
            names.extend(
                os.path.relpath(Path(directory) / name, root) for name in files
            )
        return names


def _path_words(relative: str) -> frozenset[str]:
    path = PurePosixPath(relative)
    words: set[str] = set()
    for part in (*path.parent.parts, path.stem):
        words |= _words(part)
    return frozenset(words)


def _file_words(relative: str, text: str) -> frozenset[str]:
    words = set(_path_words(relative))
    for name in _DEFINITION.findall(text):
        words |= _words(name)
    for line in _IMPORT.findall(text):
        words |= _words(line)
    for module in _REQUIRE.findall(text):
        words |= _words(module)
    return frozenset(words)


class CodeIndex:
    """Words → files over one or more local checkouts. Build with :meth:`build`."""

    def __init__(self, files: Sequence[CodeFile]) -> None:
        self.files = tuple(files)
        self._by_word: dict[str, list[CodeFile]] = defaultdict(list)
        for file in self.files:
            for word in file.words:
                self._by_word[word].append(file)
        # A word carried by more files than this says nothing about where to look.
        self._max_spread = max(5, len(self.files) // 10)

    @classmethod
    def build(cls, roots: Iterable[Path]) -> "CodeIndex":
        """Index the source files under ``roots``. Blocks; unreadable files are skipped."""
        roots = list(roots)
        files: list[CodeFile] = []
        for root in roots:
            prefix = f"{root.name}/" if len(roots) > 1 else ""
            for relative in _listed(root):
                pure = PurePosixPath(relative.replace(os.sep, "/"))
                if pure.suffix not in SOURCE_SUFFIXES or SKIPPED_DIRS.intersection(
                    pure.parts
                ):
                    continue
                try:
                    with (root / relative).open(
                        encoding="utf-8", errors="replace"
                    ) as handle:
                        text = handle.read(MAX_READ)
                except OSError:
                    continue
                files.append(
                    CodeFile(
                        prefix + str(pure),
                        _file_words(str(pure), text),
                        _path_words(str(pure)),
                    )
                )
                if len(files) >= MAX_FILES:
                    logger.warning("Code index stopped at %d files", MAX_FILES)
                    return cls(files)
        logger.info("Indexed %d source files for code context", len(files))
        return cls(files)

    def match(self, text: str) -> CodeMatch | None:
        """The files ``text`` is about, or ``None`` when it names nothing specific in the code."""
        spoken = {_stem(word) for word in _SPOKEN.findall(text) if len(word) >= 4}
        topics = sorted(
            word
            for word in spoken - EVERYDAY
            if 0 < len(self._by_word.get(word, ())) <= self._max_spread
        )
        if not topics:
            return None
        hits: Counter[str] = Counter()
        by_path: dict[str, CodeFile] = {}
        for word in topics:
            for file in self._by_word[word]:
                # A file named after the topic counts double.
                hits[file.path] += 2 if word in file.named else 1
                by_path[file.path] = file
        ranked = sorted(hits, key=lambda path: (_is_test(path), -hits[path], path))
        return CodeMatch(
            tuple(topics), tuple(by_path[path] for path in ranked[:MAX_FILES_SHOWN])
        )


def _is_test(path: str) -> bool:
    return (
        any(
            part in {"test", "tests", "__tests__", "spec"}
            for part in PurePosixPath(path).parts
        )
        or ".test." in path
    )


def _where(files: Sequence[CodeFile]) -> str:
    folders = Counter(str(PurePosixPath(file.path).parent) for file in files)
    folder, count = folders.most_common(1)[0]
    if count == len(files) and folder != ".":
        return f" under {folder}/"
    return ""


class CodeContext:
    """Hints about code a meeting mentions; each topic is shown once per meeting."""

    def __init__(self, index: CodeIndex) -> None:
        self._index = index
        self._shown: set[str] = set()

    def watch(self, segment: Segment) -> list[dict[str, Any]]:
        """Hints for ``segment``: at most one, naming the files it is about."""
        match = self._index.match(segment.text)
        if match is None:
            return []
        new = [topic for topic in match.topics if topic not in self._shown]
        if not new:
            return []
        self._shown.update(match.topics)
        paths = [file.path for file in match.files]
        return [
            {
                "kind": "code",
                "title": f"Code context: {', '.join(new)}",
                "body": f"{len(paths)} file(s){_where(match.files)} define, use or are named after this.",
                "details": paths,
            }
        ]

    def finish(self) -> str | None:
        """The meeting ended: forget what was shown. Adds nothing to the notes."""
        self._shown.clear()
        return None
