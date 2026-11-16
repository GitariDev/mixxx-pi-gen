#include <QApplication>
#include <QJsonArray>
#include <QListWidget>
#include <QTimer>
#include <iostream>
#include "library/mixpimediadialog.h"
#ifndef BASELINE
#include "library/mixpimediaactivity.h"
#endif

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    int failures = 0;
    int checks = 0;
    auto check = [&](bool condition, const char* message) {
        ++checks;
        if (!condition) {
            ++failures;
            std::cerr << "FAIL " << message << '\n';
        }
    };
    QString state = "Audio: 1";
    const QJsonObject volume{{"token", "volume-a"}, {"label", "Music"},
            {"mount", QJsonObject{{"path", "/media/fixture-a"}}}};
    const QJsonObject drive{{"token", "drive-a"}, {"device", "/dev/fixture"},
            {"size", 1000000}, {"volumes", QJsonArray{volume}}};
    const QJsonObject snapshot{{"version", 1}, {"drives", QJsonArray{drive}}};
    auto observe = [snapshot](MixpiMediaDialog::Receive receive) { receive(snapshot); };
    auto open = [](const QJsonObject&, QObject*, std::function<void(QString)>) {
        return MixpiMediaDialog::Cancel{};
    };
    auto opened = std::make_shared<QSet<QString>>();
    MixpiMediaDialog dialog(nullptr, observe, open, [](bool, QString) {}, opened
#ifndef BASELINE
            , [&](const QJsonObject& current) {
                check(current.value("token").toString() == "drive-a", "exact drive callback");
                return state;
            }
#endif
    );
    auto* list = dialog.findChild<QListWidget*>("mediaDrives");
    check(list && list->count() == 1, "inventory populated");
    check(list->item(0)->text().contains("Audio: 1"), "initial live state");
    list->setCurrentRow(0);
    auto* selected = list->currentItem();
    auto* timer = dialog.findChild<QTimer*>("mediaActivityTimer");
    auto tick = [&] {
        if (timer) QMetaObject::invokeMethod(timer, "timeout", Qt::DirectConnection);
    };
    state = "Import: 1 / Copy/check: 2";
    tick();
    check(list->item(0)->text().contains(state), "poll changes activity without inventory reload");
    check(list->currentItem() == selected, "poll preserves selected item");
    state = "Drive identity changed or unavailable";
    tick();
    check(list->item(0)->text().contains(state), "identity error replaces prior live activity");
    check(!list->item(0)->text().contains("Copy/check: 2"), "old live state not retained");
    tick();
    check(list->item(0)->text().count(state) == 1, "refresh never appends duplicate history");
#ifndef BASELINE
    using namespace mixxx::media;
    MediaUseRegistry registry;
    auto audio = registry.acquire({"generation-a", "source-a", {}}, Producer::Decoder);
    auto copy = registry.acquire({"generation-b", "source-b", {}}, Producer::Copy);
    auto observed = registry.observe("generation-a");
    check(observed.users[1] == 1 && observed.users[8] == 0, "two-drive counts remain separate");
    check(!observed.draining && !observed.locallyIdle(), "observation does not grant drain clearance");
    check(bool(registry.acquire({"generation-a", "source-a", {}}, Producer::Load)),
            "observation does not block admission");
    auto unknown = registry.acquire({}, Producer::Recording);
    check(activityText(registry.observe("generation-b")).contains("Mixxx may still use this drive."),
            "unknown use visible across generations");
    unknown.reset();
    auto drain = registry.beginDrain("generation-a");
    check(activityText(registry.observe("generation-a")).contains("Release requested"),
            "drain state is observable");
    check(!registry.acquire({"generation-a", "source-a", {}}, Producer::Import),
            "observation does not weaken draining refusal");
    audio.reset();
    check(drain.snapshot().locallyIdle(), "original drain semantics unchanged");
    drain.cancel();
    check(activityText(registry.observe("generation-a")) == "Mixxx is not using this drive. This does not mean it is safe to remove.",
            "zero use is not copy success or eject authority");
    check(activityText(registry.observe("generation-b")).contains("Copy/check: 1"),
            "copy admission not represented as transfer completion or percentage");
    if (argc > 1) {
        auto next = registry.acquire({"generation-c", "source-c", {}}, Producer::Analysis);
        check(registry.observe("generation-c").users[2] == 1 &&
                registry.observe("generation-c").users[8] == 0,
                "holdout replacement generation cannot inherit old copy count");
        copy.reset();
        check(registry.observe("generation-b").users[8] == 0 &&
                registry.observe("generation-c").users[2] == 1,
                "holdout old worker release cannot release replacement worker");
    }
#endif
    std::cout << checks << " checks, " << failures << " failures\n";
    return failures ? 1 : 0;
}
