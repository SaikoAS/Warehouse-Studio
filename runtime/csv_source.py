"""Decode original CSV bytes and preserve the physical start line of each record."""

import base64
import codecs
import csv
from io import StringIO
from itertools import chain, islice


MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_PREVIEW_BYTES = 2 * 1024 * 1024
MAX_COLUMNS = 64
MAX_HEADER_LENGTH = 120
MAX_CELL_LENGTH = 4096
MAX_ROWS = 200_000
MAX_CELLS = 1_000_000
PREVIEW_ROWS = 10
ENCODINGS = {
    "utf-8": ("UTF-8", "utf-8", codecs.BOM_UTF8),
    "utf-16-le": ("UTF-16 LE", "utf-16-le", codecs.BOM_UTF16_LE),
    "utf-16-be": ("UTF-16 BE", "utf-16-be", codecs.BOM_UTF16_BE),
    "windows-1252": ("Windows-1252", "cp1252", b""),
}
DELIMITERS = (";", ",")


def upload(request, limit):
    name, encoded = request.get("name"), request.get("content")
    if not isinstance(name, str) or not 1 <= len(name) <= 255 or not isinstance(encoded, str):
        raise ValueError("Choose a CSV file.")
    try:
        source = base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise ValueError("The upload could not be read. Choose the CSV file again.") from error
    if len(source) > limit:
        raise ValueError(f"The CSV upload exceeds the {limit:,}-byte limit.")
    return name, source


def decode(source, encoding, truncated=False):
    label, codec, bom = ENCODINGS[encoding]
    try:
        text = codecs.getincrementaldecoder(codec)().decode(source.removeprefix(bom), final=not truncated)
    except UnicodeDecodeError as error:
        raise ValueError(f"Cannot read this CSV as {label}. Check the character encoding.") from error
    if truncated:
        # A slice may end in the middle of a physical line or between CR and LF.
        text = text.removesuffix("\r")
        text = text[:max(text.rfind("\r"), text.rfind("\n")) + 1]
    return text


def decode_preview(source, encoding, truncated):
    try:
        return decode(source, encoding, truncated), truncated, None
    except ValueError as error:
        underlying = error.__cause__
        # The display can still show a complete sample before a later decoding error.
        prefix = decode(underlying.object[:underlying.start], encoding, truncated=True)
        return prefix, True, error


def records(text, delimiter, truncated=False):
    reader = csv.reader(StringIO(text, newline=""), delimiter=delimiter, strict=True)
    while True:
        line = reader.line_num + 1
        try:
            cells = next(reader)
        except StopIteration:
            return
        except csv.Error as error:
            if truncated and str(error) == "unexpected end of data":
                return
            raise ValueError(f"Invalid CSV at line {line}: {error}.") from error
        if cells:
            yield line, cells


def header_names(cells):
    names = [cell.strip() for cell in cells]
    if (not 1 <= len(names) <= MAX_COLUMNS or len(set(names)) != len(names)
            or any(not 1 <= len(name) <= MAX_HEADER_LENGTH for name in names)):
        raise ValueError(f"Use up to {MAX_COLUMNS} unique, non-empty column names (up to {MAX_HEADER_LENGTH} characters each).")
    return names


def custom_headers(value, delimiter):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 16_384:
        raise ValueError("Enter custom column names in one record using the chosen delimiter.")
    entered = list(islice(records(value, delimiter), 2))
    if len(entered) != 1:
        raise ValueError("Enter custom column names in one record using the chosen delimiter.")
    return header_names(entered[0][1])


def table(text, delimiter, assigned_names, truncated=False):
    rows = records(text, delimiter, truncated)
    first = next(rows, None)
    if first is None:
        raise ValueError("The preview has no complete CSV records." if truncated else "The CSV has no records.")
    if assigned_names is None:
        original_names = first[1]
        names = header_names(original_names)
    else:
        names = original_names = assigned_names
        rows = chain((first,), rows)
    return [{"name": name, "type": "text"} for name in names], original_names, validated_rows(rows, len(names))


def validated_rows(rows, width):
    for count, (line, cells) in enumerate(rows, 1):
        if count > MAX_ROWS or count * width > MAX_CELLS:
            raise ValueError(f"The CSV exceeds the limit of {MAX_ROWS:,} data records or {MAX_CELLS:,} data cells.")
        if len(cells) != width:
            raise ValueError(f"CSV line {line} has {len(cells)} fields. Expected {width}.")
        if any(len(cell) > MAX_CELL_LENGTH for cell in cells):
            raise ValueError(f"CSV line {line} has a field longer than {MAX_CELL_LENGTH} characters.")
        yield line, cells


def sample_widths(text, delimiter, truncated):
    try:
        return [len(cells) for _, cells in islice(records(text, delimiter, truncated), PREVIEW_ROWS + 1)]
    except ValueError:
        return []


def detect_encoding(source, truncated):
    for bom, encoding in ((codecs.BOM_UTF8, "utf-8"), (codecs.BOM_UTF16_LE, "utf-16-le"),
                          (codecs.BOM_UTF16_BE, "utf-16-be")):
        if source.startswith(bom):
            return encoding
    sample = source[:2048]
    if len(sample) >= 8:
        even, odd = sample[::2], sample[1::2]
        even_zeros, odd_zeros = even.count(0) / len(even), odd.count(0) / len(odd)
        if odd_zeros >= 0.3 and even_zeros <= 0.08:
            return "utf-16-le"
        if even_zeros >= 0.3 and odd_zeros <= 0.08:
            return "utf-16-be"
    try:
        decode(source, "utf-8", truncated)
    except ValueError:
        try:
            text = decode(source, "windows-1252", truncated)
        except ValueError:
            return None
        if all(character >= " " or character in "\r\n\t" for character in text):
            for delimiter in DELIMITERS:
                widths = sample_widths(text, delimiter, truncated)
                if widths and len(set(widths)) == 1 and widths[0] <= MAX_COLUMNS:
                    return "windows-1252"
        return None
    return "utf-8"


def detect_delimiter(text, truncated):
    candidates = []
    for delimiter in DELIMITERS:
        widths = sample_widths(text, delimiter, truncated)
        if len(widths) >= 2 and len(set(widths)) == 1 and 1 < widths[0] <= MAX_COLUMNS:
            candidates.append(delimiter)
    return candidates[0] if len(candidates) == 1 else None


def option(request, name, choices, default=None):
    value = request.get(name, default)
    if value is not None and (not isinstance(value, str) or value not in choices):
        raise ValueError(f"Choose a supported CSV {name}.")
    return value


def preview(_db, request):
    name, source = upload(request, MAX_PREVIEW_BYTES)
    truncated = request.get("truncated", False)
    if type(truncated) is not bool:
        raise ValueError("Invalid CSV preview sample.")
    manual_encoding = option(request, "encoding", ENCODINGS)
    manual_delimiter = option(request, "delimiter", DELIMITERS)
    suggested_encoding = detect_encoding(source, truncated)
    suggested_delimiter = None
    sample = None
    error = None
    try:
        encoding = manual_encoding or suggested_encoding
        if encoding is None:
            raise ValueError("The encoding could not be detected. Choose a character encoding.")
        text, partial, decoding_error = decode_preview(source, encoding, truncated)
        suggested_delimiter = detect_delimiter(text, partial)
        delimiter = manual_delimiter or suggested_delimiter
        if delimiter is None:
            if decoding_error is not None:
                raise decoding_error
            raise ValueError("The delimiter is ambiguous or there are too few records. Choose a delimiter.")
        assigned_names = custom_headers(request.get("headers"), delimiter)
        if decoding_error is not None and not text:
            raise decoding_error
        columns, _, rows = table(text, delimiter, assigned_names, partial)
        rows = list(islice(rows, PREVIEW_ROWS))
        if decoding_error is not None and len(rows) < PREVIEW_ROWS:
            raise decoding_error
        sample = {"name": name, "encoding": encoding, "delimiter": delimiter, "columns": columns,
                  "rows": rows}
    except ValueError as cause:
        error = str(cause)
    return {"suggestedEncoding": suggested_encoding, "suggestedDelimiter": suggested_delimiter,
            "sample": sample, "error": error}
