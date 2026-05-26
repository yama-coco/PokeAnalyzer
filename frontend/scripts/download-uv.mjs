#!/usr/bin/env node
/**
 * Downloads the platform-specific uv standalone binary for Electron bundling.
 *
 * Usage:
 *   node scripts/download-uv.mjs            # current platform
 *   UV_PLATFORM=win32 UV_ARCH=x64 node ...  # cross-platform override
 */
import { execSync } from "child_process";
import { existsSync, mkdirSync, rmSync, chmodSync, copyFileSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, "..");

const TARGETS = {
  "win32-x64": "x86_64-pc-windows-msvc",
  "win32-arm64": "aarch64-pc-windows-msvc",
  "darwin-x64": "x86_64-apple-darwin",
  "darwin-arm64": "aarch64-apple-darwin",
  "linux-x64": "x86_64-unknown-linux-musl",
  "linux-arm64": "aarch64-unknown-linux-musl",
};

function resolveTarget() {
  const platform = process.env.UV_PLATFORM || process.platform;
  const arch = process.env.UV_ARCH || process.arch;
  const key = `${platform}-${arch}`;
  const target = TARGETS[key];
  if (!target) {
    throw new Error(`Unsupported platform/arch: ${key}`);
  }
  return { target, isWindows: platform === "win32" };
}

function download() {
  const { target, isWindows } = resolveTarget();
  const ext = isWindows ? "zip" : "tar.gz";
  const url = `https://github.com/astral-sh/uv/releases/latest/download/uv-${target}.${ext}`;

  const outputDir = path.join(rootDir, "build", "uv");
  const tempDir = path.join(rootDir, "build", "temp-uv");

  for (const dir of [outputDir, tempDir]) {
    if (existsSync(dir)) rmSync(dir, { recursive: true });
    mkdirSync(dir, { recursive: true });
  }

  const archivePath = path.join(tempDir, `uv.${ext}`);

  console.log(`Downloading uv for ${target} ...`);
  execSync(`curl -fsSL -o "${archivePath}" "${url}"`, { stdio: "inherit" });

  console.log("Extracting ...");
  if (isWindows) {
    execSync(
      `powershell -Command "Expand-Archive -Path '${archivePath}' -DestinationPath '${tempDir}'"`,
      { stdio: "inherit" },
    );
  } else {
    execSync(`tar -xzf "${archivePath}" -C "${tempDir}"`, {
      stdio: "inherit",
    });
  }

  const binaryName = isWindows ? "uv.exe" : "uv";
  const extractedBin = path.join(tempDir, `uv-${target}`, binaryName);
  const destBin = path.join(outputDir, binaryName);

  copyFileSync(extractedBin, destBin);
  if (!isWindows) chmodSync(destBin, 0o755);

  rmSync(tempDir, { recursive: true });
  console.log(`uv binary ready: ${destBin}`);
}

download();
