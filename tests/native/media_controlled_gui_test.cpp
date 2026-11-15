#include "library/mixpicontrolleddialog.h"
#include "media_browse_refresh_test.h"

#include <QApplication>
#include <QElapsedTimer>
#include <QThread>
#include <cassert>
#include <functional>
#include <iostream>
#include <sys/socket.h>
#include <unistd.h>

using State = MixpiControlledMedia::State;
const QString physical(64, 'a');
const QString replacement(64, 'b');
const QString volume(64, 'c');

void until(const std::function<bool()>& predicate) {
    QElapsedTimer elapsed;
    elapsed.start();
    while (!predicate() && elapsed.elapsed() < 2000) {
        QCoreApplication::processEvents();
        QThread::msleep(1);
    }
    assert(predicate());
}

QJsonObject disk(const QString& token, const QString& device, bool mounted = true) {
    QJsonArray volumes;
    if (mounted) {
        volumes.append(QJsonObject{{"token", volume}, {"label", "Guest"}, {"discriminator", device + " /part1"}});
        volumes.append(QJsonObject{{"token", QString(64, 'd')}, {"label", "Guest"}, {"discriminator", device + " /part2"}});
    }
    return {{"token", token}, {"device", device}, {"diskseq", "51"}, {"volumes", volumes}};
}

struct Backend {
    int peer;
    MixpiControlledMedia operation;
    static int pair(int* peer) {
        int descriptors[2];
        assert(::socketpair(AF_UNIX, SOCK_SEQPACKET | SOCK_NONBLOCK | SOCK_CLOEXEC, 0, descriptors) == 0);
        *peer = descriptors[1];
        return descriptors[0];
    }
    Backend() : operation(pair(&peer), nullptr, 30) { expect("list"); }
    ~Backend() { ::close(peer); }
    void expect(const QString& expected, const QString& token = {}) {
        QByteArray bytes;
        until([&] {
            char buffer[8192];
            const int size = ::recv(peer, buffer, sizeof(buffer), MSG_DONTWAIT);
            if (size > 0) {
                bytes = QByteArray(buffer, size);
            }
            return !bytes.isEmpty();
        });
        const auto request = QJsonDocument::fromJson(bytes).object();
        assert(request.value("op").toString() == expected);
        assert(request.value("token").toString() == token);
    }
    void reply(QJsonObject answer) {
        if (!answer.contains("safe")) {
            answer.insert("safe", false);
        }
        const auto bytes = QJsonDocument(answer).toJson(QJsonDocument::Compact);
        assert(::send(peer, bytes.constData(), bytes.size(), MSG_NOSIGNAL) == bytes.size());
        until([&] { return !operation.pending(); });
    }
    void replyThenRefresh(QJsonObject answer, std::function<void()> afterRefresh = {}) {
        assert(!answer.contains("safe") || answer.value("safe").isBool());
        if (!answer.contains("safe")) {
            answer.insert("safe", false);
        }
        const auto bytes = QJsonDocument(answer).toJson(QJsonDocument::Compact);
        assert(::send(peer, bytes.constData(), bytes.size(), MSG_NOSIGNAL) == bytes.size());
        auto* reader = operation.findChild<QSocketNotifier*>();
        assert(reader);
        bool refreshed = false;
        const auto connection = QObject::connect(reader, &QSocketNotifier::activated, [&] {
            assert(!operation.pending());
            assert(operation.state() == State::Mounted || operation.state() == State::Safe);
            operation.refresh();
            assert(operation.state() == State::Waiting);
            if (afterRefresh) {
                afterRefresh();
            }
            refreshed = true;
        });
        until([&] { return refreshed; });
        QObject::disconnect(connection);
    }
    void inventory(bool mounted = true) {
        reply({{"status", "inventory"}, {"drives", QJsonArray{disk(physical, "8:32", mounted), disk(replacement, "8:80")}}});
        assert(operation.state() == State::Inventory);
    }
    void prepare() {
        inventory();
        operation.begin(physical, true);
        expect("eject", physical);
        reply({{"status", "draining"}});
        expect("poll", physical);
        reply({{"status", "ready"}, {"cancellable", true}});
        assert(operation.state() == State::Ready);
    }
};

QPushButton* button(QWidget* widget, const QString& text) {
    for (auto* found : widget->findChildren<QPushButton*>()) {
        if (found->text() == text) {
            return found;
        }
    }
    assert(false);
    return nullptr;
}

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    testBrowseRefresh();
    for (bool eject : {false, true}) {
        Backend backend;
        QObject owner;
        int completions = 0;
        backend.operation.setCompletionHandler(&owner, [&] { ++completions; });
        if (eject) {
            backend.prepare();
            backend.operation.commit();
            backend.expect("commit", physical);
            backend.reply({{"status", "committing"}, {"cancellable", false}});
            backend.expect("poll", physical);
            backend.replyThenRefresh({{"status", "unmounted"}, {"safe", true},
                    {"token", QJsonValue::Null}, {"removed", QJsonArray{21, 22}}});
        } else {
            backend.inventory(false);
            backend.operation.begin(physical, false);
            backend.expect("mount", physical);
            backend.replyThenRefresh({{"status", "mounted"}, {"token", replacement}});
        }
        backend.expect("list", physical);
        backend.reply({{"status", "inventory"}, {"drives", QJsonArray{disk(replacement, "8:80")}}});
        until([&] { return completions == 1; });
        backend.operation.refresh();
        backend.expect("list", physical);
        backend.reply({{"status", "inventory"}, {"drives", QJsonArray{disk(replacement, "8:80")}}});
        QCoreApplication::processEvents();
        assert(completions == 1);
    }
    {
        Backend backend;
        auto* owner = new QObject;
        int completions = 0;
        backend.operation.setCompletionHandler(owner, [&] { ++completions; });
        backend.inventory(false);
        backend.operation.begin(physical, false);
        backend.expect("mount", physical);
        backend.replyThenRefresh({{"status", "mounted"}, {"token", replacement}}, [&] { delete owner; });
        backend.expect("list", physical);
        backend.reply({{"status", "inventory"}, {"drives", QJsonArray{disk(replacement, "8:80")}}});
        QCoreApplication::processEvents();
        assert(completions == 0);
    }
    for (bool cancel : {false, true}) {
        Backend backend;
        QObject owner;
        int completions = 0;
        backend.operation.setCompletionHandler(&owner, [&] { ++completions; });
        backend.prepare();
        backend.operation.cancel();
        backend.expect("cancel", physical);
        backend.reply({{"status", cancel ? "cancelled" : "quarantined"}});
        QCoreApplication::processEvents();
        assert(completions == 0);
    }
    application.setQuitOnLastWindowClosed(false);
    {
        Backend backend;
        backend.inventory();
        auto* dialog = new MixpiControlledDialog(&backend.operation, false, nullptr);
        dialog->show();
        auto* list = dialog->findChild<QListWidget*>("physicalDisks");
        assert(list->count() == 2 && list->currentRow() == -1);
        assert(list->item(0)->text().contains("8:32") && list->item(0)->text().contains("/part2"));
        assert(list->item(1)->text().contains("8:80"));
        assert(!button(dialog, "Prepare selected disk")->isEnabled());
        list->setCurrentRow(0);
        button(dialog, "Prepare selected disk")->click();
        backend.expect("eject", physical);
        QPointer<QDialog> destroyed(dialog);
        dialog->close();
        QCoreApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete);
        assert(!destroyed && backend.operation.locked());
        backend.reply({{"status", "draining"}});
        backend.expect("poll", physical);
        backend.reply({{"status", "ready"}, {"cancellable", true}});
        auto* reopened = new MixpiControlledDialog(&backend.operation, false, nullptr);
        assert(button(reopened, "Eject irreversibly")->isEnabled());
        button(reopened, "Cancel preparation")->click();
        backend.expect("cancel", physical);
        assert(backend.operation.state() != State::Cancelled);
        until([&] { return backend.operation.message().contains("overdue"); });
        assert(backend.operation.locked());
        backend.reply({{"status", "cancelled"}});
        assert(backend.operation.state() == State::Cancelled && !backend.operation.locked());
        delete reopened;
    }
    {
        Backend backend;
        backend.inventory();
        backend.operation.begin(volume, true);
        assert(!backend.operation.pending());
        backend.operation.refresh();
        backend.expect("list");
        backend.reply({{"status", "inventory"}, {"drives", QJsonArray{disk(replacement, "8:32")}}});
        backend.operation.begin(physical, true);
        assert(!backend.operation.pending());
        backend.operation.begin(replacement, true);
        backend.expect("eject", replacement);
        backend.reply({{"status", "blocked"}, {"error", "Stale physical selection"}});
        assert(backend.operation.state() == State::Unknown && backend.operation.locked());
    }
    {
        Backend backend;
        backend.inventory();
        backend.operation.begin(physical, true);
        backend.expect("eject", physical);
        backend.operation.cancel();
        backend.reply({{"status", "draining"}});
        backend.expect("cancel", physical);
        backend.reply({{"status", "cancelled"}});
        assert(backend.operation.state() == State::Cancelled);
    }
    {
        Backend backend;
        backend.prepare();
        backend.operation.commit();
        backend.expect("commit", physical);
        backend.operation.cancel();
        assert(!backend.operation.canCancel());
        until([&] { return backend.operation.message().contains("overdue"); });
        assert(backend.operation.pending() && backend.operation.locked());
        backend.reply({{"status", "committing"}, {"cancellable", false}});
        backend.expect("poll", physical);
        assert(!backend.operation.message().contains("preparation remains cancellable"));
        backend.reply({{"status", "busy"}});
        backend.expect("poll", physical);
        backend.reply({{"status", "unmounted"}, {"safe", true}, {"token", QJsonValue::Null}, {"removed", QJsonArray{21, 22}}});
        assert(backend.operation.state() == State::Safe && !backend.operation.locked());
        assert(backend.operation.selectedDescription().contains("8:32"));
    }
    for (const auto& failure : {QString("too-late"), QString("quarantined"), QString("blocked")}) {
        Backend backend;
        backend.prepare();
        backend.operation.cancel();
        backend.expect("cancel", physical);
        backend.reply({{"status", failure}});
        assert(backend.operation.state() == (failure == "quarantined" ? State::Quarantined : State::Unknown));
        assert(backend.operation.locked());
    }
    {
        Backend backend;
        backend.prepare();
        backend.operation.commit();
        backend.expect("commit", physical);
        backend.reply({{"status", "unmounted"}, {"safe", true}, {"token", QJsonValue::Null}, {"removed", QJsonArray{21}}});
        assert(backend.operation.state() == State::Unknown);
    }
    {
        Backend backend;
        backend.inventory(false);
        auto* dialog = new MixpiControlledDialog(&backend.operation, true, nullptr);
        auto* list = dialog->findChild<QListWidget*>("physicalDisks");
        assert(list->count() == 1 && list->currentRow() == -1);
        list->setCurrentRow(0);
        button(dialog, "Mount selected disk")->click();
        backend.expect("mount", physical);
        backend.reply({{"status", "mounted"}, {"token", replacement}});
        assert(backend.operation.state() == State::Mounted);
        assert(backend.operation.drives().isEmpty());
        delete dialog;
        backend.operation.refresh();
        backend.expect("list", physical);
        backend.reply({{"status", "inventory"}, {"drives", QJsonArray{disk(replacement, "8:32")}}});
        assert(MixpiControlledMedia::resolve(backend.operation.drives(), physical).isEmpty());
    }
    {
        Backend backend;
        backend.reply({{"status", "inventory"}, {"drives", QJsonArray{disk(physical, "8:32"), disk(physical, "8:80")}}});
        assert(backend.operation.state() == State::Unknown);
    }
    {
        Backend backend;
        backend.prepare();
        ::shutdown(backend.peer, SHUT_RDWR);
        until([&] { return backend.operation.state() == State::Unknown; });
        assert(backend.operation.locked());
    }
    {
        Backend backend;
        backend.prepare();
        backend.operation.commit();
        backend.expect("commit", physical);
        ::shutdown(backend.peer, SHUT_RDWR);
        until([&] { return backend.operation.state() == State::Unknown; });
        assert(backend.operation.locked() && !backend.operation.canCancel());
    }
    {
        Backend backend;
        backend.inventory();
        backend.reply({{"status", "unmounted"}, {"safe", true}, {"token", QJsonValue::Null}, {"removed", QJsonArray{21}}});
        until([&] { return backend.operation.state() == State::Unknown; });
    }
    for (const auto& token : {replacement, QString(64, 'e')}) {
        Backend backend;
        backend.inventory();
        auto* dialog = new MixpiControlledDialog(&backend.operation, false, nullptr, token);
        auto* list = dialog->findChild<QListWidget*>("physicalDisks");
        assert(list->currentRow() == (token == replacement ? 1 : -1));
        assert(button(dialog, "Prepare selected disk")->isEnabled() == (token == replacement));
        assert(backend.operation.state() == State::Inventory && !backend.operation.pending());
        char buffer[1024];
        assert(::recv(backend.peer, buffer, sizeof(buffer), MSG_DONTWAIT) < 0);
        delete dialog;
    }
    {
        MixpiControlledMedia unavailable(-1, nullptr);
        auto* dialog = new MixpiControlledDialog(&unavailable, false, nullptr);
        assert(!button(dialog, "Prepare selected disk")->isEnabled());
        assert(unavailable.state() == State::Unavailable);
        delete dialog;
    }
    std::cout << "PASS production Qt controlled lifecycle and physical chooser (synthetic sockets only)\n";
}
