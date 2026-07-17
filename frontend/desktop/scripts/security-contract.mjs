import { readFileSync, readdirSync, statSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(new URL("..", import.meta.url).pathname);
const sourceRoot = resolve(root, "src");

function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      return walk(path);
    }
    return entry.isFile() && /\.(?:ts|tsx)$/.test(entry.name) ? [path] : [];
  });
}

const files = walk(sourceRoot);
if (files.length === 0) {
  throw new Error("renderer security check found no TypeScript sources");
}

const forbidden = [
  ["direct network fetch", /\bfetch\s*\(/],
  ["XMLHttpRequest", /\bXMLHttpRequest\b/],
  ["WebSocket", /\bWebSocket\b/],
  ["EventSource", /\bEventSource\b/],
  ["sidecar loopback address", /127\.0\.0\.1|localhost/i],
  ["Tauri shell plugin", /@tauri-apps\/plugin-shell/],
  ["Tauri filesystem plugin", /@tauri-apps\/plugin-fs/],
  ["Tauri HTTP plugin", /@tauri-apps\/plugin-http/],
  ["Tauri dialog plugin in renderer", /@tauri-apps\/plugin-dialog/],
  ["Node child process", /node:child_process|child_process/],
  ["Node filesystem", /node:fs|from\s+["']fs["']/],
];

const allowedInvokeCommands = new Set(["desktop_status", "choose_library_root"]);
const observedInvokeCommands = new Set();
const violations = [];

for (const file of files) {
  const content = readFileSync(file, "utf8");
  for (const [label, pattern] of forbidden) {
    if (pattern.test(content)) {
      violations.push(`${file}: forbidden ${label}`);
    }
  }

  for (const match of content.matchAll(/invoke(?:<[^>]+>)?\(\s*["']([^"']+)["']/g)) {
    observedInvokeCommands.add(match[1]);
  }
}

for (const command of observedInvokeCommands) {
  if (!allowedInvokeCommands.has(command)) {
    violations.push(`renderer invokes undeclared command: ${command}`);
  }
}

for (const command of allowedInvokeCommands) {
  if (!observedInvokeCommands.has(command)) {
    violations.push(`expected typed command is not exercised: ${command}`);
  }
}

const bridge = readFileSync(resolve(sourceRoot, "desktopBridge.ts"), "utf8");
if (!bridge.includes('from "@tauri-apps/api/core"')) {
  violations.push("desktopBridge.ts must use only @tauri-apps/api/core invoke");
}

if (violations.length > 0) {
  throw new Error(violations.join("\n"));
}

console.log(
  JSON.stringify(
    {
      schemaVersion: "applaylist-renderer-security-v1",
      filesChecked: files.length,
      allowedCommands: [...allowedInvokeCommands].sort(),
      status: "pass",
    },
    null,
    2,
  ),
);
