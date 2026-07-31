"""Compare a standalone X-Gorgon candidate with captures in memory.

No captured header values, request values, cookies, or identifiers are printed.
"""

from __future__ import annotations

import hashlib
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from mitmproxy import http


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "method2"))

from capcut_method2.signatures import x_gorgon_material, x_gorgon_mix


GORGON_TABLE = bytes.fromhex("ce7c47e421ff095cc9da81690147cba1ed6cc4b1")
GORGON_INPUT_VERSION = bytes.fromhex("24060605")


def openapi_paths() -> set[str]:
    return {
        line.strip()[:-1]
        for line in (ROOT / "openapi.yaml").read_text().splitlines()
        if line.startswith("  /") and line.endswith(":")
    }


def reverse_bits(value: int) -> int:
    return int(f"{value:08b}"[::-1], 2)


def encode_suffix(
    params_hash: bytes,
    body_hash: bytes,
    cookie_hash: bytes,
    timestamp: int,
) -> bytes:
    buffer = bytearray(
        params_hash[:4]
        + body_hash[:4]
        + cookie_hash[:4]
        + GORGON_INPUT_VERSION
        + timestamp.to_bytes(4, "big")
    )
    for index in range(20):
        buffer[index] ^= GORGON_TABLE[index]
    for index in range(19):
        buffer[index] = (
            ((buffer[index] >> 4) | (buffer[index] << 4)) & 0xFF
        )
        buffer[index] ^= buffer[index + 1]
    for index in range(19):
        buffer[index] = reverse_bits(buffer[index]) ^ 0xEB
    buffer[19] = (
        ((buffer[19] >> 4) | (buffer[19] << 4)) & 0xFF
    )
    buffer[19] ^= buffer[0]
    buffer[19] = reverse_bits(buffer[19]) ^ 0xEB
    return bytes(buffer)


def swap_nibbles(value: int) -> int:
    return ((value >> 4) | (value << 4)) & 0xFF


def decode_pre_table(output: bytes) -> bytes:
    """Invert the public 20-byte Gorgon mixing stage."""

    if len(output) != 20:
        raise ValueError("X-Gorgon suffix must contain 20 bytes")
    mixed = bytearray(20)
    for index in range(19):
        mixed[index] = reverse_bits(output[index] ^ 0xEB)
    pre_table = bytearray(20)
    pre_table[19] = swap_nibbles(
        reverse_bits(output[19] ^ 0xEB) ^ output[0]
    )
    for index in range(18, -1, -1):
        pre_table[index] = swap_nibbles(
            mixed[index] ^ pre_table[index + 1]
        )
    return bytes(pre_table)


class Validator:
    def __init__(self):
        self.paths = openapi_paths()
        self.checked = 0
        self.suffix_matches = 0
        self.tables = Counter()
        self.prefixes = Counter()
        self.table_bytes = [Counter() for _ in range(20)]
        self.variant_tables: dict[str, Counter] = {}
        self.exact_variants = Counter()

    def request(self, flow: http.HTTPFlow):
        path = urlsplit(flow.request.pretty_url).path
        value = flow.request.headers.get("x-gorgon")
        timestamp = flow.request.headers.get("x-khronos")
        if path not in self.paths or not value or not timestamp:
            return
        query = urlsplit(flow.request.pretty_url).query.encode()
        body = flow.request.raw_content or b""
        cookie = flow.request.headers.get("cookie", "").encode()
        expected = bytes.fromhex(value)
        params_hash = hashlib.md5(query).digest()
        body_hash = hashlib.md5(body).digest()
        cookie_hash = hashlib.md5(cookie).digest() if cookie else bytes(16)
        stub = flow.request.headers.get("x-ss-stub")
        material = x_gorgon_material(
            query,
            body,
            cookie,
            int(timestamp),
            stub=stub,
        )
        candidate = x_gorgon_mix(material, expected[2:6])
        pre_table = decode_pre_table(expected[6:])
        table = bytes(a ^ b for a, b in zip(pre_table, material))
        self.tables[table] += 1
        self.prefixes[expected[:6]] += 1
        for index, byte in enumerate(table):
            self.table_bytes[index][byte] += 1
        query_inputs = {
            "query_md5": params_hash[:4],
            "query_raw": (query + bytes(4))[:4],
        }
        body_inputs = {
            "body_md5": body_hash[:4],
            "body_raw": (body + bytes(4))[:4],
            "body_zero": bytes(4),
        }
        if stub:
            body_inputs["body_stub"] = bytes.fromhex(stub)[:4]
        cookie_inputs = {
            "cookie_md5": cookie_hash[:4],
            "cookie_raw": (cookie + bytes(4))[:4],
            "cookie_zero": bytes(4),
        }
        tail = GORGON_INPUT_VERSION + int(timestamp).to_bytes(4, "big")
        for query_name, query_input in query_inputs.items():
            for body_name, body_input in body_inputs.items():
                for cookie_name, cookie_input in cookie_inputs.items():
                    name = f"{query_name}+{body_name}+{cookie_name}"
                    variant_material = query_input + body_input + cookie_input + tail
                    if (
                        x_gorgon_mix(variant_material, expected[2:6])
                        == expected[6:]
                    ):
                        self.exact_variants[name] += 1
                    variant_table = bytes(
                        a ^ b for a, b in zip(pre_table, variant_material)
                    )
                    self.variant_tables.setdefault(name, Counter())[variant_table] += 1
        self.checked += 1
        if expected[6:] == candidate:
            self.suffix_matches += 1

    def done(self):
        print(
            f"gorgon checked={self.checked}"
            f" suffix_matches={self.suffix_matches}"
            f" mismatches={self.checked - self.suffix_matches}"
            f" derived_tables={len(self.tables)}"
            f" most_common_table_uses="
            f"{self.tables.most_common(1)[0][1] if self.tables else 0}"
            f" prefixes={len(self.prefixes)}"
            f" unique_values_per_table_byte="
            f"{','.join(str(len(values)) for values in self.table_bytes)}"
        )
        ranked = sorted(
            (
                (len(tables), -tables.most_common(1)[0][1], name)
                for name, tables in self.variant_tables.items()
            )
        )
        for unique_count, negative_common, name in ranked[:8]:
            print(
                f"variant={name} derived_tables={unique_count}"
                f" most_common_table_uses={-negative_common}"
            )
        for name, count in self.exact_variants.most_common():
            print(f"exact_variant={name} matches={count}")


addons = [Validator()]
