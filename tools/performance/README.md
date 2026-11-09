# Performance patch checks

`test-ram-cache.sh` extracts the actual cache header from the image patch,
compiles it with Qt 6, and exercises it independently of Mixxx. Run on Linux
with `g++`, `pkg-config`, `python3`, and Qt6Core development files:

```sh
bash tools/performance/test-ram-cache.sh
```

The test refuses to run while Mixxx is running or its fixed RAM-cache directory
already exists. It creates temporary source files, limits the cache to 1 MiB,
and checks copied bytes, shared-reader lifetime, stale-source replacement,
source removal, the size budget, missing files, concurrent requests and
WavPack companion cleanup. It uses no music library or audio devices.

On 2026-11-09 this exposed an ambiguous Qt 6 `qBound` overload on the Pi's
Qt 6.8.2. Explicit 64-bit bounds fixed compilation, and the smoke check passed.
The ARM package workflow now runs it before compiling Mixxx.

This does **not** validate audio decoding, playback, hotplug races, or safe
physical eject. The cache still falls back to the original track if copying
or decoding fails. Do not unplug a device based only on these results.
