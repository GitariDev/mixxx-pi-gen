#include <iostream>
#include <stdexcept>

#include "library/rekordbox/sourcecache.h"

using namespace mixxx::rekordbox;

int main() {
    const QString path = QStringLiteral("/media/pi/Guest");
    SourceMount mount{"20", "8:33", "/", path.toStdString()};
    PhysicalGeneration physical{"boot", "mnt:[1]", "/sys/devices/usb/disk", "8:32", "50"};
    const auto oldRevision = QString::fromStdString(databaseRevision(sourceRevision(mount, physical), "4096:1000:0:20"));
    TreeItem root;
    auto* imported = root.appendChild(QStringLiteral("Guest"), QVariant(QList<QString>{
            path, QStringLiteral("::isRecordboxDevice::"), oldRevision}));
    auto data = imported->getData().toList();
    data[1] = QStringLiteral("::isNotRecordboxDevice::");
    imported->setData(data);
    imported->appendChild(QStringLiteral("Imported playlist"), QVariant(QList<QString>{
            path + QStringLiteral("-->Old playlist"), QStringLiteral("::isNotRecordboxDevice::")}));
    if (cachedSourceRow(&root, path, oldRevision) != 0) {
        return 1;
    }
    physical.diskseq = "51";
    const auto newRevision = QString::fromStdString(databaseRevision(sourceRevision(mount, physical), "4096:1000:0:20"));
    if (cachedSourceRow(&root, path, newRevision) != -1 || matchesCachedSource(imported, path, newRevision)) {
        return 2;
    }
    root.removeChildren(0, 1);
    auto* fresh = root.appendChild(QStringLiteral("Guest"), QVariant(QList<QString>{
            path, QStringLiteral("::isRecordboxDevice::"), newRevision}));
    if (fresh->hasChildren() || cachedSourceRow(&root, path, newRevision) != 0 ||
            fresh->getData().toList().value(1).toString() != QStringLiteral("::isRecordboxDevice::")) {
        return 3;
    }
    std::cout << "PASS actual TreeItem and production cache matcher: imported root with playlist rejected after generation replacement, stale node removed, replacement requires fresh import\n";
    return 0;
}
