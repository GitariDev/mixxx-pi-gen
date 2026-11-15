#include <QApplication>
#include <QJsonArray>
#include <QListWidget>
#include <QTimer>
#include <iostream>

#include "library/mixpimediadialog.h"
#include "library/mixpimediaactivity.h"

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    using namespace mixxx::media;
    int checks = 0;
    int failures = 0;
    auto check = [&](bool condition, const char* message) {
        ++checks;
        if (!condition) {
            ++failures;
            std::cerr << "FAIL " << message << '\n';
        }
    };
    MediaUseRegistry registry;
    TransferHistory history;
    bool identityValid = true;
    auto lease = registry.acquire({"generation-a", "source-a", {}}, Producer::Copy);
    const QJsonObject volume{{"token", "volume-a"}, {"label", "Music"},
            {"mount", QJsonObject{{"path", "/media/fixture-a"}}}};
    const QJsonObject drive{{"token", "drive-a"}, {"device", "/dev/fixture"},
            {"size", 1000000}, {"volumes", QJsonArray{volume}}};
    const QJsonObject snapshot{{"version", 1}, {"drives", QJsonArray{drive}}};
    MixpiMediaDialog dialog(nullptr,
            [snapshot](MixpiMediaDialog::Receive receive) { receive(snapshot); },
            [](const QJsonObject&, QObject*, std::function<void(QString)>) {
                return MixpiMediaDialog::Cancel{};
            }, [](bool, QString) {}, std::make_shared<QSet<QString>>(),
            [&](const QJsonObject&) {
                return identityValid ? activityText(registry.observe("generation-a"),
                                               history.snapshot({"generation-a", "source-a"})) :
                                       QStringLiteral("Drive identity changed or unavailable");
            });
    auto* list = dialog.findChild<QListWidget*>("mediaDrives");
    auto* timer = dialog.findChild<QTimer*>("mediaActivityTimer");
    check(list && timer && list->count() == 1, "actual dialog inventory and polling");
    if (!list || !timer || list->count() != 1) {
        return 1;
    }
    list->setCurrentRow(0);
    check(list->wordWrap(), "long per-drive state wraps instead of clipping");
    auto* selected = list->currentItem();
    auto tick = [&] { QMetaObject::invokeMethod(timer, "timeout", Qt::DirectConnection); };
    auto text = [&] { return list->item(0)->text(); };
    check(text().contains("Copy/check: 1") && text().contains("No retained transfer result"),
            "admission does not imply an actual transfer");
    const auto job = history.begin({{"generation-a", "source-a"}});
    check(job && history.update(job, "copying", "47"), "actual bound progress admitted");
    tick();
    check(text().contains("Copying: 47%"), "actual dialog displays production history progress");
    check(list->currentItem() == selected, "progress refresh preserves selection");
    check(history.update(job, "verifying", "99"), "verification progress accepted");
    tick();
    check(text().contains("Verifying: 99%") && !text().contains("100%"), "99 percent is not success");
    check(history.finish(job, "verified"), "verified terminal accepted");
    tick();
    check(text().contains("Transfer verified by copy worker: 100%"), "worker verification labeled honestly");
    const auto screenshot = qEnvironmentVariable("MEDIA_TRANSFER_DISPLAY_SCREENSHOT");
    if (!screenshot.isEmpty()) {
        dialog.show();
        application.processEvents();
        check(dialog.grab().save(screenshot), "native fixture screenshot saved");
    }
    check(registry.observe("generation-a").users[8] == 1, "terminal report does not release ownership");
    const auto next = history.begin({{"generation-a", "source-a"}});
    tick();
    check(text().contains("Copying: 0%") && !text().contains("100%"), "new job replaces stale success");
    check(history.update(next, "verifying", "23") && history.finish(next, "failed"), "failure recorded");
    tick();
    check(text().contains("Transfer failed; last progress: 23%"), "failed transfer remains distinct");
    const auto cancelled = history.begin({{"generation-a", "source-a"}});
    check(history.finish(cancelled, "cancelled"), "cancelled terminal recorded");
    tick();
    check(text().contains("Transfer cancelled"), "cancelled display distinct from failure");
    const auto interrupted = history.begin({{"generation-a", "source-a"}});
    history.update(interrupted, "copying", "82");
    history.interrupt(interrupted);
    tick();
    check(text().contains("Transfer interrupted; progress unavailable") && !text().contains("82%"),
            "interruption does not present old progress as current");
    identityValid = false;
    tick();
    check(text().contains("identity changed") && !text().contains("Transfer interrupted"),
            "identity failure replaces all prior transfer state");
    check(!history.snapshot({"generation-a", "different-source"}).valid &&
                    !history.snapshot({"replacement-generation", "source-a"}).valid,
            "replacement binding cannot inherit history");
    TransferSnapshot invalid{true, true, 1, TransferPhase::Copying, TransferOutcome::Verified, 100, 0};
    check(transferText(invalid) == "Transfer result unavailable", "wrong verified phase rejected");
    invalid.phase = TransferPhase::Verifying;
    invalid.progress = 99;
    check(transferText(invalid) == "Transfer result unavailable", "incomplete verified progress rejected");
    invalid.status = TransferOutcome::Running;
    invalid.progress = 100;
    invalid.activeJobs = 1;
    check(transferText(invalid) == "Transfer result unavailable", "running 100 never success");
    invalid.progress = -1;
    check(transferText(invalid) == "Transfer result unavailable", "negative progress rejected");
    if (argc > 1) {
        TransferHistory held;
        const auto old = held.begin({{"old", "old-source"}});
        held.update(old, "verifying", "99");
        held.finish(old, "verified");
        for (std::size_t index = 0; index < TransferHistory::Capacity; ++index) {
            check(held.begin({{"new", "new-source"}}) != 0, "holdout capacity retains active jobs");
        }
        check(!held.snapshot({"old", "old-source"}).valid, "holdout evicted success honestly unknown");
        check(held.begin({{"other", "source"}}) == 0, "holdout full active history rejects another job");
        auto active = held.snapshot({"new", "new-source"});
        check(active.activeJobs == TransferHistory::Capacity &&
                        transferText(active).contains("64 active jobs; newest shown"),
                "holdout concurrent jobs explicitly labeled");
        check(activityText(registry.observe("unused"), {}).contains("not eject clearance"),
                "holdout idle and no history never grant removal authority");
    }
    std::cout << checks << " checks, " << failures << " failures\n";
    return failures ? 1 : 0;
}
