"""Pure-Python request signatures recovered from CapCut 9.1.0."""

from __future__ import annotations

import base64
import hashlib
import secrets
import struct
import time

from ._blowfish import blowfish_cbc_encrypt


GORGON_INPUT_VERSION = bytes.fromhex("24060605")
GORGON_HEADER = bytes.fromhex("8404")
CAPCUT_APP_ID = 359289
LADON_LICENSE_ID = 1369207606
ARGUS_SIGN_KEY = base64.b64decode(
    "sD3hXOFeh2yHhf3mFKRRCKd9NLRoEXedYNslC3zxvSc="
)
ARGUS_SDK_VERSION = "v05.06.06-ov-mac"
ARGUS_SDK_VERSION_CODE = 84280868


def _gf_multiply(left: int, right: int) -> int:
    result = 0
    for _ in range(8):
        if right & 1:
            result ^= left
        left = ((left << 1) ^ (0x11B if left & 0x80 else 0)) & 0xFF
        right >>= 1
    return result


def _aes_sbox(value: int) -> int:
    inverse = 0
    if value:
        inverse = 1
        power = value
        exponent = 254
        while exponent:
            if exponent & 1:
                inverse = _gf_multiply(inverse, power)
            power = _gf_multiply(power, power)
            exponent >>= 1
    return (
        inverse
        ^ ((inverse << 1) | (inverse >> 7))
        ^ ((inverse << 2) | (inverse >> 6))
        ^ ((inverse << 3) | (inverse >> 5))
        ^ ((inverse << 4) | (inverse >> 4))
        ^ 0x63
    ) & 0xFF


_AES_SBOX = bytes(_aes_sbox(value) for value in range(256))


def _aes128_round_keys(key: bytes) -> bytes:
    if len(key) != 16:
        raise ValueError("AES-128 key must be exactly 16 bytes")
    expanded = bytearray(key)
    rcon = 1
    while len(expanded) < 176:
        word = list(expanded[-4:])
        if len(expanded) % 16 == 0:
            word = [
                _AES_SBOX[word[1]] ^ rcon,
                _AES_SBOX[word[2]],
                _AES_SBOX[word[3]],
                _AES_SBOX[word[0]],
            ]
            rcon = _gf_multiply(rcon, 2)
        for value in word:
            expanded.append(expanded[-16] ^ value)
    return bytes(expanded)


def _aes128_encrypt_block(block: bytes, round_keys: bytes) -> bytes:
    if len(block) != 16 or len(round_keys) != 176:
        raise ValueError("AES-128 requires a 16-byte block and expanded key")
    state = bytearray(
        value ^ round_keys[index] for index, value in enumerate(block)
    )
    for round_index in range(1, 11):
        state = bytearray(_AES_SBOX[value] for value in state)
        state = bytearray(
            state[index]
            for index in (0, 5, 10, 15, 4, 9, 14, 3, 8, 13, 2, 7, 12, 1, 6, 11)
        )
        if round_index != 10:
            for offset in range(0, 16, 4):
                first, second, third, fourth = state[offset : offset + 4]
                state[offset : offset + 4] = bytes(
                    (
                        _gf_multiply(first, 2)
                        ^ _gf_multiply(second, 3)
                        ^ third
                        ^ fourth,
                        first
                        ^ _gf_multiply(second, 2)
                        ^ _gf_multiply(third, 3)
                        ^ fourth,
                        first
                        ^ second
                        ^ _gf_multiply(third, 2)
                        ^ _gf_multiply(fourth, 3),
                        _gf_multiply(first, 3)
                        ^ second
                        ^ third
                        ^ _gf_multiply(fourth, 2),
                    )
                )
        key_offset = round_index * 16
        for index in range(16):
            state[index] ^= round_keys[key_offset + index]
    return bytes(state)


def _aes128_cbc_encrypt(plaintext: bytes, key: bytes, iv: bytes) -> bytes:
    if len(plaintext) % 16:
        raise ValueError("AES-CBC plaintext must be block aligned")
    if len(iv) != 16:
        raise ValueError("AES-CBC IV must be exactly 16 bytes")
    round_keys = _aes128_round_keys(key)
    previous = iv
    ciphertext = bytearray()
    for offset in range(0, len(plaintext), 16):
        block = bytes(
            left ^ right
            for left, right in zip(
                plaintext[offset : offset + 16], previous
            )
        )
        previous = _aes128_encrypt_block(block, round_keys)
        ciphertext.extend(previous)
    return bytes(ciphertext)


def _rotate_left32(value: int, count: int) -> int:
    count %= 32
    return ((value << count) | (value >> (32 - count))) & 0xFFFFFFFF


def _sm3(data: bytes) -> bytes:
    """Return the Chinese SM3 digest without relying on OpenSSL support."""

    state = [
        0x7380166F,
        0x4914B2B9,
        0x172442D7,
        0xDA8A0600,
        0xA96F30BC,
        0x163138AA,
        0xE38DEE4D,
        0xB0FB0E4E,
    ]
    bit_length = len(data) * 8
    padding = b"\x80" + bytes((55 - len(data)) % 64)
    padded = data + padding + bit_length.to_bytes(8, "big")
    for block_offset in range(0, len(padded), 64):
        words = list(struct.unpack(">16I", padded[block_offset : block_offset + 64]))
        words.extend([0] * 52)
        derived = [0] * 64
        for index in range(16, 68):
            value = (
                words[index - 16]
                ^ words[index - 9]
                ^ _rotate_left32(words[index - 3], 15)
            )
            value ^= _rotate_left32(value, 15) ^ _rotate_left32(value, 23)
            words[index] = (
                value
                ^ _rotate_left32(words[index - 13], 7)
                ^ words[index - 6]
            )
        for index in range(64):
            derived[index] = words[index] ^ words[index + 4]

        a, b, c, d, e, f, g, h = state
        for index in range(64):
            constant = 0x79CC4519 if index < 16 else 0x7A879D8A
            first = _rotate_left32(
                (_rotate_left32(a, 12) + e + _rotate_left32(constant, index))
                & 0xFFFFFFFF,
                7,
            )
            second = first ^ _rotate_left32(a, 12)
            if index < 16:
                ff = a ^ b ^ c
                gg = e ^ f ^ g
            else:
                ff = (a & b) | (a & c) | (b & c)
                gg = (e & f) | ((~e) & g)
            first_temp = (ff + d + second + derived[index]) & 0xFFFFFFFF
            second_temp = (gg + h + first + words[index]) & 0xFFFFFFFF
            d = c
            c = _rotate_left32(b, 9)
            b = a
            a = first_temp
            h = g
            g = _rotate_left32(f, 19)
            f = e
            e = (
                second_temp
                ^ _rotate_left32(second_temp, 9)
                ^ _rotate_left32(second_temp, 17)
            )
        state = [
            left ^ right
            for left, right in zip(state, (a, b, c, d, e, f, g, h))
        ]
    return struct.pack(">8I", *state)


def _protobuf_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("protobuf varints must be non-negative")
    output = bytearray()
    while value >= 0x80:
        output.append((value & 0x7F) | 0x80)
        value >>= 7
    output.append(value)
    return bytes(output)


def _protobuf_field_varint(field: int, value: int) -> bytes:
    return _protobuf_varint(field << 3) + _protobuf_varint(value)


def _protobuf_field_bytes(field: int, value: bytes | str) -> bytes:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return (
        _protobuf_varint((field << 3) | 2)
        + _protobuf_varint(len(value))
        + value
    )


def _argus_protobuf(
    query: bytes,
    stub_digest: bytes,
    timestamp: int,
    *,
    app_id: int,
    device_id: str,
    license_id: int,
    sdk_version: str,
    sdk_version_code: int,
    device_type: str,
    channel: str,
    random_value: int,
    request_random: int,
) -> bytes:
    if not 0 <= random_value <= 0x7FFFFFFF:
        raise ValueError("X-Argus protobuf random value must fit in 31 bits")
    if not 0 <= request_random <= 0x7FFFFFFF:
        raise ValueError("X-Argus request random value must fit in 31 bits")
    request_state = (
        _protobuf_field_varint(1, 2)
        + _protobuf_field_varint(2, 2)
        + _protobuf_field_varint(6, request_random << 1)
        + _protobuf_field_varint(7, timestamp << 1)
    )
    device_state = (
        _protobuf_field_bytes(1, device_type)
        + _protobuf_field_varint(2, 23 << 1)
        + _protobuf_field_bytes(3, channel)
        + _protobuf_field_varint(4, 1999997)
    )
    return b"".join(
        (
            _protobuf_field_varint(1, 0x20200929 << 1),
            _protobuf_field_varint(2, 2),
            _protobuf_field_varint(3, random_value << 1),
            _protobuf_field_bytes(4, str(app_id)),
            _protobuf_field_bytes(5, device_id),
            _protobuf_field_bytes(6, str(license_id)),
            _protobuf_field_bytes(8, sdk_version),
            _protobuf_field_varint(9, sdk_version_code << 1),
            _protobuf_field_bytes(10, bytes.fromhex("8080000000000000")),
            _protobuf_field_varint(11, 5),
            _protobuf_field_varint(12, timestamp << 1),
            _protobuf_field_bytes(13, _sm3(stub_digest)[:6]),
            _protobuf_field_bytes(14, _sm3(query)[:6]),
            _protobuf_field_bytes(15, request_state),
            _protobuf_field_varint(17, timestamp << 1),
            _protobuf_field_bytes(20, "none"),
            _protobuf_field_varint(21, 369 << 1),
            _protobuf_field_bytes(23, device_state),
            _protobuf_field_varint(25, 2),
            _protobuf_field_varint(28, 10 << 1),
        )
    )


def _argus_mix(random_tail: bytes) -> bytes:
    if len(random_tail) != 2:
        raise ValueError("X-Argus mix input must be exactly two bytes")
    combined = random_tail[0]
    result = ~(
        combined
        ^ (combined >> 5)
        ^ (random_tail[1] | ((combined << 11) & 0xFFFFFFFF))
    ) & 0xFFFFFFFF
    mixed = bytearray(result.to_bytes(4, "little"))
    first = bytearray(mixed)
    first[0] ^= 0x80
    first[1] ^= 0x80
    return bytes(first + mixed)


def _argus_outer_padding(
    plaintext: bytes, padding_seed: int
) -> bytes:
    padding_length = 16 - (len(plaintext) % 16)
    padded = bytearray(plaintext + bytes(padding_length))
    padded[-1] = padding_length
    if padding_length >= 2:
        checksum = 0
        for value in padded[:8]:
            checksum ^= value
        padded[-2] = checksum
    for counter in range(1, padding_length - 1):
        padded[-2 - counter] = (padding_seed >> (counter * 2)) & 0xFF
    return bytes(padded)


def x_argus(
    query: bytes | str,
    body: bytes | str,
    timestamp: int,
    *,
    app_id: int = CAPCUT_APP_ID,
    device_id: str,
    license_id: int = LADON_LICENSE_ID,
    sdk_version: str = ARGUS_SDK_VERSION,
    sdk_version_code: int = ARGUS_SDK_VERSION_CODE,
    device_type: str = "Mac15,9",
    channel: str = "appstore",
    stub: bytes | str | None = None,
    random_bytes: bytes | None = None,
    protobuf_random: int | None = None,
    request_random: int | None = None,
    header_random: bytes | None = None,
    padding_seed: int | None = None,
) -> str:
    """Return CapCut 9.1.0's standalone Base64 ``X-Argus`` value.

    The optional entropy arguments expose every native random input for
    reproducible vectors. ``padding_seed`` represents the low bits of the
    native output-buffer address that its custom AES padding leaks; a random
    seed is used outside deterministic tests.
    """

    if isinstance(query, str):
        query = query.encode("utf-8")
    if isinstance(body, str):
        body = body.encode("utf-8")
    if stub is None:
        stub_digest = hashlib.md5(body).digest()
    else:
        if isinstance(stub, str):
            try:
                stub_digest = bytes.fromhex(stub)
            except ValueError as error:
                raise ValueError(
                    "X-SS-STUB must contain 32 hexadecimal characters"
                ) from error
        else:
            stub_digest = bytes(stub)
        if len(stub_digest) != 16:
            raise ValueError(
                "X-SS-STUB must contain 16 digest bytes or 32 hexadecimal characters"
            )

    if random_bytes is None:
        random_bytes = secrets.token_bytes(4)
    if len(random_bytes) != 4:
        raise ValueError("X-Argus random prefix must be exactly four bytes")
    if protobuf_random is None:
        protobuf_random = secrets.randbits(31)
    if request_random is None:
        request_random = secrets.randbelow(231) + 20
    if header_random is None:
        header_random = secrets.token_bytes(5)
    if len(header_random) != 5:
        raise ValueError("X-Argus header random input must be exactly five bytes")
    if padding_seed is None:
        padding_seed = secrets.randbits(30) & ~3
    if padding_seed < 0:
        raise ValueError("X-Argus padding seed must be non-negative")

    protobuf = _argus_protobuf(
        query,
        stub_digest,
        int(timestamp),
        app_id=int(app_id),
        device_id=str(device_id),
        license_id=int(license_id),
        sdk_version=sdk_version,
        sdk_version_code=int(sdk_version_code),
        device_type=device_type,
        channel=channel,
        random_value=protobuf_random,
        request_random=request_random,
    )
    inner_padding = 8 - ((8 + len(protobuf)) % 8)
    inner_plaintext = (
        bytes(8) + protobuf + bytes((inner_padding,)) * inner_padding
    )
    inner_key = _sm3(ARGUS_SIGN_KEY + random_bytes + ARGUS_SIGN_KEY)
    inner_ciphertext = blowfish_cbc_encrypt(
        inner_plaintext, inner_key, bytes(8)
    )

    transformed = bytearray(_argus_mix(random_bytes[2:]) + inner_ciphertext)
    # The native path toggles bit 7 in the first two prefix bytes only after
    # using the untoggled duplicate as the payload XOR key.
    xor_key = transformed[4:8]
    for index in range(8, len(transformed)):
        transformed[index] ^= xor_key[index % 4]
    transformed.reverse()
    header = (
        b"\xff"
        + header_random[:4]
        + b"\x01"
        + header_random[4:]
        + b"\x5b\x18"
    )
    outer_plaintext = (
        header + bytes(transformed) + random_bytes[2:]
    )
    outer_plaintext = _argus_outer_padding(
        outer_plaintext, padding_seed
    )
    key = hashlib.md5(ARGUS_SIGN_KEY[:16]).digest()
    iv = hashlib.md5(ARGUS_SIGN_KEY[16:]).digest()
    ciphertext = _aes128_cbc_encrypt(outer_plaintext, key, iv)
    return base64.b64encode(random_bytes[:2] + ciphertext).decode("ascii")


def _reverse_bits(value: int) -> int:
    value = ((value & 0x55) << 1) | ((value >> 1) & 0x55)
    value = ((value & 0x33) << 2) | ((value >> 2) & 0x33)
    return ((value & 0x0F) << 4) | ((value >> 4) & 0x0F)


def _gorgon_key(prefix: bytes) -> bytes:
    """Expand the four-byte wire prefix into the native eight-byte key."""

    if len(prefix) != 4:
        raise ValueError("X-Gorgon prefix must be exactly four bytes")
    return bytes(
        (0x05, prefix[2], 0x50, prefix[1], 0x47, 0x1E, prefix[3], prefix[0])
    )


def x_gorgon_mix(material: bytes, prefix: bytes) -> bytes:
    """Return the 20-byte encrypted suffix for a four-byte wire prefix.

    CapCut 9.1.0 uses an RC4-shaped transform whose state update deliberately
    copies ``S[j]`` to ``S[i]`` without writing the old ``S[i]`` back.
    """

    if len(material) != 20:
        raise ValueError("X-Gorgon material must be exactly 20 bytes")

    key = _gorgon_key(prefix)
    state = list(range(256))
    index_j = 0
    for index_i in range(256):
        index_j = (index_j + state[index_i] + key[index_i % len(key)]) & 0xFF
        state[index_i] = state[index_j]

    mixed = bytearray(material)
    index_i = 0
    index_j = 0
    for offset in range(len(mixed)):
        index_i = (index_i + 1) & 0xFF
        index_j = (index_j + state[index_i]) & 0xFF
        state[index_i] = state[index_j]
        stream_byte = state[(state[index_i] + state[index_j]) & 0xFF]
        mixed[offset] ^= stream_byte

    for offset in range(len(mixed)):
        value = (mixed[offset] >> 4) | ((mixed[offset] & 0x0F) << 4)
        next_value = mixed[offset + 1] if offset + 1 < len(mixed) else mixed[0]
        mixed[offset] = _reverse_bits(value ^ next_value) ^ 0xEB
    return bytes(mixed)


def x_gorgon(
    query: bytes | str,
    body: bytes | str,
    cookie: bytes | str,
    timestamp: int,
    *,
    stub: bytes | str | None = None,
    prefix: bytes | None = None,
) -> str:
    """Return the complete lowercase CapCut 9.1.0 ``X-Gorgon`` value.

    ``prefix`` is exposed for reproducible vectors. When omitted, four random
    bytes are masked with the native macOS prefix masks ``E0/FF/80/80``.
    """

    if prefix is None:
        random_bytes = secrets.token_bytes(4)
        prefix = bytes(
            (
                random_bytes[0] & 0xE0,
                random_bytes[1],
                random_bytes[2] & 0x80,
                random_bytes[3] & 0x80,
            )
        )
    material = x_gorgon_material(
        query, body, cookie, timestamp, stub=stub
    )
    return (GORGON_HEADER + prefix + x_gorgon_mix(material, prefix)).hex()


def business_sign(
    request_url: str,
    platform: str,
    app_version: str,
    device_time: str | int,
    device_id: str,
) -> str:
    """Return the lowercase business ``sign`` header.

    The input order and constants match CapCut 9.1.0's native signer.
    ``app_version`` is the portion of the ``appvr`` header before ``-``.
    """

    material = (
        f"9e2c|{request_url}|{platform}|{app_version}|"
        f"{device_time}|{device_id}|11ac"
    )
    return hashlib.md5(material.encode("utf-8")).hexdigest()


def x_ss_stub(body: bytes | str) -> str:
    """Return the uppercase MD5 body digest used by ``X-SS-STUB``."""

    if isinstance(body, str):
        body = body.encode("utf-8")
    return hashlib.md5(body).hexdigest().upper()


def x_khronos(timestamp: int | None = None) -> str:
    """Return the decimal Unix timestamp used by ``X-Khronos``."""

    return str(int(time.time()) if timestamp is None else int(timestamp))


def x_ladon(
    timestamp: int,
    license_id: str | int = LADON_LICENSE_ID,
    app_id: str | int = CAPCUT_APP_ID,
    *,
    random_bytes: bytes | None = None,
) -> str:
    """Return CapCut 9.1.0's Base64-encoded ``X-Ladon`` value.

    ``random_bytes`` is exposed only for reproducible vectors. The native
    signer derives an ASCII AES key and IV from the hexadecimal MD5 digest of
    ``random4 || app_id`` and encrypts ``timestamp-license_id-app_id`` with
    AES-128-CBC and PKCS#7 padding.
    """

    if random_bytes is None:
        random_bytes = secrets.token_bytes(4)
    if len(random_bytes) != 4:
        raise ValueError("X-Ladon random prefix must be exactly four bytes")
    app_id_text = str(app_id)
    digest_text = hashlib.md5(
        random_bytes + app_id_text.encode("ascii")
    ).hexdigest()
    key = digest_text[:16].encode("ascii")
    iv = digest_text[16:].encode("ascii")
    plaintext = (
        f"{int(timestamp)}-{license_id}-{app_id_text}".encode("ascii")
    )
    padding_length = 16 - (len(plaintext) % 16)
    padded = plaintext + bytes((padding_length,)) * padding_length
    ciphertext = _aes128_cbc_encrypt(padded, key, iv)
    return base64.b64encode(random_bytes + ciphertext).decode("ascii")


def x_gorgon_material(
    query: bytes | str,
    body: bytes | str,
    cookie: bytes | str,
    timestamp: int,
    *,
    stub: bytes | str | None = None,
) -> bytes:
    """Build CapCut 9.1.0's 20-byte input to the native Gorgon mixer.

    When ``stub`` is supplied it must be the 32-character hexadecimal
    ``X-SS-STUB`` value. Without it the body slot is zero. CapCut 9.1.0's
    macOS signer also leaves the four-byte cookie slot zero even when a Cookie
    header is present.
    """

    if isinstance(query, str):
        query = query.encode("utf-8")
    if isinstance(body, str):
        body = body.encode("utf-8")
    if isinstance(cookie, str):
        cookie = cookie.encode("utf-8")
    _ = cookie

    if stub is None:
        body_prefix = bytes(4)
    else:
        if isinstance(stub, bytes):
            try:
                stub = stub.decode("ascii")
            except UnicodeDecodeError as error:
                raise ValueError(
                    "X-SS-STUB must contain 32 hexadecimal characters"
                ) from error
        if len(stub) != 32:
            raise ValueError("X-SS-STUB must contain 32 hexadecimal characters")
        try:
            body_prefix = bytes.fromhex(stub)[:4]
        except ValueError as error:
            raise ValueError(
                "X-SS-STUB must contain 32 hexadecimal characters"
            ) from error

    return (
        hashlib.md5(query).digest()[:4]
        + body_prefix
        + bytes(4)
        + GORGON_INPUT_VERSION
        + int(timestamp).to_bytes(4, "big")
    )
