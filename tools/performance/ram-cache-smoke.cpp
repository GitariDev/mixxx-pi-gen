// Exercise the actual patched cache on Linux/Qt, without loading audio or Mixxx.
#include "removabletrackcache.h"
#include <QCoreApplication>
#include <QTemporaryDir>
#include <cstdlib>
#include <thread>

static void require(bool ok, const char* reason) {
    if (!ok) { qCritical() << reason; std::exit(1); }
}
static void writeFile(const QString& name, const QByteArray& bytes) {
    QFile file(name);
    require(file.open(QIODevice::WriteOnly), "open test source");
    require(file.write(bytes) == bytes.size(), "write test source");
}
static QByteArray readFile(const QString& name) {
    QFile file(name);
    require(file.open(QIODevice::ReadOnly), "open cached file");
    return file.readAll();
}
int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    QTemporaryDir source;
    require(source.isValid(), "create source directory");
    qputenv("MIXPI_RAM_CACHE_PREFIXES", source.path().toUtf8());
    qputenv("MIXPI_RAM_CACHE_MAX_MB", "1");
    using Cache = mixxx::RemovableTrackCache;
    Cache::initialize();
    const QString track = source.filePath("track.mp3");
    const QByteArray bytes(600 * 1024, 'a');
    writeFile(track, bytes);
    require(!Cache::acquire(track, false), "existing-only must not create");
    auto a = Cache::acquire(track, true);
    require(bool(a), "create cache lease");
    require(readFile(a->path) == bytes, "copy preserves bytes");
    auto b = Cache::acquire(track, false);
    require(a == b, "reuse live lease");
    const auto cached = a->path;
    a.reset();
    require(QFile::exists(cached), "file survives another reader");
    QFile::remove(track);
    require(Cache::acquire(track, false) == b, "existing lease survives source removal");
    writeFile(track, QByteArray(600 * 1024, 'b'));
    require(!Cache::acquire(track, false), "replacement must not reuse stale bytes");
    require(!Cache::acquire(track, true), "held stale lease still counts against budget");
    b.reset();
    require(!QFile::exists(cached), "last reader removes cached file");
    auto replacement = Cache::acquire(track, true);
    require(bool(replacement), "replacement can load after budget released");
    require(readFile(replacement->path) == QByteArray(600 * 1024, 'b'), "replacement bytes");
    replacement.reset();
    writeFile(track, QByteArray(2 * 1024 * 1024, 'x'));
    require(!Cache::acquire(track, true), "oversized track falls back");
    require(!Cache::acquire(source.path(), true), "directory is not audio");
    require(!Cache::acquire(source.filePath("missing.mp3"), true), "missing source falls back");
    writeFile(track, bytes);
    Cache::Lease first, second;
    std::thread one([&] { first = Cache::acquire(track, true); });
    std::thread two([&] { second = Cache::acquire(track, true); });
    one.join(); two.join();
    require(first && first == second, "concurrent requests share one copy");
    first.reset(); second.reset();
    const auto wavpack = source.filePath("hybrid.wv");
    writeFile(wavpack, "main");
    writeFile(wavpack + "c", "correction");
    auto hybrid = Cache::acquire(wavpack, true);
    require(hybrid && hybrid->hasCorrection, "WavPack companion preserved");
    const auto hybridPath = hybrid->path;
    require(readFile(hybridPath + "c") == "correction", "companion bytes");
    hybrid.reset();
    require(!QFile::exists(hybridPath) && !QFile::exists(hybridPath + "c"), "companion cleanup");
    qInfo() << "PASS: cache bytes, leases, source replacement/removal, limits, concurrent loads and WavPack companion";
}
