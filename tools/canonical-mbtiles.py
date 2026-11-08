#!/usr/bin/env python3
"""Serialise an MBTiles file into a canonical byte stream.

The delta pipeline patches this stream rather than the SQLite file, because the
file layout depends on insert order and page allocation: two builds with
identical content produce different bytes, and tile payloads are gzip streams
whose bytes change wholesale for a one-character edit. The canonical stream
fixes both by sorting rows, dropping page layout and storing tile payloads
decompressed.

The format is part of the client contract; the dashboard implements the same
writer in C++. Keep them in step.

    magic      "MBTC1\n"
    schema     for each sqlite_master row with non-null sql, ordered by (type,
               name): "S", then the four values (type, name, tbl_name, sql)
    table      for each user table (name not starting with "sqlite_"), ordered
               by name: "T", name value, then rows, then "E"
    row        "R", then one value per column in table_info order. Column order
               for "tiles" is rowid order (zoom_level, tile_column,
               tile_row); every other table is ordered by its primary key
               columns, or by all columns when it has no primary key.
    tile data  decompressed MVT bytes; the client re-compresses when rebuilding

Values: "n" null, "i" plus int64 big-endian, "f" plus float64 big-endian,
"s" plus uint32 length and UTF-8 bytes, "b" plus uint32 length and raw bytes.
"""

import argparse
import gzip
import hashlib
import sqlite3
import struct
import sys

MAGIC = b"MBTC1\n"


def _frame(buf, payload):
    buf += struct.pack(">I", len(payload))
    buf += payload


def _value(buf, value):
    if value is None:
        buf += b"n"
    elif isinstance(value, int):
        buf += b"i" + struct.pack(">q", value)
    elif isinstance(value, float):
        buf += b"f" + struct.pack(">d", value)
    elif isinstance(value, str):
        buf += b"s"
        _frame(buf, value.encode("utf-8"))
    elif isinstance(value, (bytes, bytearray, memoryview)):
        buf += b"b"
        _frame(buf, bytes(value))
    else:
        raise TypeError(f"unsupported value type {type(value)!r}")


def _order(conn, table):
    columns = [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]
    if table == "tiles":
        keys = ["zoom_level", "tile_column", "tile_row"]
    else:
        primary = sorted((row[5], row[1]) for row in conn.execute(
            f'PRAGMA table_info("{table}")') if row[5])
        keys = [name for _, name in primary] or columns
    return columns, ", ".join(f'"{name}"' for name in keys)


def write(conn, path):
    digest = hashlib.sha256()
    with open(path, "wb", buffering=1 << 20) as out:
        def emit(data):
            out.write(data)
            digest.update(data)

        emit(MAGIC)
        schema = list(conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE sql IS NOT NULL ORDER BY type, name"))
        for row in schema:
            chunk = bytearray(b"S")
            for value in row:
                _value(chunk, value)
            emit(bytes(chunk))

        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        for table in tables:
            columns, order = _order(conn, table)
            chunk = bytearray(b"T")
            _value(chunk, table)
            emit(bytes(chunk))
            tile_index = columns.index("tile_data") if table == "tiles" else None
            for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY {order}'):
                chunk = bytearray(b"R")
                for index, value in enumerate(row):
                    if index == tile_index:
                        value = gzip.decompress(value)
                    _value(chunk, value)
                emit(bytes(chunk))
            emit(b"E")
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mbtiles", type=str)
    parser.add_argument("output", type=str)
    parser.add_argument("--print-hash", action="store_true",
                        help="print the SHA-256 of the canonical stream")
    args = parser.parse_args()
    conn = sqlite3.connect(f"file:{args.mbtiles}?mode=ro", uri=True)
    try:
        digest = write(conn, args.output)
    finally:
        conn.close()
    if args.print_hash:
        print(digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
