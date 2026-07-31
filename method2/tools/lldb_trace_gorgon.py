"""LLDB callbacks for locating CapCut's native X-Gorgon input pipeline.

Load this file after creating the harness target:

    command script import method2/tools/lldb_trace_gorgon.py
    method2-gorgon-trace

The trace stays disabled until the harness enters its HTTP signer wrapper. It
then reports 4/8/12/20-byte copies whose stack belongs to the recovered Gorgon
function, plus the completed 20-byte mixer input. Run the harness only with the
repository's fixed dummy identifiers; the callback intentionally prints the
copied bytes needed for a test vector.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import struct

import lldb


MAX_HITS = 128
MAX_WATCH_HITS = 128
GORGON_ENTRY = 0xBFD7B84
GORGON_STOP = 0xBFD9CF4
GORGON_RC4_KEY_READY = 0xBFD682C
GORGON_MATERIAL_PREFIX_COPY = 0xBFD9598
GORGON_MATERIAL_READY = 0xBFD95C4
FORMAT_ALLOCATOR = 0xC072AC8
LADON_BLOCK_DISPATCH = 0xBFDB61C
LADON_KEY_READY = 0xBFDB6C4
LADON_DIGEST_DISPATCH = 0xBFDB6BC
ARGUS_BLOCK_DISPATCH = 0xBFDB32C
ARGUS_BLOCK_RETURN = 0xBFDB330
ARGUS_INNER_BUILDER = 0xC052240
ARGUS_AES_DISPATCH = 0xBFDB570
AES_KEY_SCHEDULE = 0xC0148B4
AES_ENCRYPT_BLOCK = 0xC014CF4
AES_CBC_ENCRYPT = 0xC0617A4
BYTE_ARRAY_FROM_DATA = 0xC031008
ARGUS_INNER_ENCRYPT = 0xC076BD8
_armed = False
_hit_count = 0
_last_copy = None
_copy_breakpoint = None
_move_breakpoint = None
_strlen_breakpoint = None
_format_breakpoint = None
_gorgon_entry_breakpoint = None
_rc4_key_breakpoint = None
_material_breakpoint = None
_ladon_dispatch_breakpoint = None
_ladon_key_breakpoint = None
_ladon_digest_breakpoint = None
_argus_dispatch_breakpoint = None
_argus_return_breakpoint = None
_argus_return_contexts = {}
_aes_key_breakpoint = None
_aes_block_breakpoint = None
_aes_cbc_breakpoint = None
_byte_array_breakpoint = None
_argus_inner_encrypt_breakpoint = None
_argus_aes_dispatch_breakpoint = None
_aes_return_contexts = {}
_aes_hit_count = 0
_current_timestamp = 0
_material_address = 0
_material_watchpoints = []
_watch_hit_count = 0
_watch_seen = set()
_mixer_address = 0
_mixer_watchpoints = []
_mixer_hit_count = 0
_mixer_seen = set()
_expected_material_prefix = b""
_query_digest = b""
_stub_digest = b""
_memory_scan_done = False


def _register_unsigned(frame: lldb.SBFrame, name: str) -> int:
    value = frame.FindRegister(name)
    return value.GetValueAsUnsigned(0) if value.IsValid() else 0


def _module_name(frame: lldb.SBFrame) -> str:
    module = frame.GetModule()
    if not module.IsValid():
        return ""
    return module.GetFileSpec().GetFilename() or ""


def _file_offset(frame: lldb.SBFrame) -> int:
    address = frame.GetPCAddress()
    return address.GetFileAddress() if address.IsValid() else lldb.LLDB_INVALID_ADDRESS


def _read_bytes(process: lldb.SBProcess, address: int, size: int) -> bytes | None:
    error = lldb.SBError()
    data = process.ReadMemory(address, size, error)
    return bytes(data) if error.Success() and len(data) == size else None


def _read_c_string(
    process: lldb.SBProcess, address: int, limit: int = 256
) -> str | None:
    error = lldb.SBError()
    try:
        value = process.ReadCStringFromMemory(address, limit, error)
    except SystemError:
        return None
    return value if error.Success() else None


def _read_libcpp_string(process: lldb.SBProcess, address: int) -> bytes | None:
    """Read Apple's 24-byte libc++ ``std::string`` representation."""

    value = _read_bytes(process, address, 24)
    if value is None:
        return None
    if value[0] & 1 == 0:
        size = value[0] >> 1
        return value[1 : 1 + size] if size <= 22 else None
    size = struct.unpack_from("<Q", value, 8)[0]
    pointer = struct.unpack_from("<Q", value, 16)[0]
    if size > 4096:
        return None
    return _read_bytes(process, pointer, size)


def _creator_breakpoint(
    target: lldb.SBTarget, file_address: int, callback: str
) -> lldb.SBBreakpoint | None:
    for index in range(target.GetNumModules()):
        module = target.GetModuleAtIndex(index)
        if "libVECreator" not in (module.GetFileSpec().GetFilename() or ""):
            continue
        address = module.ResolveFileAddress(file_address)
        if not address.IsValid():
            return None
        breakpoint = target.BreakpointCreateBySBAddress(address)
        breakpoint.SetScriptCallbackFunction(callback)
        breakpoint.SetAutoContinue(True)
        return breakpoint
    return None


def _clear_material_watchpoints(target: lldb.SBTarget) -> None:
    global _material_watchpoints, _mixer_watchpoints
    for watchpoint in _material_watchpoints + _mixer_watchpoints:
        if watchpoint.IsValid():
            target.DeleteWatchpoint(watchpoint.GetID())
    _material_watchpoints = []
    _mixer_watchpoints = []


def _install_material_watchpoints(frame: lldb.SBFrame) -> None:
    global _material_watchpoints
    target = frame.GetThread().GetProcess().GetTarget()
    debugger = target.GetDebugger()
    error = lldb.SBError()
    for offset, size in ((0, 8), (8, 8), (16, 4)):
        watchpoint = target.WatchAddress(
            _material_address + offset, size, True, True, error
        )
        if not error.Success() or not watchpoint.IsValid():
            print(
                "method2_material_watchpoint"
                f" offset={offset} size={size} unavailable={error.GetCString()}"
            )
            continue
        _material_watchpoints.append(watchpoint)
        debugger.HandleCommand(
            "watchpoint command add -F "
            f"{__name__}._material_access {watchpoint.GetID()}"
        )
        print(
            "method2_material_watchpoint"
            f" id={watchpoint.GetID()} offset={offset} size={size}"
        )


def _install_mixer_watchpoints(frame: lldb.SBFrame, address: int) -> None:
    global _mixer_watchpoints
    target = frame.GetThread().GetProcess().GetTarget()
    debugger = target.GetDebugger()
    for watchpoint in _material_watchpoints:
        watchpoint.SetEnabled(False)
    error = lldb.SBError()
    for offset in (0, 8, 16):
        watchpoint = target.WatchAddress(address + offset, 1, True, True, error)
        if not error.Success() or not watchpoint.IsValid():
            print(
                "method2_mixer_watchpoint"
                f" offset={offset} unavailable={error.GetCString()}"
            )
            continue
        _mixer_watchpoints.append(watchpoint)
        debugger.HandleCommand(
            "watchpoint command add -F "
            f"{__name__}._mixer_access {watchpoint.GetID()}"
        )
        print(
            "method2_mixer_watchpoint"
            f" id={watchpoint.GetID()} offset={offset}"
        )


def _signer_entered(frame: lldb.SBFrame, _location, _internal_dict) -> bool:
    global _armed, _format_breakpoint, _gorgon_entry_breakpoint
    global _rc4_key_breakpoint
    global _material_breakpoint, _last_copy, _material_address
    global _ladon_dispatch_breakpoint
    global _ladon_key_breakpoint
    global _ladon_digest_breakpoint
    global _argus_dispatch_breakpoint, _argus_return_breakpoint
    global _argus_return_contexts
    global _aes_key_breakpoint, _aes_block_breakpoint, _aes_cbc_breakpoint
    global _byte_array_breakpoint, _argus_inner_encrypt_breakpoint
    global _argus_aes_dispatch_breakpoint
    global _aes_return_contexts, _aes_hit_count
    global _watch_hit_count, _watch_seen, _mixer_address
    global _mixer_hit_count, _mixer_seen
    global _expected_material_prefix, _query_digest, _stub_digest
    global _memory_scan_done
    _armed = True
    _last_copy = None
    _material_address = 0
    _watch_hit_count = 0
    _watch_seen = set()
    _mixer_address = 0
    _mixer_hit_count = 0
    _mixer_seen = set()
    _clear_material_watchpoints(frame.GetThread().GetProcess().GetTarget())
    _memory_scan_done = False
    _aes_return_contexts = {}
    _argus_return_contexts = {}
    _aes_hit_count = 0
    process = frame.GetThread().GetProcess()
    url = _read_c_string(process, _register_unsigned(frame, "x0"), 4096) or ""
    headers = _read_c_string(
        process, _register_unsigned(frame, "x1"), 8192
    ) or ""
    query = url.partition("?")[2]
    stub_match = re.search(
        r"x-ss-stub\r\n([0-9A-Fa-f]{32})", headers, re.IGNORECASE
    )
    if query and stub_match:
        _query_digest = hashlib.md5(query.encode()).digest()
        _stub_digest = bytes.fromhex(stub_match.group(1))
        _expected_material_prefix = _query_digest[:4] + _stub_digest[:4]
        print(
            "method2_expected_material_prefix="
            + _expected_material_prefix.hex()
        )
    else:
        _expected_material_prefix = b""
        _query_digest = b""
        _stub_digest = b""
    if _copy_breakpoint is not None:
        _copy_breakpoint.SetEnabled(True)
    if _move_breakpoint is not None:
        _move_breakpoint.SetEnabled(True)
    if _strlen_breakpoint is not None:
        _strlen_breakpoint.SetEnabled(True)
    if _format_breakpoint is None:
        _format_breakpoint = _creator_breakpoint(
            frame.GetThread().GetProcess().GetTarget(),
            FORMAT_ALLOCATOR,
            f"{__name__}._format_entered",
        )
        print(
            "method2_format_breakpoint="
            + ("installed" if _format_breakpoint is not None else "unavailable")
        )
    if _gorgon_entry_breakpoint is None:
        _gorgon_entry_breakpoint = _creator_breakpoint(
            frame.GetThread().GetProcess().GetTarget(),
            GORGON_ENTRY,
            f"{__name__}._gorgon_entry",
        )
        print(
            "method2_gorgon_entry_breakpoint="
            + (
                "installed"
                if _gorgon_entry_breakpoint is not None
                else "unavailable"
            )
        )
    if _material_breakpoint is None:
        _material_breakpoint = _creator_breakpoint(
            frame.GetThread().GetProcess().GetTarget(),
            GORGON_MATERIAL_READY,
            f"{__name__}._material_ready",
        )
        print(
            "method2_material_breakpoint="
            + (
                "installed"
                if _material_breakpoint is not None
                else "unavailable"
            )
        )
    if _rc4_key_breakpoint is None:
        _rc4_key_breakpoint = _creator_breakpoint(
            frame.GetThread().GetProcess().GetTarget(),
            GORGON_RC4_KEY_READY,
            f"{__name__}._rc4_key_ready",
        )
    if (
        os.environ.get("CAPCUT_TRACE_LADON_DISPATCH", "0") == "1"
        and _ladon_dispatch_breakpoint is None
    ):
        _ladon_dispatch_breakpoint = _creator_breakpoint(
            frame.GetThread().GetProcess().GetTarget(),
            LADON_BLOCK_DISPATCH,
            f"{__name__}._ladon_block_dispatch",
        )
        print(
            "method2_ladon_dispatch_breakpoint="
            + (
                "installed"
                if _ladon_dispatch_breakpoint is not None
                else "unavailable"
            )
        )
    if (
        os.environ.get("CAPCUT_TRACE_LADON_KEY", "0") == "1"
        and _ladon_key_breakpoint is None
    ):
        _ladon_key_breakpoint = _creator_breakpoint(
            frame.GetThread().GetProcess().GetTarget(),
            LADON_KEY_READY,
            f"{__name__}._ladon_key_ready",
        )
        print(
            "method2_ladon_key_breakpoint="
            + (
                "installed"
                if _ladon_key_breakpoint is not None
                else "unavailable"
            )
        )
    if (
        os.environ.get("CAPCUT_TRACE_LADON_DIGEST", "0") == "1"
        and _ladon_digest_breakpoint is None
    ):
        _ladon_digest_breakpoint = _creator_breakpoint(
            frame.GetThread().GetProcess().GetTarget(),
            LADON_DIGEST_DISPATCH,
            f"{__name__}._ladon_digest_dispatch",
        )
        print(
            "method2_ladon_digest_breakpoint="
            + (
                "installed"
                if _ladon_digest_breakpoint is not None
                else "unavailable"
            )
        )
    if (
        os.environ.get("CAPCUT_TRACE_ARGUS_DISPATCH", "0") == "1"
        and _argus_dispatch_breakpoint is None
    ):
        _argus_dispatch_breakpoint = _creator_breakpoint(
            frame.GetThread().GetProcess().GetTarget(),
            ARGUS_BLOCK_DISPATCH,
            f"{__name__}._argus_block_dispatch",
        )
        print(
            "method2_argus_dispatch_breakpoint="
            + (
                "installed"
                if _argus_dispatch_breakpoint is not None
                else "unavailable"
            )
        )
        if _argus_return_breakpoint is None:
            _argus_return_breakpoint = _creator_breakpoint(
                frame.GetThread().GetProcess().GetTarget(),
                ARGUS_BLOCK_RETURN,
                f"{__name__}._argus_block_returned",
            )
        print(
            "method2_argus_return_breakpoint="
            + (
                "installed"
                if _argus_return_breakpoint is not None
                else "unavailable"
            )
        )
        print(
            "method2_rc4_key_breakpoint="
            + (
                "installed"
                if _rc4_key_breakpoint is not None
                else "unavailable"
            )
        )
    if os.environ.get("CAPCUT_TRACE_AES", "0") == "1":
        if _aes_key_breakpoint is None:
            _aes_key_breakpoint = _creator_breakpoint(
                frame.GetThread().GetProcess().GetTarget(),
                AES_KEY_SCHEDULE,
                f"{__name__}._aes_key_schedule",
            )
            print(
                "method2_aes_key_breakpoint="
                + (
                    "installed"
                    if _aes_key_breakpoint is not None
                    else "unavailable"
                )
            )
        if _aes_block_breakpoint is None:
            _aes_block_breakpoint = _creator_breakpoint(
                frame.GetThread().GetProcess().GetTarget(),
                AES_ENCRYPT_BLOCK,
                f"{__name__}._aes_block_entered",
            )
            print(
                "method2_aes_block_breakpoint="
                + (
                    "installed"
                    if _aes_block_breakpoint is not None
                    else "unavailable"
                )
            )
        if _aes_cbc_breakpoint is None:
            _aes_cbc_breakpoint = _creator_breakpoint(
                frame.GetThread().GetProcess().GetTarget(),
                AES_CBC_ENCRYPT,
                f"{__name__}._aes_cbc_entered",
            )
            print(
                "method2_aes_cbc_breakpoint="
                + (
                    "installed"
                    if _aes_cbc_breakpoint is not None
                    else "unavailable"
                )
            )
    if (
        os.environ.get("CAPCUT_TRACE_ARGUS_ARRAYS", "0") == "1"
        and _byte_array_breakpoint is None
    ):
        _byte_array_breakpoint = _creator_breakpoint(
            frame.GetThread().GetProcess().GetTarget(),
            BYTE_ARRAY_FROM_DATA,
            f"{__name__}._byte_array_from_data",
        )
        print(
            "method2_argus_array_breakpoint="
            + (
                "installed"
                if _byte_array_breakpoint is not None
                else "unavailable"
            )
        )
        if _argus_inner_encrypt_breakpoint is None:
            _argus_inner_encrypt_breakpoint = _creator_breakpoint(
                frame.GetThread().GetProcess().GetTarget(),
                ARGUS_INNER_ENCRYPT,
                f"{__name__}._argus_inner_encrypt",
            )
        print(
            "method2_argus_inner_encrypt_breakpoint="
            + (
                "installed"
                if _argus_inner_encrypt_breakpoint is not None
                else "unavailable"
            )
        )
        if _argus_aes_dispatch_breakpoint is None:
            _argus_aes_dispatch_breakpoint = _creator_breakpoint(
                frame.GetThread().GetProcess().GetTarget(),
                ARGUS_AES_DISPATCH,
                f"{__name__}._argus_aes_dispatch",
            )
        print(
            "method2_argus_aes_dispatch_breakpoint="
            + (
                "installed"
                if _argus_aes_dispatch_breakpoint is not None
                else "unavailable"
            )
        )
    print("method2_trace=armed")
    return False


def _creator_stack(frame: lldb.SBFrame, limit: int = 20) -> str:
    frames = []
    thread = frame.GetThread()
    for index in range(1, min(thread.GetNumFrames(), limit)):
        candidate = thread.GetFrameAtIndex(index)
        if "libVECreator" in _module_name(candidate):
            frames.append(f"0x{_file_offset(candidate):x}")
    return ",".join(frames)


def _byte_array_from_data(
    frame: lldb.SBFrame, _location, _internal_dict
) -> bool:
    if not _armed:
        return False
    length = _register_unsigned(frame, "x2")
    if length > 4096:
        return False
    stack = _creator_stack(frame)
    if "0xbfd5010" not in stack:
        return False
    process = frame.GetThread().GetProcess()
    source_address = _register_unsigned(frame, "x1")
    source = _read_bytes(process, source_address, length)
    print(
        "method2_argus_array"
        f" output=0x{_register_unsigned(frame, 'x0'):x}"
        f" source=0x{source_address:x}"
        f" length={length}"
        f" bytes={source.hex() if source is not None else 'unavailable'}"
        f" stack={stack}"
    )
    return False


def _argus_inner_encrypt(
    frame: lldb.SBFrame, _location, _internal_dict
) -> bool:
    if not _armed:
        return False
    stack = _creator_stack(frame)
    if "0xbfdb530" not in stack:
        return False
    process = frame.GetThread().GetProcess()
    address = _register_unsigned(frame, "x1")
    parsed = _read_argus_byte_array(process, address)
    if parsed is None:
        print(
            "method2_argus_inner_plaintext"
            f" object=0x{address:x} bytes=unavailable stack={stack}"
        )
        return False
    allocation, pointer, payload = parsed
    print(
        "method2_argus_inner_plaintext"
        f" object=0x{address:x}"
        f" allocation={allocation}"
        f" length={len(payload)}"
        f" data=0x{pointer:x}"
        f" bytes={payload.hex()}"
        f" stack={stack}"
    )
    return False


def _read_argus_byte_array(
    process: lldb.SBProcess, address: int
) -> tuple[int, int, bytes] | None:
    """Read the byte-array layout consumed by the Argus AES wrapper.

    The wrapper at 0xC01BDB8 reads the logical length at +12 and the data
    pointer at +16.  The preceding 32-bit value is the allocation size.
    """

    header = _read_bytes(process, address, 24)
    if header is None:
        return None
    allocation = struct.unpack_from("<I", header, 8)[0]
    length = struct.unpack_from("<I", header, 12)[0]
    pointer = struct.unpack_from("<Q", header, 16)[0]
    if length > 4096 or pointer < 0x10000:
        return None
    payload = _read_bytes(process, pointer, length)
    if payload is None:
        return None
    return allocation, pointer, payload


def _argus_aes_dispatch(
    frame: lldb.SBFrame, _location, _internal_dict
) -> bool:
    if not _armed:
        return False
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    function_pointer = _register_unsigned(frame, "x10")
    resolved = target.ResolveLoadAddress(function_pointer)
    function_offset = (
        resolved.GetFileAddress()
        if resolved.IsValid()
        else lldb.LLDB_INVALID_ADDRESS
    )
    fields = []
    for register in ("x8", "x9", "x1", "x2", "x3"):
        address = _register_unsigned(frame, register)
        parsed = _read_argus_byte_array(process, address)
        if parsed is None:
            header = _read_bytes(process, address, 24)
            fields.append(
                f"{register}=0x{address:x}:"
                + (header.hex() if header is not None else "unavailable")
            )
            continue
        allocation, pointer, payload = parsed
        fields.append(
            f"{register}=0x{address:x}"
            f":allocation={allocation}"
            f":length={len(payload)}"
            f":data=0x{pointer:x}"
            f":bytes={payload.hex()}"
        )
    print(
        "method2_argus_aes_dispatch"
        f" function=0x{function_offset:x}"
        f" w4={_register_unsigned(frame, 'w4')} "
        + " ".join(fields)
        + f" stack={_creator_stack(frame)}"
    )
    return False


def _aes_key_schedule(
    frame: lldb.SBFrame, _location, _internal_dict
) -> bool:
    global _aes_hit_count
    if not _armed or _aes_hit_count >= MAX_HITS:
        return False
    key_size = _register_unsigned(frame, "w2")
    if key_size not in (16, 24, 32):
        return False
    process = frame.GetThread().GetProcess()
    key_address = _register_unsigned(frame, "x1")
    key = _read_bytes(process, key_address, key_size)
    if key is None:
        return False
    preview_start = max(1, key_address - 64)
    preview = _read_bytes(process, preview_start, 160)
    _aes_hit_count += 1
    print(
        "method2_aes_key"
        f" hit={_aes_hit_count}"
        f" bits={key_size * 8}"
        f" context=0x{_register_unsigned(frame, 'x0'):x}"
        f" address=0x{key_address:x}"
        f" key={key.hex()}"
        f" preview_start=0x{preview_start:x}"
        f" preview={preview.hex() if preview is not None else 'unavailable'}"
        f" stack={_creator_stack(frame)}"
    )
    return False


def _aes_block_entered(
    frame: lldb.SBFrame, _location, _internal_dict
) -> bool:
    global _aes_hit_count
    if not _armed or _aes_hit_count >= MAX_HITS:
        return False
    process = frame.GetThread().GetProcess()
    input_address = _register_unsigned(frame, "x1")
    output_address = _register_unsigned(frame, "x2")
    block = _read_bytes(process, input_address, 16)
    if block is None or output_address == 0:
        return False
    _aes_hit_count += 1
    return_address = _register_unsigned(frame, "x30")
    target = process.GetTarget()
    return_breakpoint = target.BreakpointCreateByAddress(return_address)
    return_breakpoint.SetScriptCallbackFunction(
        f"{__name__}._aes_block_returned"
    )
    return_breakpoint.SetAutoContinue(True)
    return_breakpoint.SetOneShot(True)
    _aes_return_contexts[return_breakpoint.GetID()] = (
        _aes_hit_count,
        output_address,
        block,
        _creator_stack(frame),
    )
    print(
        "method2_aes_block_in"
        f" hit={_aes_hit_count}"
        f" context=0x{_register_unsigned(frame, 'x0'):x}"
        f" input=0x{input_address:x}:{block.hex()}"
        f" output=0x{output_address:x}"
        f" return=0x{return_address:x}"
        f" stack={_creator_stack(frame)}"
    )
    return False


def _aes_cbc_entered(
    frame: lldb.SBFrame, _location, _internal_dict
) -> bool:
    if not _armed:
        return False
    length = _register_unsigned(frame, "w3")
    if length == 0 or length > 4096 or length % 16:
        return False
    process = frame.GetThread().GetProcess()
    context_address = _register_unsigned(frame, "x0")
    input_address = _register_unsigned(frame, "x1")
    plaintext = _read_bytes(process, input_address, length)
    iv = _read_bytes(process, context_address + 0x1E4, 16)
    if plaintext is None:
        return False
    print(
        "method2_aes_cbc"
        f" length={length}"
        f" context=0x{context_address:x}"
        f" input=0x{input_address:x}:{plaintext.hex()}"
        f" output=0x{_register_unsigned(frame, 'x2'):x}"
        f" iv={iv.hex() if iv is not None else 'unavailable'}"
        f" stack={_creator_stack(frame)}"
    )
    return False


def _aes_block_returned(
    frame: lldb.SBFrame, location, _internal_dict
) -> bool:
    breakpoint = location.GetBreakpoint()
    context = _aes_return_contexts.pop(breakpoint.GetID(), None)
    if context is None:
        return False
    hit, output_address, input_block, creator_stack = context
    output = _read_bytes(
        frame.GetThread().GetProcess(), output_address, 16
    )
    print(
        "method2_aes_block_out"
        f" hit={hit}"
        f" input={input_block.hex()}"
        f" output={output.hex() if output is not None else 'unavailable'}"
        f" stack={creator_stack}"
    )
    return False


def _ladon_block_dispatch(
    frame: lldb.SBFrame, _location, _internal_dict
) -> bool:
    if not _armed:
        return False
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    function_pointer = _register_unsigned(frame, "x8")
    resolved = target.ResolveLoadAddress(function_pointer)
    function_offset = (
        resolved.GetFileAddress()
        if resolved.IsValid()
        else lldb.LLDB_INVALID_ADDRESS
    )
    fields = []
    for register in ("x0", "x1", "x19"):
        address = _register_unsigned(frame, register)
        data = _read_bytes(process, address, 128)
        fields.append(
            f"{register}=0x{address:x}:"
            + (data.hex() if data is not None else "unavailable")
        )
    print(
        "method2_ladon_block_dispatch"
        f" function=0x{function_offset:x} "
        + " ".join(fields)
    )
    return False


def _argus_block_dispatch(
    frame: lldb.SBFrame, _location, _internal_dict
) -> bool:
    if not _armed:
        return False
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    function_pointer = _register_unsigned(frame, "x10")
    resolved = target.ResolveLoadAddress(function_pointer)
    function_offset = (
        resolved.GetFileAddress()
        if resolved.IsValid()
        else lldb.LLDB_INVALID_ADDRESS
    )
    fields = []
    for register in ("x9", "x1"):
        address = _register_unsigned(frame, register)
        data = _read_bytes(process, address, 256)
        fields.append(
            f"{register}=0x{address:x}:"
            + (data.hex() if data is not None else "unavailable")
        )
    print(
        "method2_argus_block_dispatch"
        f" function=0x{function_offset:x} "
        + " ".join(fields)
        + f" stack={_creator_stack(frame)}"
    )
    if function_offset == ARGUS_INNER_BUILDER:
        thread_id = frame.GetThread().GetThreadID()
        _argus_return_contexts[thread_id] = (
            _register_unsigned(frame, "x8"),
            _register_unsigned(frame, "x9"),
            _register_unsigned(frame, "x1"),
        )
    return False


def _argus_block_returned(
    frame: lldb.SBFrame, _location, _internal_dict
) -> bool:
    if not _armed:
        return False
    thread_id = frame.GetThread().GetThreadID()
    context = _argus_return_contexts.pop(thread_id, None)
    if context is None:
        return False
    output_address, context_address, input_address = context
    process = frame.GetThread().GetProcess()
    output = _read_bytes(process, output_address, 0x500)
    payload_address = 0
    payload_length = 0
    payload = None
    if output is not None and len(output) >= 24:
        payload_length = struct.unpack_from("<I", output, 8)[0]
        payload_address = struct.unpack_from("<Q", output, 16)[0]
        if payload_length <= 4096:
            payload = _read_bytes(
                process, payload_address, payload_length
            )
    print(
        "method2_argus_inner_return"
        f" output=0x{output_address:x}:"
        + (output.hex() if output is not None else "unavailable")
        + f" context=0x{context_address:x}"
        + f" input=0x{input_address:x}"
        + f" x0=0x{_register_unsigned(frame, 'x0'):x}"
        + f" stack={_creator_stack(frame)}"
    )
    print(
        "method2_argus_inner_payload"
        f" address=0x{payload_address:x}"
        f" length={payload_length}"
        f" bytes={payload.hex() if payload is not None else 'unavailable'}"
    )
    return False


def _ladon_digest_dispatch(
    frame: lldb.SBFrame, _location, _internal_dict
) -> bool:
    if not _armed:
        return False
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    function_pointer = _register_unsigned(frame, "x10")
    resolved = target.ResolveLoadAddress(function_pointer)
    function_offset = (
        resolved.GetFileAddress()
        if resolved.IsValid()
        else lldb.LLDB_INVALID_ADDRESS
    )
    context_address = _register_unsigned(frame, "x9")
    context = _read_bytes(process, context_address, 256)
    digest_input = None
    input_address = 0
    input_length = 0
    if context is not None and len(context) >= 24:
        input_length = struct.unpack_from("<I", context, 12)[0]
        input_address = struct.unpack_from("<Q", context, 16)[0]
        if input_length <= 4096:
            digest_input = _read_bytes(
                process, input_address, input_length
            )
    print(
        "method2_ladon_digest_dispatch"
        f" function=0x{function_offset:x}"
        f" selector={_register_unsigned(frame, 'w1')}"
        f" context=0x{context_address:x}:"
        + (context.hex() if context is not None else "unavailable")
        + f" input=0x{input_address:x}:{input_length}:"
        + (
            digest_input.hex()
            if digest_input is not None
            else "unavailable"
        )
        + f" stack={_creator_stack(frame)}"
    )
    return False


def _ladon_key_ready(frame: lldb.SBFrame, _location, _internal_dict) -> bool:
    if not _armed:
        return False
    process = frame.GetThread().GetProcess()
    needles = [
        value
        for value in (
            str(_current_timestamp).encode() if _current_timestamp else b"",
            b"1369207606",
            b"359289",
        )
        if value
    ]
    combined_needle = (
        f"{_current_timestamp}-1369207606-359289".encode()
        if _current_timestamp
        else b""
    )
    stack_pointer = frame.GetSP()
    start = max(1, stack_pointer - 0x20000)
    data = _read_bytes(process, start, 0x40000)
    hits = []
    if data is not None:
        for needle in needles:
            offset = data.find(needle)
            while offset >= 0:
                window_start = max(0, offset - 32)
                window_stop = min(len(data), offset + 96)
                hits.append(
                    f"needle={needle.decode()} address=0x{start + offset:x}"
                    f" preview_offset={offset - window_start}"
                    f" bytes={data[window_start:window_stop].hex()}"
                )
                offset = data.find(needle, offset + 1)
    for register_index in range(29):
        pointer = _register_unsigned(frame, f"x{register_index}")
        if pointer < 0x100000000:
            continue
        page = pointer & ~0xFFF
        register_data = _read_bytes(process, page, 0x4000)
        if register_data is None:
            continue
        for needle in needles:
            offset = register_data.find(needle)
            while offset >= 0:
                window_start = max(0, offset - 32)
                window_stop = min(len(register_data), offset + 96)
                hits.append(
                    f"needle={needle.decode()} register=x{register_index}"
                    f" address=0x{page + offset:x}"
                    f" preview_offset={offset - window_start}"
                    f" bytes={register_data[window_start:window_stop].hex()}"
                )
                offset = register_data.find(needle, offset + 1)
    if combined_needle:
        regions = process.GetMemoryRegions()
        total_scanned = 0
        for region_index in range(regions.GetSize()):
            region = lldb.SBMemoryRegionInfo()
            if not regions.GetMemoryRegionAtIndex(region_index, region):
                continue
            region_size = region.GetRegionEnd() - region.GetRegionBase()
            if (
                not region.IsReadable()
                or region.IsExecutable()
                or region_size <= 0
                or region_size > 64 * 1024 * 1024
                or total_scanned + region_size > 512 * 1024 * 1024
            ):
                continue
            total_scanned += region_size
            region_data = _read_bytes(
                process, region.GetRegionBase(), region_size
            )
            if region_data is None:
                continue
            offset = region_data.find(combined_needle)
            if offset >= 0:
                window_start = max(0, offset - 32)
                window_stop = min(len(region_data), offset + 96)
                hits.append(
                    f"needle={combined_needle.decode()} region={region_index}"
                    f" address=0x{region.GetRegionBase() + offset:x}"
                    f" preview_offset={offset - window_start}"
                    f" bytes={region_data[window_start:window_stop].hex()}"
                )
    print(
        "method2_ladon_key_ready"
        f" sp=0x{stack_pointer:x}"
        f" hits={len(hits)}"
    )
    for hit in hits[:24]:
        print("method2_ladon_stack_hit " + hit)
    return False


def _strlen_called(frame: lldb.SBFrame, _location, _internal_dict) -> bool:
    if os.environ.get("CAPCUT_TRACE_ONLY_ARGUS", "0") == "1":
        return False
    global _memory_scan_done
    if not _armed:
        return False
    value = _read_c_string(
        frame.GetThread().GetProcess(), _register_unsigned(frame, "x0"), 384
    )
    decoded_signature = None
    if (
        value is not None
        and 48 <= len(value) <= 720
        and re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", value)
    ):
        try:
            decoded_signature = base64.b64decode(value, validate=True)
        except ValueError:
            decoded_signature = None
    if decoded_signature is not None and (
        len(value) == 48 or len(decoded_signature) >= 128
    ):
        label = "ladon" if len(value) == 48 else "argus"
        creator_frames = []
        thread = frame.GetThread()
        for index in range(1, min(thread.GetNumFrames(), 20)):
            candidate = thread.GetFrameAtIndex(index)
            if "libVECreator" in _module_name(candidate):
                creator_frames.append(f"0x{_file_offset(candidate):x}")
        print(
            f"method2_{label}_base64 length={len(value)}"
            f" decoded_length={len(decoded_signature)}"
            f" prefix={decoded_signature[:4].hex()}"
            + (
                " stack=" + ",".join(creator_frames)
                if creator_frames
                else ""
            )
        )
    if (
        value is None
        or len(value) < 52
        or not value.startswith("8404")
        or any(character not in "0123456789abcdefABCDEF" for character in value[:52])
    ):
        return False
    thread = frame.GetThread()
    print(f"method2_gorgon_hex={value[:52].lower()}")
    creator_frames = []
    for index in range(1, min(thread.GetNumFrames(), 16)):
        candidate = thread.GetFrameAtIndex(index)
        if "libVECreator" in _module_name(candidate):
            creator_frames.append(f"0x{_file_offset(candidate):x}")
    if creator_frames:
        print("method2_gorgon_strlen_stack=" + ",".join(creator_frames))
    for watchpoint in _material_watchpoints + _mixer_watchpoints:
        watchpoint.SetEnabled(False)
    if not _memory_scan_done and _expected_material_prefix:
        _memory_scan_done = True
        _scan_reachable_memory(frame)
    return False


def _format_entered(frame: lldb.SBFrame, _location, _internal_dict) -> bool:
    if os.environ.get("CAPCUT_TRACE_ONLY_ARGUS", "0") == "1":
        return False
    if not _armed:
        return False
    process = frame.GetThread().GetProcess()
    format_string = _read_c_string(process, _register_unsigned(frame, "x1"), 160)
    caller = frame.GetThread().GetFrameAtIndex(1)
    registers = ",".join(
        f"x{index}=0x{_register_unsigned(frame, f'x{index}'):x}"
        for index in range(2, 8)
    )
    print(
        "method2_format"
        f" caller=0x{_file_offset(caller):x}"
        f" format={format_string!r}"
        f" {registers}"
    )
    return False


def _material_ready(frame: lldb.SBFrame, _location, _internal_dict) -> bool:
    if not _armed:
        return False
    process = frame.GetThread().GetProcess()
    material = (
        _read_bytes(process, _material_address, 20)
        if _material_address
        else None
    )
    if material is None:
        material = _read_libcpp_string(process, frame.GetFP() - 0xD8)
    if material is None:
        print("method2_gorgon_material=unavailable")
        return False
    print(
        "method2_gorgon_material"
        f" length={len(material)}"
        f" bytes={material.hex()}"
    )
    if len(material) == 20:
        print(
            "method2_gorgon_material_fields"
            f" query={material[0:4].hex()}"
            f" stub={material[4:8].hex()}"
            f" cookie={material[8:12].hex()}"
            f" version={material[12:16].hex()}"
            f" timestamp={int.from_bytes(material[16:20], 'big')}"
        )
        if os.environ.get("CAPCUT_TRACE_GORGON_WATCHES", "1") != "0":
            _install_material_watchpoints(frame)
    return False


def _rc4_key_ready(frame: lldb.SBFrame, _location, _internal_dict) -> bool:
    if not _armed:
        return False
    process = frame.GetThread().GetProcess()
    key_address = _register_unsigned(frame, "x20")
    state_address = _register_unsigned(frame, "x28")
    key = _read_bytes(process, key_address, 8)
    state = _read_bytes(process, state_address, 16)
    print(
        "method2_gorgon_rc4"
        f" key={key.hex() if key is not None else 'unavailable'}"
        f" state_prefix={state.hex() if state is not None else 'unavailable'}"
    )
    return False


def _material_access(
    frame: lldb.SBFrame, _watchpoint, _internal_dict=None
) -> bool:
    global _watch_hit_count, _mixer_address
    if not _armed or _watch_hit_count >= MAX_WATCH_HITS:
        return False
    _watch_hit_count += 1
    pc = _file_offset(frame)
    module = _module_name(frame)
    process = frame.GetThread().GetProcess()
    material = _read_bytes(process, _material_address, 20)
    key = (module, pc)
    if key not in _watch_seen:
        _watch_seen.add(key)
        registers = ",".join(
            f"x{index}=0x{_register_unsigned(frame, f'x{index}'):x}"
            for index in (0, 1, 2, 3, 8, 9)
        )
        print(
            "method2_material_access"
            f" hit={_watch_hit_count}"
            f" module={module}"
            f" pc=0x{pc:x}"
            f" instruction=0x{pc - 4:x}"
            f" bytes={material.hex() if material is not None else 'unavailable'}"
            f" {registers}"
        )
    if (
        not _mixer_address
        and "libVECreator" in module
        and _register_unsigned(frame, "x2") == 20
    ):
        candidate = _register_unsigned(frame, "x0")
        if candidate and candidate != _material_address:
            _mixer_address = candidate
            print(f"method2_mixer_address=0x{_mixer_address:x}")
            _install_mixer_watchpoints(frame, _mixer_address)
    if _watch_hit_count >= MAX_WATCH_HITS:
        for watchpoint in _material_watchpoints:
            watchpoint.SetEnabled(False)
        print("method2_material_watchpoint=hit_limit")
    return False


def _mixer_access(
    frame: lldb.SBFrame, _watchpoint, _internal_dict=None
) -> bool:
    global _mixer_hit_count
    if not _armed or _mixer_hit_count >= MAX_WATCH_HITS:
        return False
    _mixer_hit_count += 1
    pc = _file_offset(frame)
    module = _module_name(frame)
    process = frame.GetThread().GetProcess()
    value = _read_bytes(process, _mixer_address, 20)
    key = (module, pc, value)
    if key not in _mixer_seen:
        _mixer_seen.add(key)
        registers = ",".join(
            f"x{index}=0x{_register_unsigned(frame, f'x{index}'):x}"
            for index in (0, 1, 2, 3, 8, 9, 10, 11, 12)
        )
        print(
            "method2_mixer_access"
            f" hit={_mixer_hit_count}"
            f" module={module}"
            f" pc=0x{pc:x}"
            f" instruction=0x{pc - 4:x}"
            f" bytes={value.hex() if value is not None else 'unavailable'}"
            f" {registers}"
        )
    if _mixer_hit_count >= MAX_WATCH_HITS:
        for watchpoint in _mixer_watchpoints:
            watchpoint.SetEnabled(False)
        print("method2_mixer_watchpoint=hit_limit")
    return False


def _scan_window(
    process: lldb.SBProcess,
    start: int,
    size: int,
    label: str,
    seen: set[int],
) -> None:
    if start <= 0 or size <= 0 or size > 2 * 1024 * 1024:
        return
    error = lldb.SBError()
    try:
        data = process.ReadMemory(start, size, error)
    except (SystemError, OverflowError):
        return
    if not error.Success():
        return
    offset = bytes(data).find(_expected_material_prefix)
    while offset >= 0:
        address = start + offset
        if address not in seen:
            seen.add(address)
            preview_start = max(0, offset - 16)
            preview_stop = min(len(data), offset + 64)
            print(
                "method2_material_memory"
                f" label={label}"
                f" address=0x{address:x}"
                f" preview_offset={offset - preview_start}"
                f" bytes={bytes(data[preview_start:preview_stop]).hex()}"
            )
        offset = bytes(data).find(_expected_material_prefix, offset + 1)


def _scan_reachable_memory(frame: lldb.SBFrame) -> None:
    process = frame.GetThread().GetProcess()
    thread = frame.GetThread()
    seen: set[int] = set()
    stack_pointers = [
        thread.GetFrameAtIndex(index).GetSP()
        for index in range(thread.GetNumFrames())
        if thread.GetFrameAtIndex(index).GetSP() > 0
    ]
    if stack_pointers:
        low = max(1, min(stack_pointers) - 1024 * 1024)
        high = max(stack_pointers) + 1024 * 1024
        _scan_window(process, low, min(high - low, 2 * 1024 * 1024), "stack", seen)

    for frame_index in range(min(thread.GetNumFrames(), 16)):
        candidate = thread.GetFrameAtIndex(frame_index)
        for register_index in range(29):
            pointer = _register_unsigned(candidate, f"x{register_index}")
            if pointer < 0x100000000:
                continue
            start = pointer & ~0xFFF
            _scan_window(
                process,
                start,
                0x4000,
                f"frame{frame_index}_x{register_index}",
                seen,
            )
    if not seen:
        print("method2_material_memory=not_found_in_reachable_windows")


def _gorgon_entry(frame: lldb.SBFrame, _location, _internal_dict) -> bool:
    if os.environ.get("CAPCUT_TRACE_ONLY_ARGUS", "0") == "1":
        return False
    global _current_timestamp
    if not _armed:
        return False
    process = frame.GetThread().GetProcess()
    values = []
    for index in range(8):
        address = _register_unsigned(frame, f"x{index}")
        candidate = _read_c_string(process, address, 192)
        if candidate and (
            "dummy" in candidate
            or "x-ss-stub" in candidate.lower()
            or candidate.startswith("8404")
        ):
            values.append(f"x{index}_string={candidate!r}")
        else:
            values.append(f"x{index}=0x{address:x}")
    print("method2_gorgon_entry " + " ".join(values))
    for index in (0, 1, 2, 4):
        address = _register_unsigned(frame, f"x{index}")
        data = _read_bytes(process, address, 128)
        if data is not None:
            print(
                f"method2_gorgon_entry_memory x{index}=0x{address:x}"
                f" bytes={data.hex()}"
            )
    context_address = _register_unsigned(frame, "x0")
    context = _read_bytes(process, context_address, 128)
    if context is not None:
        _current_timestamp = struct.unpack_from("<I", context)[0]
        print(
            "method2_gorgon_context"
            f" timestamp={_current_timestamp}"
        )
        dumped: set[int] = set()
        for offset in range(0, len(context), 8):
            pointer = struct.unpack_from("<Q", context, offset)[0]
            if pointer < 0x100000000 or pointer in dumped:
                continue
            child = _read_bytes(process, pointer, 128)
            if child is None:
                continue
            dumped.add(pointer)
            child_string = _read_c_string(process, pointer, 128)
            print(
                "method2_gorgon_context_pointer"
                f" offset=0x{offset:x}"
                f" address=0x{pointer:x}"
                f" string={child_string!r}"
                f" bytes={child.hex()}"
            )
        _scan_pointer_graph(
            process,
            [
                context_address,
                *[
                    struct.unpack_from("<Q", context, offset)[0]
                    for offset in range(0, len(context), 8)
                ],
            ],
        )
    return False


def _scan_pointer_graph(process: lldb.SBProcess, roots: list[int]) -> None:
    needles = {
        "material8": _expected_material_prefix,
        "query16": _query_digest,
        "stub16": _stub_digest,
        "query4": _query_digest[:4],
        "stub4": _stub_digest[:4],
    }
    needles = {name: value for name, value in needles.items() if value}
    queue = [(value, 0) for value in roots]
    visited: set[int] = set()
    hits: set[tuple[str, int]] = set()
    while queue and len(visited) < 512:
        address, depth = queue.pop(0)
        if (
            address in visited
            or address < 0x100000000
            or address > 0x0000FFFFFFFFFFFF
        ):
            continue
        visited.add(address)
        page = address & ~0xFFF
        data = _read_bytes(process, page, 0x1000)
        if data is None:
            continue
        for name, needle in needles.items():
            offset = data.find(needle)
            while offset >= 0:
                hit_address = page + offset
                key = (name, hit_address)
                if key not in hits:
                    hits.add(key)
                    start = max(0, offset - 16)
                    stop = min(len(data), offset + max(64, len(needle)))
                    print(
                        "method2_pointer_graph_hit"
                        f" needle={name}"
                        f" depth={depth}"
                        f" address=0x{hit_address:x}"
                        f" preview_offset={offset - start}"
                        f" bytes={data[start:stop].hex()}"
                    )
                offset = data.find(needle, offset + 1)
        if depth >= 4:
            continue
        for offset in range(0, len(data) - 7, 8):
            pointer = struct.unpack_from("<Q", data, offset)[0]
            if (
                0x100000000 <= pointer <= 0x0000FFFFFFFFFFFF
                and pointer not in visited
            ):
                queue.append((pointer, depth + 1))
    print(
        "method2_pointer_graph"
        f" nodes={len(visited)} hits={len(hits)}"
    )


def _memcpy_called(frame: lldb.SBFrame, _location, _internal_dict) -> bool:
    global _hit_count, _last_copy, _material_address
    if os.environ.get("CAPCUT_TRACE_ONLY_ARGUS", "0") == "1":
        return False
    if not _armed or _hit_count >= MAX_HITS:
        return False
    length = _register_unsigned(frame, "x2")
    trace_signature_copies = (
        os.environ.get("CAPCUT_TRACE_SIGNATURE_COPIES", "0") == "1"
    )
    trace_argus_copies = (
        os.environ.get("CAPCUT_TRACE_ARGUS_COPIES", "0") == "1"
    )
    interesting_lengths = (
        (2, 4, 8, 12, 16, 20, 32, 36, 224, 226, 240, 242, 256)
        if trace_argus_copies
        else (
            (4, 8, 12, 16, 20, 32, 36)
            if trace_signature_copies
            else (4, 8, 12, 20)
        )
    )
    if length not in interesting_lengths:
        return False

    thread = frame.GetThread()
    if thread.GetNumFrames() < 2:
        return False
    creator_frames = []
    creator_offsets = []
    in_gorgon = False
    in_signature_pipeline = False
    for index in range(1, min(thread.GetNumFrames(), 12)):
        candidate = thread.GetFrameAtIndex(index)
        if "libVECreator" not in _module_name(candidate):
            continue
        offset = _file_offset(candidate)
        creator_offsets.append(offset)
        creator_frames.append(f"0x{offset:x}")
        in_gorgon = in_gorgon or GORGON_ENTRY <= offset < GORGON_STOP
        in_signature_pipeline = (
            in_signature_pipeline or 0xBFD5910 <= offset < 0xBFE54C8
        )
    if not in_gorgon and not (
        (trace_signature_copies or trace_argus_copies)
        and in_signature_pipeline
        and length in (2, 16, 32, 36, 224, 226, 240, 242, 256)
    ):
        return False
    caller = thread.GetFrameAtIndex(1)

    source_address = _register_unsigned(frame, "x1")
    destination_address = _register_unsigned(frame, "x0")
    source = _read_bytes(frame.GetThread().GetProcess(), source_address, length)
    if source is None:
        return False
    if (
        length == 12
        and GORGON_MATERIAL_PREFIX_COPY in creator_offsets
    ):
        _material_address = destination_address
    copy_key = (
        _file_offset(caller),
        source_address,
        destination_address,
        length,
        source,
    )
    if copy_key == _last_copy:
        return False
    _last_copy = copy_key

    _hit_count += 1
    offset = _file_offset(caller)
    print(
        "method2_copy"
        f" hit={_hit_count}"
        f" function={frame.GetFunctionName() or 'unknown'}"
        f" length={length}"
        f" caller=0x{offset:x}"
        f" source=0x{source_address:x}"
        f" destination=0x{destination_address:x}"
        f" bytes={source.hex()}"
    )
    if creator_frames:
        print("method2_creator_stack=" + ",".join(creator_frames))
    if _hit_count >= MAX_HITS and _copy_breakpoint is not None:
        _copy_breakpoint.SetEnabled(False)
        if _move_breakpoint is not None:
            _move_breakpoint.SetEnabled(False)
        print("method2_trace=hit_limit")
    return False


def install(debugger: lldb.SBDebugger, _command, result, _internal_dict) -> None:
    global _armed, _hit_count, _copy_breakpoint, _move_breakpoint
    global _strlen_breakpoint, _last_copy, _argus_return_breakpoint
    _armed = False
    _hit_count = 0
    _last_copy = None
    target = debugger.GetSelectedTarget()
    if not target.IsValid():
        result.SetError("create a target before installing the trace")
        return

    signer = target.BreakpointCreateByName(
        "_ZN12_GLOBAL__N_118traced_http_signerEPKcS1_"
    )
    signer.SetScriptCallbackFunction(
        f"{__name__}._signer_entered"
    )
    signer.SetAutoContinue(True)

    _copy_breakpoint = target.BreakpointCreateByName("memcpy")
    _copy_breakpoint.SetScriptCallbackFunction(
        f"{__name__}._memcpy_called"
    )
    _copy_breakpoint.SetAutoContinue(True)
    _copy_breakpoint.SetEnabled(False)

    _move_breakpoint = target.BreakpointCreateByName("memmove")
    _move_breakpoint.SetScriptCallbackFunction(
        f"{__name__}._memcpy_called"
    )
    _move_breakpoint.SetAutoContinue(True)
    _move_breakpoint.SetEnabled(False)

    _strlen_breakpoint = target.BreakpointCreateByName("strlen")
    _strlen_breakpoint.SetScriptCallbackFunction(
        f"{__name__}._strlen_called"
    )
    _strlen_breakpoint.SetAutoContinue(True)
    _strlen_breakpoint.SetEnabled(False)

    print(
        "method2_trace=installed"
        f" signer_locations={signer.GetNumLocations()}"
        f" memcpy_locations={_copy_breakpoint.GetNumLocations()}"
        f" memmove_locations={_move_breakpoint.GetNumLocations()}"
        f" strlen_locations={_strlen_breakpoint.GetNumLocations()}"
    )


def __lldb_init_module(debugger: lldb.SBDebugger, _internal_dict) -> None:
    debugger.HandleCommand(
        f"command script add -f {__name__}.install method2-gorgon-trace"
    )
    print("method2 command available: method2-gorgon-trace")
