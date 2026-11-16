#include <QApplication>
#include <QFile>
#include <QLabel>
#include <QPushButton>
#include <QRegularExpression>
#include <QJsonArray>
#include <QListWidget>
#include <QTimer>
#include <iostream>

#include "library/mixpimediadialog.h"
#include "library/mixpimediaactivity.h"

static QString logged;

static void capture(QtMsgType, const QMessageLogContext&, const QString& message) {
    logged += message + '\n';
}

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    qInstallMessageHandler(capture);
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
    const QJsonObject drive{{"token", "drive-a"}, {"device", "8:0"},
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
    // F-10: no internal terms and no major:minor device number on any user label.
    auto userFacing = [&] {
        bool clean = true;
        const QRegularExpression deviceNumber(QStringLiteral("\\b\\d+:\\d+\\b"));
        QStringList texts{dialog.windowTitle()};
        for (int row = 0; row < list->count(); ++row) texts.append(list->item(row)->text());
        for (auto* label : dialog.findChildren<QLabel*>()) texts.append(label->text());
        for (auto* button : dialog.findChildren<QPushButton*>()) texts.append(button->text());
        for (const auto& value : texts) {
            clean = clean && !value.contains("clearance", Qt::CaseInsensitive) &&
                    !value.contains("retained", Qt::CaseInsensitive) &&
                    !deviceNumber.match(value).hasMatch();
        }
        return clean;
    };
    check(userFacing(), "idle dialog labels have no internal terms or device number");
    check(list->item(0)->text().startsWith("Music · 0.0 GiB · Available\n/media/fixture-a\n"),
            "drive label keeps name, size, state and mount path");
    check(logged.contains("MixPi Load/Eject drive") && logged.contains("8:0"),
            "device number stays in the log");
    list->setCurrentRow(0);
    check(userFacing(), "selected dialog labels have no internal terms or device number");
    check(list->wordWrap(), "long per-drive state wraps instead of clipping");
    auto* selected = list->currentItem();
    auto tick = [&] { QMetaObject::invokeMethod(timer, "timeout", Qt::DirectConnection); };
    auto text = [&] { return list->item(0)->text(); };
    check(text().contains("Copy/check: 1") && text().contains("No copy has run yet."),
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
    check(text().contains("The last copy was interrupted.") && !text().contains("82%"),
            "interruption does not present old progress as current");
    check(userFacing(), "interrupted dialog labels have no internal terms or device number");
    identityValid = false;
    tick();
    check(text().contains("identity changed") && !text().contains("The last copy was interrupted."),
            "identity failure replaces all prior transfer state");
    check(!history.snapshot({"generation-a", "different-source"}).valid &&
                    !history.snapshot({"replacement-generation", "source-a"}).valid,
            "replacement binding cannot inherit history");
    TransferSnapshot invalid{true, true, 1, TransferPhase::Copying, TransferOutcome::Verified, 100, 0};
    check(transferText(invalid) == "The last copy result is not available.", "wrong verified phase rejected");
    invalid.phase = TransferPhase::Verifying;
    invalid.progress = 99;
    check(transferText(invalid) == "The last copy result is not available.", "incomplete verified progress rejected");
    invalid.status = TransferOutcome::Running;
    invalid.progress = 100;
    invalid.activeJobs = 1;
    check(transferText(invalid) == "The last copy result is not available.", "running 100 never success");
    invalid.progress = -1;
    check(transferText(invalid) == "The last copy result is not available.", "negative progress rejected");
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
        check(activityText(registry.observe("unused"), {}).contains("This does not mean it is safe to remove."),
                "holdout idle and no history never grant removal authority");
    }
    // F-10 (acceptance finding 7): every Load/Eject button is a 48 px touch
    // target, shown on its own and under a window with the MixPi skin styles.
    auto buttonHeights = [&](QDialog& shown, const char* where) {
        shown.show();
        application.processEvents();
        bool tall = true;
        for (auto* button : shown.findChildren<QPushButton*>()) {
            std::cout << "OBSERVE " << where << ' ' << button->text().toStdString() << ' '
                      << button->height() << " px\n";
            tall = tall && button->height() >= 48;
        }
        return tall && shown.findChildren<QPushButton*>().size() == 5;
    };
    check(buttonHeights(dialog, "dialog"), "every Load/Eject button is at least 48 px high");
    dialog.hide();
    QWidget host;
    QString skinStyle;
    for (const auto& path : qEnvironmentVariable("MIXPI_SKIN_QSS").split(':', Qt::SkipEmptyParts)) {
        QFile file(path);
        check(file.open(QIODevice::ReadOnly), "MixPi skin style file readable");
        skinStyle += QString::fromUtf8(file.readAll()) + '\n';
    }
    check(!skinStyle.isEmpty(), "MixPi skin styles loaded");
    host.setStyleSheet(skinStyle);
    host.resize(800, 444);
    host.show();
    {
        MixpiMediaDialog styled(&host,
                [snapshot](MixpiMediaDialog::Receive receive) { receive(snapshot); },
                [](const QJsonObject&, QObject*, std::function<void(QString)>) {
                    return MixpiMediaDialog::Cancel{};
                }, [](bool, QString) {}, std::make_shared<QSet<QString>>());
        styled.setAttribute(Qt::WA_DeleteOnClose, false);
        check(buttonHeights(styled, "skin"), "every Load/Eject button is at least 48 px high under the skin styles");
        check(!styled.findChild<QPushButton*>("mediaEject")->isEnabled(),
                "Eject stays disabled with controlled media off");
    }
    std::cout << checks << " checks, " << failures << " failures\n";
    return failures ? 1 : 0;
}
