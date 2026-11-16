// Native check of the shipped util/unixsignalquit.h (mixxx-clean-quit.patch).
// Modes: "term" (SIGTERM in the running loop), "early" (SIGTERM before the
// loop, held until enable()), "hup" (SIGHUP). Built with
// MIXPI_PINNED_NO_HANDLER it is the pinned app, which installs no handler.
#include <QCoreApplication>
#include <QTimer>
#include <csignal>
#include <cstdio>
#include <cstring>
#ifndef MIXPI_PINNED_NO_HANDLER
#include "util/unixsignalquit.h"
#endif

namespace {
int failures = 0;

void check(bool ok, const char* name) {
    std::printf("%s %s\n", ok ? "PASS" : "FAIL", name);
    std::fflush(stdout);
    if (!ok) {
        std::fprintf(stderr, "FAIL %s\n", name);
        ++failures;
    }
}

// Runs the loop until quit() or the guard; true when quit() ended it.
bool runLoop(int guardMs) {
    bool timedOut = false;
    QTimer guard;
    guard.setSingleShot(true);
    QObject::connect(&guard, &QTimer::timeout, [&timedOut] {
        timedOut = true;
        QCoreApplication::quit();
    });
    guard.start(guardMs);
    QCoreApplication::exec();
    return !timedOut;
}
} // namespace

int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    const char* mode = argc > 1 ? argv[1] : "term";
    const int signalNumber = std::strcmp(mode, "hup") == 0 ? SIGHUP : SIGTERM;
    int calls = 0;
    int received = 0;
#ifndef MIXPI_PINNED_NO_HANDLER
    mixxx::UnixSignalQuit signalQuit;
    signalQuit.setQuitFunction([&](int number) {
        ++calls;
        received = number;
        // A second stop while quitting must not re-enter or crash.
        std::raise(SIGTERM);
        std::raise(SIGHUP);
        QCoreApplication::quit();
    });
#endif

    if (std::strcmp(mode, "early") == 0) {
        std::raise(SIGTERM);
        std::printf("ALIVE after SIGTERM before the event loop\n");
        app.processEvents();
        check(calls == 0, "a SIGTERM before enable() is held, not run");
#ifndef MIXPI_PINNED_NO_HANDLER
        signalQuit.enable();
#endif
        check(runLoop(2000), "the held SIGTERM ends the event loop");
    } else {
#ifndef MIXPI_PINNED_NO_HANDLER
        signalQuit.enable();
#endif
        QTimer::singleShot(0, [signalNumber] { std::raise(signalNumber); });
        check(runLoop(2000), "the signal ends the event loop");
    }
    std::printf("ALIVE after the first signal\n");
    check(calls == 1, "the quit function ran exactly once");
    check(received == signalNumber, "the quit function got the signal number");

    // Shutdown continues with the loop still serviced: more signals are harmless.
    std::raise(SIGTERM);
    std::raise(SIGHUP);
    runLoop(200);
    check(calls == 1, "a second SIGTERM and a SIGHUP during shutdown do nothing");

#ifndef MIXPI_PINNED_NO_HANDLER
    // After the loop ended (finalize), a signal must still not kill the app.
    signalQuit.finish();
    check(signalQuit.quitRequested(), "finish() leaves the request marked");
#endif
    for (int i = 0; i < 64; ++i) {
        std::raise(SIGTERM); // Also fills the socket: the handler must not block.
    }
    app.processEvents();
    check(calls == 1, "64 SIGTERMs after the loop neither kill nor re-run the quit");

    std::printf("FAILURES %d\n", failures);
    return failures ? 1 : 0;
}
