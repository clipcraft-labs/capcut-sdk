"""Find ARM64 references near target virtual addresses in CapCut Mach-O files."""

from __future__ import annotations

import mmap
import struct
import sys

from capstone import CS_ARCH_ARM64, CS_MODE_ARM, Cs
from capstone.arm64 import ARM64_OP_IMM, ARM64_OP_MEM, ARM64_OP_REG


TEXT_RANGES = {
    "libVECreator": (0x202B0, 0xC281C68),
    "libsscronet": (0x1180, 0x605144),
}


def sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def adrp_target(instruction: int, pc: int) -> int | None:
    if instruction & 0x9F000000 != 0x90000000:
        return None
    immediate = ((instruction >> 5) & 0x7FFFF) << 2
    immediate |= (instruction >> 29) & 0x3
    return (pc & ~0xFFF) + (sign_extend(immediate, 21) << 12)


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit(f"usage: {sys.argv[0]} MACH_O ADDRESS...")
    source_path = sys.argv[1]
    targets = [int(value, 0) for value in sys.argv[2:]]
    text_start, text_stop = next(
        (
            bounds
            for name, bounds in TEXT_RANGES.items()
            if name in source_path
        ),
        (0, 0),
    )
    if text_stop <= text_start:
        raise SystemExit("unsupported Mach-O")
    disassembler = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    disassembler.detail = True
    with open(source_path, "rb") as source:
        with mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as binary:
            stop = min(text_stop, len(binary))
            for offset in range(text_start, stop - 52, 4):
                instruction = struct.unpack_from("<I", binary, offset)[0]
                page = adrp_target(instruction, offset)
                if page is None or not any(
                    page == target & ~0xFFF for target in targets
                ):
                    continue
                instructions = list(
                    disassembler.disasm(binary[offset : offset + 52], offset)
                )
                if not instructions:
                    continue
                base_register = instructions[0].operands[0].reg
                resolved = []
                for following in instructions[1:]:
                    operands = following.operands
                    if (
                        len(operands) >= 3
                        and operands[1].type == ARM64_OP_REG
                        and operands[1].reg == base_register
                        and operands[2].type == ARM64_OP_IMM
                    ):
                        resolved.append(page + operands[2].imm)
                    for operand in operands:
                        if (
                            operand.type == ARM64_OP_MEM
                            and operand.mem.base == base_register
                        ):
                            resolved.append(page + operand.mem.disp)
                matched = sorted(set(resolved) & set(targets))
                if matched:
                    print(
                        f"xref=0x{offset:x}"
                        f" targets={','.join(hex(value) for value in matched)}"
                    )
                    for decoded in instructions:
                        print(
                            f"  0x{decoded.address:x}"
                            f" {decoded.mnemonic} {decoded.op_str}"
                        )


if __name__ == "__main__":
    main()
