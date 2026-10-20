"""Rows to and from CSV, JSON and TYTX files, one block at a time.

``query().fetch(destination=)`` writes through :func:`write_rows` and
``table.sql_insert(file)`` reads through :func:`read_records`. The format
comes from ``format=`` or from the file extension. CSV and JSON carry no
types: on import their values go through ``table.adaptRecord``. TYTX keeps
the types, one TYTX value per line.
"""
from __future__ import annotations

import csv
import datetime
import json
from os import PathLike
from pathlib import Path

import genro_tytx
from genro_bag import Bag

FORMATS = {'.csv': 'csv', '.json': 'json', '.tytx': 'tytx'}


def file_format(file, format=None):
    """The format of ``file``: ``format=`` first, then the extension of its path or name."""
    if format is not None:
        if format not in FORMATS.values():
            raise ValueError(f'Unknown data format {format!r}; use one of {sorted(FORMATS.values())}')
        return format
    name = file if isinstance(file, (str, PathLike)) else getattr(file, 'name', None)
    if not isinstance(name, (str, PathLike)):
        raise ValueError('A stream without a file name needs format=')
    suffix = Path(name).suffix.lower()
    if suffix not in FORMATS:
        raise ValueError(f'Unknown data file extension {suffix!r}; use one of {sorted(FORMATS)} or format=')
    return FORMATS[suffix]


def _text(value):
    if isinstance(value, (datetime.date, datetime.time, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, Bag):
        return value.to_xml()
    return str(value)


def write_rows(destination, chunks, format=None):
    """Write the row blocks of ``chunks`` to a path or an open text stream; return the row count."""
    format = file_format(destination, format)
    if isinstance(destination, (str, PathLike)):
        with open(destination, 'w', newline='', encoding='utf-8') as stream:
            return _WRITERS[format](stream, chunks)
    return _WRITERS[format](destination, chunks)


def _write_csv(stream, chunks):
    writer, count = None, 0
    for rows in chunks:
        for row in rows:
            if writer is None:
                writer = csv.writer(stream)
                writer.writerow(row.keys())
            writer.writerow(['' if value is None else _text(value) for value in row.values()])
            count += 1
    return count


def _write_json(stream, chunks):
    count = 0
    stream.write('[')
    for rows in chunks:
        for row in rows:
            stream.write(',\n' if count else '\n')
            stream.write(json.dumps(dict(row), default=_text))
            count += 1
    stream.write('\n]\n')
    return count


def _write_tytx(stream, chunks):
    count = 0
    for rows in chunks:
        for row in rows:
            stream.write(genro_tytx.to_tytx(dict(row)))
            stream.write('\n')
            count += 1
    return count


_WRITERS = {'csv': _write_csv, 'json': _write_json, 'tytx': _write_tytx}


def read_records(source, format=None):
    """Yield the records of an open text stream as dicts, without loading the whole file."""
    return _READERS[file_format(source, format)](source)


def _read_csv(stream):
    for row in csv.DictReader(stream):
        yield {key: (None if value == '' else value) for key, value in row.items()}


def _read_json(stream, size=65536):
    decoder = json.JSONDecoder()
    buffer, position, started = '', 0, False
    while True:
        while True:
            while position < len(buffer) and buffer[position] in ' \t\r\n,':
                position += 1
            if not started:
                if position < len(buffer):
                    if buffer[position] != '[':
                        raise ValueError('A JSON data file is an array of objects')
                    started, position = True, position + 1
                    continue
                break
            if position < len(buffer) and buffer[position] == ']':
                return
            try:
                record, end = decoder.raw_decode(buffer, position)
            except json.JSONDecodeError:
                break
            if not isinstance(record, dict):
                raise ValueError(f'A JSON data file holds objects, not {record!r}')
            yield record
            position = end
        block = stream.read(size)
        if not block:
            if started and buffer[position:].strip():
                raise ValueError('Truncated JSON data file')
            raise ValueError('A JSON data file is an array of objects')
        buffer, position = buffer[position:] + block, 0


def _read_tytx(stream):
    for line in stream:
        if line.strip():
            record = genro_tytx.from_tytx(line.rstrip('\n'))
            if not isinstance(record, dict):
                raise ValueError(f'A TYTX data line holds an object, not {record!r}')
            yield record


_READERS = {'csv': _read_csv, 'json': _read_json, 'tytx': _read_tytx}
