// Linux holdouts compiled against the production header extracted from its patch.
#include "removabletrackcache.h"
#include <QCoreApplication>
#include <QTemporaryDir>
#include <cstdlib>
#include <sys/resource.h>

using Cache = mixxx::RemovableTrackCache;
static void require(bool ok, const char* reason) {
    if (!ok) { qCritical() << reason; std::exit(1); }
}
static void writeFile(const QString& path, const QByteArray& bytes) {
    QFile file(path);
    require(file.open(QIODevice::WriteOnly), "open source");
    require(file.write(bytes) == bytes.size(), "write source");
}
static QByteArray readFile(const QString& path) {
    QFile file(path);
    require(file.open(QIODevice::ReadOnly), "open cache");
    return file.readAll();
}
static int descriptors() {
    return QDir(QStringLiteral("/proc/self/fd")).entryList(QDir::AllEntries | QDir::NoDotAndDotDot).size();
}
int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    QTemporaryDir source;
    require(source.isValid(), "temporary source");
    qputenv("MIXPI_RAM_CACHE_PREFIXES", source.path().toUtf8());
    qputenv("MIXPI_RAM_CACHE_MAX_MB", "1");
    Cache::initialize();
    const int baseline = descriptors();
    const auto track = source.filePath("track.mp3");
    writeFile(track, "aaaa");
    auto lease = Cache::acquire(track, true);
    require(bool(lease), "create watched lease");
    require(descriptors() == baseline + 1, "one notification FD, no retained source FD");
    const auto alias = source.filePath("alias.mp3");
    require(::link(QFile::encodeName(track).constData(), QFile::encodeName(alias).constData()) == 0, "hard link");
    // Drain the link-count ATTRIB change by replacing the snapshot first.
    lease.reset();
    lease = Cache::acquire(track, true);
    require(bool(lease), "snapshot after hard link");
    QFile writer(alias);
    require(writer.open(QIODevice::WriteOnly | QIODevice::ExistingOnly), "in-place alias writer");
    require(writer.write("bbbb", 4) == 4 && writer.flush(), "same-size write while FD remains open");
    require(!lease->proof->unchanged(), "kernel detects in-place write independently of stat identity");
    require(!Cache::acquire(track, false), "same-size in-place write invalidates reuse");
    require(!Cache::acquire(track, false), "drained notification permanently invalidates entry");
    require(readFile(lease->path) == "aaaa", "existing decoder snapshot survives mutation");
    writer.close();
    lease.reset();
    require(descriptors() == baseline, "last lease closes notification FD");
    lease = Cache::acquire(track, true);
    require(lease && readFile(lease->path) == "bbbb", "new copy has changed bytes");
    const auto renamed = source.filePath("moved.mp3");
    require(QFile::rename(track, renamed), "rename source");
    require(Cache::acquire(track, false) == lease, "missing source retains live snapshot");
    require(QFile::rename(renamed, track), "restore source name");
    require(!Cache::acquire(track, false), "move-away-and-back invalidates");
    lease.reset();

    // Moving the containing directory leaves every file identity field exactly
    // unchanged, yet invalidates the path's change proof.
    const auto folder = source.filePath("folder");
    const auto movedFolder = source.filePath("moved-folder");
    require(QDir().mkdir(folder), "create nested source directory");
    const auto nested = folder + "/nested.mp3";
    writeFile(nested, "same");
    lease = Cache::acquire(nested, true);
    require(bool(lease), "nested snapshot");
    struct stat before {}, after {};
    const auto nativeNested = QFile::encodeName(nested);
    require(::stat(nativeNested.constData(), &before) == 0, "initial nested identity");
    require(QDir().rename(folder, movedFolder) && QDir().rename(movedFolder, folder), "move directory away and back");
    require(::stat(nativeNested.constData(), &after) == 0, "restored nested identity");
    require(before.st_dev == after.st_dev && before.st_ino == after.st_ino &&
                    before.st_size == after.st_size &&
                    before.st_mtim.tv_sec == after.st_mtim.tv_sec &&
                    before.st_mtim.tv_nsec == after.st_mtim.tv_nsec &&
                    before.st_ctim.tv_sec == after.st_ctim.tv_sec &&
                    before.st_ctim.tv_nsec == after.st_ctim.tv_nsec,
            "all cached metadata fields exactly identical");
    require(!Cache::acquire(nested, false), "kernel change proof rejects identical metadata");
    lease.reset();

    const auto hybrid = source.filePath("hybrid.wv");
    writeFile(hybrid, "main");
    writeFile(hybrid + 'c', "1111");
    lease = Cache::acquire(hybrid, true);
    require(lease && lease->hasCorrection, "hybrid snapshot");
    writeFile(hybrid + 'c', "2222");
    require(!lease->proof->unchanged(), "companion modification notification");
    require(!Cache::acquire(hybrid, false), "same-size companion edit invalidates");
    lease.reset();
    require(QFile::remove(hybrid + 'c'), "remove companion");
    lease = Cache::acquire(hybrid, true);
    require(lease && !lease->hasCorrection, "snapshot without companion");
    writeFile(hybrid + 'c', "3333");
    require(!lease->proof->unchanged(), "directory detects newly added companion");
    require(!Cache::acquire(hybrid, false), "new companion invalidates lossy snapshot");
    lease.reset();
    lease = Cache::acquire(hybrid, true);
    require(lease && readFile(lease->path + 'c') == "3333", "replacement companion bytes");
    require(QFile::remove(hybrid + 'c'), "unlink companion");
    require(!Cache::acquire(hybrid, false), "companion removal invalidates");
    lease.reset();

    // Overflow from unrelated directory names must invalidate too. Keep only
    // one zero-byte file at a time; alternating create/delete cannot coalesce.
    QFile queueLimit(QStringLiteral("/proc/sys/fs/inotify/max_queued_events"));
    require(queueLimit.open(QIODevice::ReadOnly), "read notification queue limit");
    const int events = queueLimit.readAll().trimmed().toInt();
    queueLimit.close();
    require(events > 0 && events <= 65536, "bounded Linux queue overflow fixture");
    lease = Cache::acquire(track, true);
    require(bool(lease), "overflow snapshot");
    const auto noise = source.filePath("unrelated");
    writeFile(noise, "");
    require(lease->proof->unchanged(), "unrelated directory event permits reuse");
    require(QFile::remove(noise), "remove initial noise");
    for (int i = 0; i <= events / 2; ++i) {
        writeFile(noise, "");
        require(QFile::remove(noise), "remove queue noise");
    }
    require(!lease->proof->unchanged(), "queue overflow fails closed");
    require(!Cache::acquire(track, false), "overflow remains permanently stale");
    lease.reset();
    require(descriptors() == baseline, "overflow lease closes FD");

    // Exhaustion must fall back, not publish an unguarded copy.
    struct rlimit limit {};
    require(::getrlimit(RLIMIT_NOFILE, &limit) == 0, "read FD limit");
    auto reduced = limit;
    reduced.rlim_cur = 32;
    require(::setrlimit(RLIMIT_NOFILE, &reduced) == 0, "lower FD limit");
    int held[64];
    int count = 0;
    while (count < 64) {
        int fd = ::dup(STDERR_FILENO);
        if (fd < 0) { break; }
        held[count++] = fd;
    }
    require(!Cache::acquire(track, true), "watch creation error fails closed");
    while (count) { ::close(held[--count]); }
    require(::setrlimit(RLIMIT_NOFILE, &limit) == 0, "restore FD limit");
    // Repeated early exits after watch creation must close their descriptors.
    writeFile(track, QByteArray(1024 * 1024 + 1, 'x'));
    for (int i = 0; i < 100; ++i) {
        require(!Cache::acquire(track, true), "oversize fallback");
    }
    require(descriptors() == baseline, "early failure does not leak watch FDs");
    qInfo() << "PASS: notification writes/moves/companions/overflow, identical metadata, permanent invalidation, retained leases, FD cleanup/failure";
}
