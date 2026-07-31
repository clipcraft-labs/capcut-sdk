"""Small, dependency-free Blowfish implementation used by X-Argus."""

from __future__ import annotations

import struct


_MASK32 = 0xFFFFFFFF


def _series(j: int, n: int, precision: int) -> int:
    digits = ((n + 1 + precision).bit_length() - 1) // 4 + precision + 3
    shift = 4 * digits
    total = 0
    denominator = j
    for index in range(n + 1):
        total += (pow(16, n - index, denominator) << shift) // denominator
        denominator += 8
    exponent = shift - 4
    denominator = 8 * (n + 1) + j
    while exponent >= 0:
        term = (1 << exponent) // denominator
        if not term:
            break
        total += term
        exponent -= 4
        denominator += 8
    return total


def _pi_hex_digits(count: int) -> str:
    """Return hexadecimal digits of pi after the radix point.

    Blowfish defines its initial P-array and S-boxes as the first 8336
    fractional hexadecimal digits of pi. Generating them keeps this module
    compact while remaining completely self-contained.
    """

    precision = count
    digits = ((precision + 1).bit_length() - 1) // 4 + precision + 3
    modulus = 16**digits - 1
    value = (
        4 * _series(1, 0, precision)
        - 2 * _series(4, 0, precision)
        - _series(5, 0, precision)
        - _series(6, 0, precision)
    ) & modulus
    return f"{value // 16 ** (digits - precision):0{precision}x}"


_INITIAL_WORDS: tuple[int, ...] | None = None


def _initial_words() -> tuple[int, ...]:
    global _INITIAL_WORDS
    if _INITIAL_WORDS is None:
        digits = _pi_hex_digits(1042 * 8)
        _INITIAL_WORDS = tuple(
            int(digits[offset : offset + 8], 16)
            for offset in range(0, len(digits), 8)
        )
    return _INITIAL_WORDS


class Blowfish:
    """Blowfish block cipher with the standard pi-derived initial state."""

    block_size = 8

    def __init__(self, key: bytes):
        if not 4 <= len(key) <= 56:
            raise ValueError("Blowfish key must contain 4 to 56 bytes")
        words = _initial_words()
        self.p = list(words[:18])
        self.s = [
            list(words[18 + box * 256 : 18 + (box + 1) * 256])
            for box in range(4)
        ]

        key_index = 0
        for index in range(18):
            value = 0
            for _ in range(4):
                value = (value << 8) | key[key_index]
                key_index = (key_index + 1) % len(key)
            self.p[index] ^= value

        left = right = 0
        for index in range(0, 18, 2):
            left, right = self.encrypt_words(left, right)
            self.p[index : index + 2] = (left, right)
        for box in self.s:
            for index in range(0, 256, 2):
                left, right = self.encrypt_words(left, right)
                box[index : index + 2] = (left, right)

    def _f(self, value: int) -> int:
        result = (
            self.s[0][value >> 24]
            + self.s[1][(value >> 16) & 0xFF]
        ) & _MASK32
        result ^= self.s[2][(value >> 8) & 0xFF]
        return (result + self.s[3][value & 0xFF]) & _MASK32

    def encrypt_words(self, left: int, right: int) -> tuple[int, int]:
        for index in range(16):
            left ^= self.p[index]
            right ^= self._f(left)
            left, right = right, left
        return right ^ self.p[17], left ^ self.p[16]

    def encrypt_block(self, block: bytes) -> bytes:
        if len(block) != self.block_size:
            raise ValueError("Blowfish requires an 8-byte block")
        return struct.pack(
            ">II", *self.encrypt_words(*struct.unpack(">II", block))
        )


def blowfish_cbc_encrypt(plaintext: bytes, key: bytes, iv: bytes) -> bytes:
    if len(plaintext) % Blowfish.block_size:
        raise ValueError("Blowfish-CBC plaintext must be block aligned")
    if len(iv) != Blowfish.block_size:
        raise ValueError("Blowfish-CBC IV must be exactly 8 bytes")
    cipher = Blowfish(key)
    previous = iv
    output = bytearray()
    for offset in range(0, len(plaintext), Blowfish.block_size):
        block = bytes(
            left ^ right
            for left, right in zip(
                plaintext[offset : offset + Blowfish.block_size], previous
            )
        )
        previous = cipher.encrypt_block(block)
        output.extend(previous)
    return bytes(output)
