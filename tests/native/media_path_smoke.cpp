#include "library/media/mediause.h"

#include <iostream>
#include <stdexcept>

void require(bool condition, const char* message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

int main(int argc, char** argv) {
#ifdef __linux__
    require(argc == 2, "requires caller-owned synthetic fixture directory");
    const std::filesystem::path directory(argv[1]);
    const auto file = directory / "synthetic.raw";
    std::ofstream(file) << "synthetic decoder input, not real audio";
    auto binding = mixxx::media::observePath(file.string());
    require(!binding.generation.empty(), "fixture must have a provable block generation");
    const int descriptor = std::static_pointer_cast<mixxx::rekordbox::SourceDescriptor>(binding.descriptor)->value;
    auto lease = mixxx::media::registry().acquire(binding, mixxx::media::Producer::Load);
    binding.descriptor.reset();
    require(::fcntl(descriptor, F_GETFD) >= 0, "lease pins kernel descriptor");
    auto drain = mixxx::media::registry().beginDrain(binding.generation);
    require(!drain.snapshot().locallyIdle(), "pending load blocks local drain");
    require(!mixxx::media::acquirePath(file.string(), mixxx::media::Producer::Decoder), "new decoder denied");
    auto fallback = mixxx::media::acquirePath(file.string(), mixxx::media::Producer::Decoder, lease);
    require(bool(fallback), "already-admitted original fallback retains ownership");
    const auto alias = directory / "cross-mount";
    std::filesystem::create_symlink("/proc/self/status", alias);
    require(mixxx::media::observePath(alias.string()).generation.empty(), "cross-mount alias is unproven");
    require(!mixxx::media::acquirePath(alias.string(), mixxx::media::Producer::Metadata), "unproven alias denied during drain");
    lease.reset();
    require(!drain.snapshot().locallyIdle(), "fallback still owns original");
    fallback.reset();
    require(drain.snapshot().locallyIdle(), "actual last release makes local registry idle");
    require(::fcntl(descriptor, F_GETFD) == -1 && errno == EBADF, "descriptor released before idle");
    std::filesystem::remove(alias);
    std::filesystem::remove(file);
    std::cout << "PASS ARM production observePath/acquirePath, descriptor lifetime, synthetic cross-mount alias, drain and inherited fallback; no unmount\n";
#else
    (void)argc;
    (void)argv;
    return 77;
#endif
}
