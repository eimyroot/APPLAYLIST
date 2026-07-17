import { readFileSync, readdirSync } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const root = resolve(scriptDirectory, "..");
const sourceRoot = resolve(root, "src");
const bridgePath = resolve(sourceRoot, "desktopBridge.ts");

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
if (!files.includes(bridgePath)) {
  throw new Error("renderer security check requires src/desktopBridge.ts");
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
  const displayPath = relative(sourceRoot, file);
  const content = readFileSync(file, "utf8");

  for (const [label, pattern] of forbidden) {
    if (pattern.test(content)) {
      violations.push(`${displayPath}: forbidden ${label}`);
    }
  }

  const tauriImports = [
    ...content.matchAll(/from\s+["'](@tauri-apps\/[^"']+)["']/g),
  ].map((match) => match[1]);

  if (file !== bridgePath && tauriImports.length > 0) {
    violations.push(`${displayPath}: Tauri imports are allowed only in desktopBridge.ts`);
  }
  if (
    file === bridgePath &&
    (tauriImports.length !== 1 || tauriImports[0] !== "@tauri-apps/api/core")
  ) {
    violations.push(
      "desktopBridge.ts must have exactly one Tauri import: @tauri-apps/api/core",
    );
  }

  const invokeCalls = [
    ...content.matchAll(/\binvoke(?:<[^>]+>)?\s*\(/g),
  ];
  const literalInvokeCalls = [
    ...content.matchAll(/\binvoke(?:<[^>]+>)?\s*\(\s*["']([^"']+)["']/g),
  ];

  if (file !== bridgePath && invokeCalls.length > 0) {
    violations.push(`${displayPath}: invoke calls are allowed only in desktopBridge.ts`);
  }
  if (file === bridgePath && invokeCalls.length !== literalInvokeCalls.length) {
    violations.push("desktopBridge.ts contains a dynamic or non-literal invoke command");
  }

  for (const match of literalInvokeCalls) {
    const command = match[1];
    observedInvokeCommands.add(command);
    if (!allowedInvokeCommands.has(command)) {
      violations.push(`renderer invokes undeclared command: ${command}`);
    }
  }
}

for (const command of allowedInvokeCommands) {
  if (!observedInvokeCommands.has(command)) {
    violations.push(`expected typed command is not exercised: ${command}`);
  }
}

if (violations.length > 0) {
  throw new Error(violations.join("\n"));
}

console.log(
  JSON.stringify(
    {
      schemaVersion: "applaylist-renderer-security-v2",
      filesChecked: files.length,
      ipcBoundary: "src/desktopBridge.ts",
      allowedCommands: [...allowedInvokeCommands].sort(),
      status: "pass",
    },
    null,
    2,
  ),
);
