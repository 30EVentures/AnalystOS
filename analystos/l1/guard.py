"""L1 - input guards shared by every route and reader (overnight round 1).

An upload is untrusted bytes. Three things the readers used to leave to chance:

* a file that is not really the format its extension claims (a damaged ``.xlsx``,
  a text file renamed ``.pdf``) raised whatever the parsing library raised
  (``zipfile.BadZipFile``, a pdfminer error, ...) out of the route as an HTTP 500;
  ``unreadable_is_value_error`` turns that into the ``ValueError`` every caller
  already maps to a 4xx, with a message that names neither a library nor a path;
* ``.docx``/``.xlsx``/``.pptx`` are zip archives, and nothing bounded how far one
  expands (a few kilobytes of zeros inflate to gigabytes). ``check_archive``
  refuses one whose *declared* uncompressed size or entry count is over a cap
  before any parser opens it. Python's ``zipfile`` never reads past a member's
  declared size, so a header cannot understate the size to slip past this;
* the filename is the client's. ``upload_name`` keeps only its last component and
  refuses what the filesystem cannot hold (empty, NUL, over 255 bytes), so
  ``save`` cannot fail with an ``OSError`` after the request was accepted.
"""

import contextlib
import sys
import zipfile
from pathlib import Path

MAX_ARCHIVE_UNCOMPRESSED_BYTES = 250 * 1024 * 1024  # ~25x the 10 MB upload cap; real documents are far under
MAX_ARCHIVE_ENTRIES = 10000
MAX_FILENAME_BYTES = 255  # NAME_MAX on every filesystem we deploy to
_ARCHIVE_SUFFIXES = (".docx", ".xlsx", ".pptx")


def upload_name(filename):
    """The last path component of a client-supplied filename, or ``ValueError``."""
    name = Path(str(filename or "")).name
    if not name or "\x00" in name:
        raise ValueError("unusable upload filename")
    if len(name.encode("utf-8", "replace")) > MAX_FILENAME_BYTES:
        raise ValueError(f"the upload's filename is too long (over {MAX_FILENAME_BYTES} bytes)")
    return name


def check_archive(path):
    """Raise ``ValueError`` if ``path`` is an Office archive that expands too far
    (or has too many entries). Anything that is not a readable zip is left for the
    parser to refuse; a PDF or CSV is not an archive and is never inspected."""
    path = Path(path)
    if path.suffix.lower() not in _ARCHIVE_SUFFIXES:
        return None
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
    except (zipfile.BadZipFile, OSError):
        return None
    if len(infos) > MAX_ARCHIVE_ENTRIES:
        raise ValueError(f"this {path.suffix.lower()} file has too many entries ({len(infos)}) to read safely")
    if sum(info.file_size for info in infos) > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        raise ValueError(f"this {path.suffix.lower()} file expands to more than "
                         f"{MAX_ARCHIVE_UNCOMPRESSED_BYTES // (1024 * 1024)} MB, which is too large to read safely")
    return None


@contextlib.contextmanager
def unreadable_is_value_error(path):
    """Inside the block, anything a parsing library raises (except the ``ValueError``
    the readers raise on purpose) becomes a ``ValueError`` saying the file is damaged
    or not really the format it claims. The original is chained for the logs, never
    put in the message. Do not wrap a call that talks to a model or a network."""
    suffix = Path(path).suffix.lower()
    try:
        check_archive(path)
        yield
    except (ValueError, MemoryError):
        raise  # a ValueError is already the readers' own refusal; running out of memory is not "a damaged file"
    except Exception as exc:
        print(f"[analystos.l1] could not read a {suffix} file: {type(exc).__name__}", file=sys.stderr)  # type only, never content
        raise ValueError(f"could not read this file as {suffix}: it is damaged or not really a {suffix} file") from exc
