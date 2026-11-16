#include <QApplication>
#include <QFile>
#include <QLabel>
#include <QPushButton>
#include <QRegularExpression>
#include <QJsonArray>
#include <QListWidget>
#include <QPointer>
#include <QTimer>
#include <iostream>

#include "library/mixpicontrolleddialog.h"
#include "library/mixpimediadialog.h"
#include "library/mixpimediaactivity.h"

// F-10: words a user must not see in Load/Eject, and the plain message the
// controlled dialog shows when eject is not available.
static const char* const kInternalTerms[] = {"reviewed", "clearance", "retained", "service"};
static const QString kEjectUnavailable =
        QStringLiteral("Eject is not available on this system. Keep the drive connected.");

// Every text a user can see in the dialog: title, rows, labels, visible buttons.
static QStringList visibleTexts(QWidget* dialog) {
    QStringList texts{dialog->windowTitle()};
    for (auto* list : dialog->findChildren<QListWidget*>()) {
        for (int row = 0; row < list->count(); ++row) texts.append(list->item(row)->text());
    }
    for (auto* label : dialog->findChildren<QLabel*>()) texts.append(label->text());
    for (auto* button : dialog->findChildren<QPushButton*>()) {
        if (!button->isHidden()) texts.append(button->text());
    }
    return texts;
}

static bool plainTexts(QWidget* dialog) {
    const QRegularExpression deviceNumber(QStringLiteral("\\b\\d+:\\d+\\b"));
    bool clean = true;
    for (const auto& value : visibleTexts(dialog)) {
        for (const char* term : kInternalTerms) {
            if (value.contains(QLatin1String(term), Qt::CaseInsensitive)) {
                std::cout << "OBSERVE internal term '" << term << "' in: " << value.toStdString() << '\n';
                clean = false;
            }
        }
        if (deviceNumber.match(value).hasMatch()) {
            std::cout << "OBSERVE device number in: " << value.toStdString() << '\n';
            clean = false;
        }
    }
    return clean;
}

static QString logged;

static void capture(QtMsgType, const QMessageLogContext&, const QString& message) {
    logged += message + '\n';
}

// F-10 (council round 1): a drive SELECTED, controlled media off. Eject… is
// enabled; it opens the controlled dialog, which refuses in plain words.
template<typename Check>
static void selectedDriveEject(QApplication& application, const QJsonObject& snapshot, Check& check) {
    using namespace mixxx::media;
    MediaUseRegistry registry;
    TransferHistory history;
    int observed = 0;
    int opened = 0;
    int controlledCalls = 0;
    bool controlledMount = true;
    QString controlledToken;
    QPointer<MixpiControlledMedia> operation;
    QPointer<MixpiControlledDialog> controlled;
    QWidget parent;
    parent.resize(800, 444);
    parent.show();
    QPointer<MixpiMediaDialog> dialog = new MixpiMediaDialog(&parent,
            [&observed, snapshot](MixpiMediaDialog::Receive receive) {
                ++observed;
                receive(snapshot);
            },
            [&opened](const QJsonObject&, QObject*, std::function<void(QString)>) {
                ++opened;
                return MixpiMediaDialog::Cancel{};
            },
            // The same steps as MixpiMedia::showControlled(). With controlled
            // media off, openProduction() finds no reviewed profile, so the
            // operation has no broker connection and stays Unavailable.
            [&](bool mount, QString token) {
                ++controlledCalls;
                controlledMount = mount;
                controlledToken = token;
                operation = MixpiControlledMedia::openProduction();
                controlled = new MixpiControlledDialog(operation, mount, &parent, token);
                controlled->show();
            },
            std::make_shared<QSet<QString>>(), [&](const QJsonObject&) {
                return activityText(registry.observe("generation-a"),
                        history.snapshot({"generation-a", "source-a"}));
            });
    dialog->show();
    application.processEvents();
    auto* list = dialog->findChild<QListWidget*>("mediaDrives");
    auto* eject = dialog->findChild<QPushButton*>("mediaEject");
    auto* status = dialog->findChild<QLabel*>("mediaStatus");
    check(!QFile::exists("/etc/mixpi/controlled-media") && !QFile::exists("/etc/mixpi/eject-reviewed"),
            "selected drive: this host has no controlled media profile (as the image)");
    list->setCurrentRow(0);
    application.processEvents();
    check(list->currentRow() == 0 && list->currentItem()->isSelected(), "selected drive: the drive row is selected");
    std::cout << "OBSERVE selected status: " << status->text().toStdString() << '\n';
    check(plainTexts(dialog), "selected drive: no visible label has an internal term or device number");
    check(status->text().contains(kEjectUnavailable),
            "selected drive: the status line says eject is not available, as the controlled dialog does");
    check(eject->isEnabled() && eject->isVisible(), "selected drive: Eject… is enabled (unchanged gate)");
    // Evidence only: grabs of the selected drive and of the dialog after Eject….
    const auto shots = qEnvironmentVariable("MEDIA_SELECTED_SCREENSHOT_DIR");
    if (!shots.isEmpty()) {
        check(dialog->grab().save(shots + "/selected-drive.png"), "selected drive screenshot saved");
    }
    eject->click();
    application.processEvents();
    check(controlledCalls == 1 && !controlledMount && controlledToken == "drive-a" && observed == 2,
            "selected drive: Eject… rechecks the drive and opens the controlled eject dialog for it");
    check(opened == 0, "selected drive: Eject… does not load the drive");
    check(!dialog || !dialog->isVisible(), "selected drive: the Load/Eject dialog gives way to the controlled dialog");
    if (!controlled || !operation) {
        check(false, "selected drive: the controlled dialog is shown");
        return;
    }
    // Let its 50 ms update timer run a few times.
    for (int round = 0; round < 6; ++round) {
        QTimer wait;
        wait.setSingleShot(true);
        wait.start(50);
        while (wait.isActive()) application.processEvents(QEventLoop::AllEvents, 10);
    }
    check(controlled->isVisible() && operation->state() == MixpiControlledMedia::State::Unavailable,
            "selected drive: the controlled dialog is shown in its unavailable state");
    auto* message = controlled->findChildren<QLabel*>().value(0);
    std::cout << "OBSERVE controlled message: " << (message ? message->text().toStdString() : "") << '\n';
    check(message && message->text() == kEjectUnavailable,
            "selected drive: the controlled dialog shows exactly the plain unavailable message");
    check(plainTexts(controlled), "selected drive: the controlled dialog has no internal term or device number");
    if (!shots.isEmpty()) {
        check(controlled->grab().save(shots + "/after-eject.png"), "controlled dialog screenshot saved");
    }
    bool commits = false;
    QStringList usable;
    for (auto* button : controlled->findChildren<QPushButton*>()) {
        if (button->isVisible() && button->isEnabled()) usable.append(button->text());
        commits = commits || ((button->text().contains("Eject", Qt::CaseInsensitive) ||
                                      button->text().contains("Prepare", Qt::CaseInsensitive)) &&
                                     button->isVisible() && button->isEnabled());
    }
    std::cout << "OBSERVE controlled usable buttons: " << usable.join(", ").toStdString() << '\n';
    check(!commits && usable == QStringList{"Close"},
            "selected drive: no button can prepare or commit an eject; only Close is usable");
    // Spy: an unmount or eject request goes only through the operation's
    // broker request. Pressing every usable button except Close and waiting
    // leaves it without a request, not started and still Unavailable.
    for (auto* button : controlled->findChildren<QPushButton*>()) {
        if (button->isVisible() && button->isEnabled() && button->text() != "Close") button->click();
    }
    application.processEvents();
    check(!operation->pending() && !operation->locked() && operation->selectedDescription().isEmpty() &&
                    operation->drives().isEmpty() &&
                    operation->state() == MixpiControlledMedia::State::Unavailable,
            "selected drive: no unmount or eject request is made");
    controlled->close();
    application.processEvents();
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
    auto userFacing = [&] { return plainTexts(&dialog); };
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
                "with no drive selected, Eject is disabled");
    }
    selectedDriveEject(application, snapshot, check);
    std::cout << checks << " checks, " << failures << " failures\n";
    return failures ? 1 : 0;
}
