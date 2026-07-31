# CapCut Method 2

An independent request-signing implementation that does not require the
CapCut application or bundled dynamic libraries.

## Implemented primitives

- General `sign`
- Body-derived `X-SS-STUB`
- `X-Khronos`
- Full `X-Gorgon`, `X-Ladon`, and `X-Argus` paths for CapCut 9.1.0 arm64

`X-SS-Req-Ticket` remains an additional compatibility target where required.

## Research notes

The implementation is based on fixed synthetic requests traced with LLDB on
2026-07-31. The observed `X-Gorgon` input layout is:

```text
MD5(query)[:4] | X-SS-STUB[:4] | 00000000
| 24060605 | 32-bit big-endian X-Khronos
```

The macOS signing path keeps the cookie slot at `00000000` for synthetic
requests. Requests without `X-SS-STUB` use `00000000` for the body slot.

The subsequent transform differs from standard RC4: both KSA and PRGA use
`S[i] = S[j]` without the reverse swap. This variant and native bit
post-processing are implemented in `x_gorgon_mix`; `x_gorgon` emits the full
value with the `8404` header and four-byte prefix.

`X-Ladon` uses the following construction:

```text
digest = MD5(random4 || ASCII(app_id)).hexdigest()
key = ASCII(digest[:16])
iv = ASCII(digest[16:])
plaintext = PKCS7(ASCII(timestamp-license_id-app_id))
ciphertext = AES-128-CBC(plaintext, key, iv)
X-Ladon = Base64(random4 || ciphertext)
```

The CapCut 9.1.0 defaults are `app_id=359289` and `license_id=1369207606`.
AES-128, SM3, Blowfish, and the supporting serialization are implemented in
pure Python within this package.

`X-Argus` follows this high-level sequence:

```text
protobuf = CapCut macOS field serialization
inner_key = SM3(sign_key || random4 || sign_key)
inner_plaintext = 0000000000000000 || protobuf || PKCS7(block=8)
inner_ciphertext = Blowfish-CBC(inner_plaintext, inner_key, iv=0)
mixed = reverse(prefix8 || XOR(inner_ciphertext))
outer_plaintext = header9 || mixed || random4[2:4] || custom_padding
ciphertext = AES-128-CBC(outer_plaintext, MD5(sign_key[:16]), MD5(sign_key[16:]))
X-Argus = Base64(random4[:2] || ciphertext)
```

Runtime padding uses a safe random seed. A `padding_seed` may be supplied for
deterministic synthetic-vector verification.

```python
from capcut_method2 import x_argus

value = x_argus(
    "aid=359289&device_id=synthetic-device",
    b'{"dummy":1}',
    1785482891,
    device_id="synthetic-device",
)
```

## Tests

```bash
cd method2
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

Test vectors use synthetic inputs only. They do not contain captured device
identifiers, tokens, cookies, or live signature values.

## Research tools

Inspect signature shape, length, encoding, and version prefix without printing
captured signature values:

```bash
mitmdump -q -nr ../../capcut-research/private/captures/capcut-005.mitm \
  -s tools/inventory_signature_shapes.py
```

For native tracing, import the LLDB helper and run the synthetic harness:

```lldb
command script import method2/tools/lldb_trace_gorgon.py
method2-gorgon-trace
run request
```

Native tracing inputs and binaries remain local-only research artifacts.
