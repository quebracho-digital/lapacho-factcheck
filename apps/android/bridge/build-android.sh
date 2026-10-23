#!/usr/bin/env bash
# Builds the bridge for a device (arm64-v8a) and the emulator (x86_64) and
# generates the Kotlin bindings. Called by the :app Gradle build; OUT is where
# it expects jniLibs/ and kotlin/. Needs cargo-ndk and ANDROID_NDK_HOME.
set -euo pipefail
out="$1"
cd "$(dirname "$0")"
target="$(cargo metadata --format-version 1 --no-deps | python3 -c 'import json,sys; print(json.load(sys.stdin)["target_directory"])')"

# API 28: llama.cpp uses posix_madvise and friends missing below it.
cargo ndk -t arm64-v8a -t x86_64 -P 28 -o "$out/jniLibs" build -p factcheck-bridge --release

# llama.cpp is C++ and links the NDK's C++ runtime dynamically.
sysroot="$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib"
cp "$sysroot/aarch64-linux-android/libc++_shared.so" "$out/jniLibs/arm64-v8a/"
cp "$sysroot/x86_64-linux-android/libc++_shared.so" "$out/jniLibs/x86_64/"

# Bindings from a host build of the same crate.
cargo build -q -p factcheck-bridge
cargo run -q -p factcheck-bridge --features bindgen --bin uniffi-bindgen -- \
    generate --library "$target/debug/libfactcheck_bridge.so" \
    --language kotlin --no-format --out-dir "$out/kotlin"
