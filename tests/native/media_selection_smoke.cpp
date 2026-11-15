#include <iostream>

#include "library/mixpimedia.h"

int main(int argc, char** argv) {
    if (argc != 2) {
        return 2;
    }
    QFile input(QString::fromLocal8Bit(argv[1]));
    if (!input.open(QIODevice::ReadOnly)) {
        return 3;
    }
    const auto snapshot = QJsonDocument::fromJson(input.readAll()).object();
    const auto volumes = MixpiMedia::entries(snapshot, false);
    const auto drives = MixpiMedia::entries(snapshot, true);
    if (snapshot.contains("error") || volumes.size() < 2 || drives.size() < 2) {
        return 4;
    }
    for (const auto& value : volumes) {
        const auto volume = value.toObject();
        const auto token = volume.value("token").toString();
        if (MixpiMedia::resolve(snapshot, token, false) != volume || !MixpiMedia::stillPresent(volume)) {
            return 5;
        }
        auto replacement = volume;
        auto physical = volume.value("physical").toObject();
        physical.insert("diskseq", "not-the-observed-generation");
        replacement.insert("physical", physical);
        if (MixpiMedia::stillPresent(replacement)) {
            return 6;
        }
        replacement = volume;
        auto mount = volume.value("mount").toObject();
        mount.insert("id", -1);
        replacement.insert("mount", mount);
        if (MixpiMedia::stillPresent(replacement)) {
            return 7;
        }
    }
    if (!MixpiMedia::resolve(snapshot, "absent", false).isEmpty() ||
            !MixpiMedia::resolve(QJsonObject{{"version", 1}, {"drives", drives}, {"error", "unknown"}},
                    volumes.first().toObject().value("token").toString(), false).isEmpty()) {
        return 8;
    }
    auto duplicated = drives;
    duplicated.append(drives.first());
    if (!MixpiMedia::resolve(QJsonObject{{"version", 1}, {"drives", duplicated}},
                drives.first().toObject().value("token").toString(), true).isEmpty()) {
        return 9;
    }
    std::cout << "PASS: " << drives.size() << " physical drives, " << volumes.size()
              << " volumes; exact selection, stale mount, replacement generation, duplicate token and unknown observation gates\n";
    return 0;
}
