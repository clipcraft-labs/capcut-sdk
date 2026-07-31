/*
 * Frida probe for the native Method-2 oracle.
 *
 * Run only with the repository's fixed dummy identifiers. It prints digest
 * call sites and lengths, and reveals plaintext only when it contains one of
 * those explicit dummy markers.
 */

"use strict";

const contexts = new Map();
let installed = false;

function hex(bytes) {
  return Array.from(new Uint8Array(bytes))
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

function safePreview(bytes) {
  if (bytes === null) return "";
  const text = Array.from(new Uint8Array(bytes))
    .map((value) => (value >= 32 && value < 127 ? String.fromCharCode(value) : "."))
    .join("");
  if (
    text.includes("1000000000000000001") ||
    text.includes("2000000000000000001") ||
    text.includes("aid=359289") ||
    text.includes('{"dummy":1}')
  ) {
    return text;
  }
  return "";
}

function findExport(name) {
  try {
    return Module.findGlobalExportByName(name);
  } catch (_) {
    return Module.findExportByName(null, name);
  }
}

function install() {
  if (installed) return;
  const creator = Process.findModuleByName("libVECreator.dylib");
  if (creator === null) return;
  installed = true;
  console.log("crypto_trace=installed creator_base=" + creator.base);

  const update = findExport("MD5_Update");
  const final = findExport("MD5_Final");
  if (update !== null) {
    Interceptor.attach(update, {
      onEnter(args) {
        const caller = this.returnAddress;
        if (!creator.contains(caller)) return;
        const context = args[0].toString();
        const length = args[2].toInt32();
        const bounded = Math.max(0, Math.min(length, 4096));
        let chunks = contexts.get(context) || [];
        if (bounded > 0) chunks.push(args[1].readByteArray(bounded));
        contexts.set(context, chunks);
        console.log(
          "md5_update caller=" + caller.sub(creator.base) + " length=" + length
        );
      },
    });
  }
  if (final !== null) {
    Interceptor.attach(final, {
      onEnter(args) {
        this.output = args[0];
        this.context = args[1].toString();
        this.caller = this.returnAddress;
        this.relevant = creator.contains(this.caller);
      },
      onLeave() {
        if (!this.relevant) return;
        const chunks = contexts.get(this.context) || [];
        contexts.delete(this.context);
        let total = 0;
        for (const chunk of chunks) total += chunk.byteLength;
        const merged = new Uint8Array(total);
        let offset = 0;
        for (const chunk of chunks) {
          merged.set(new Uint8Array(chunk), offset);
          offset += chunk.byteLength;
        }
        const preview = safePreview(merged.buffer);
        console.log(
          "md5_final caller=" +
            this.caller.sub(creator.base) +
            " input_length=" +
            total +
            " digest=" +
            hex(this.output.readByteArray(16)) +
            (preview ? " dummy_input=" + preview : "")
        );
      },
    });
  }

  for (const name of ["CC_SHA256", "CCCrypt", "AES_cbc_encrypt", "AES_ctr128_encrypt"]) {
    const target = findExport(name);
    if (target === null) continue;
    Interceptor.attach(target, {
      onEnter() {
        const caller = this.returnAddress;
        if (creator.contains(caller)) {
          console.log(name + " caller=" + caller.sub(creator.base));
        }
      },
    });
  }
}

const timer = setInterval(() => {
  install();
  if (installed) clearInterval(timer);
}, 1);
