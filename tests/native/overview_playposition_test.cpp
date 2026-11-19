// Drives the shipped EngineBuffer::updateIndicators, setNewPlaypos and
// fractionalPlayposFromAbsolute (copied verbatim from the patched
// enginebuffer.cpp into enginebuffer_shipped.inc by the runner), with the
// shipped constructor initializers for the members they use, through the
// real control framework. A ControlProxy on [Channel1],playposition stands in
// for WOverview (its skin connection, deck.xml:347-349): it sees each change.
#include <QCoreApplication>
#include <QList>
#include <QSharedPointer>
#include <algorithm>
#include <climits>
#include <cmath>
#include <cstring>
#include <iostream>
#include <new>
#include <string>

#include "audio/frame.h"
#include "audio/types.h"
#include "control/controlobject.h"
#include "control/controlproxy.h"
#include "engine/slipmodestate.h"

static int checks = 0;
static int failures = 0;

static void require(bool condition, const std::string& name) {
    ++checks;
    if (condition) {
        std::cout << "PASS " << name << '\n';
    } else {
        ++failures;
        std::cerr << "FAIL " << name << '\n';
        std::cout << "FAIL " << name << '\n';
    }
}

// PIN src/engine/controls/enginecontrol.h:27-29.
constexpr auto kInitialPlayPosition =
        mixxx::audio::FramePos::fromEngineSamplePos(std::numeric_limits<double>::lowest());

namespace {
// Doubles for the engine parts the copied functions call.
struct Logger {
    bool traceEnabled() const { return false; }
    QDebug trace() const { return qDebug(); }
};
const Logger kLogger;

struct LoopingControl {
    struct LoopInfo {
        mixxx::audio::FramePos startPosition = mixxx::audio::kInvalidFramePos;
        mixxx::audio::FramePos endPosition = mixxx::audio::kInvalidFramePos;
    };
    LoopInfo getLoopInfo() { return {}; }
    bool isLoopingEnabled() { return false; }
    bool isAdjustLoopInActive() { return false; }
    bool isAdjustLoopOutActive() { return false; }
};

struct CueControl {
    long long indicatorUpdates = 0;
    void updateIndicators() { ++indicatorUpdates; }
};

struct ClockControl {
    void updateIndicators(double, mixxx::audio::FramePos, mixxx::audio::SampleRate) {}
};

struct VisualPlayPosition {
    long long sets = 0;
    void set(double, double, double, double, double, SlipModeState, bool, bool, bool,
            double, double, double, double) {
        ++sets;
    }
};

struct ReadAheadManager {
    void notifySeek(mixxx::audio::FramePos) {}
};
struct EngineBufferScale {
    void clear() {}
};
struct EngineControl {
    void notifySeek(mixxx::audio::FramePos) {}
};
} // namespace

#include "enginebuffer_shipped_constants.inc"

class EngineBuffer {
  public:
    EngineBuffer();
    void updateIndicators(double speed, int iBufferSize);
    void setNewPlaypos(mixxx::audio::FramePos position);
    double fractionalPlayposFromAbsolute(mixxx::audio::FramePos absolutePlaypos);
    double getRateRatio() const { return 1.0; }
    void readToCrossfadeBuffer(const int) {}
    void verifyPlay() {}

    // Declared in the order of PIN src/engine/enginebuffer.h:305-479.
    QString m_group = QStringLiteral("[Channel1]");
    LoopingControl* m_pLoopingControl = nullptr;
    ClockControl* m_pClockControl = nullptr;
    CueControl* m_pCueControl = nullptr;
    QList<EngineControl*> m_engineControls;
    ReadAheadManager* m_pReadAheadManager = nullptr;
    mixxx::audio::FramePos m_playPos;
    double m_baserate_old;
    double m_rate_old;
    mixxx::audio::FramePos m_trackEndPositionOld;
    mixxx::audio::SampleRate m_trackSampleRateOld;
    int m_iSamplesSinceLastIndicatorUpdate;
    mixxx::audio::FramePos m_slipPos;
    double m_dSlipRate;
    SlipModeState m_slipModeState;
    ControlObject* m_playposSlider = nullptr;
    ControlProxy* m_pSampleRate = nullptr;
    ControlProxy* m_pPassthroughEnabled = nullptr;
    EngineBufferScale* m_pScale = nullptr;
    mixxx::audio::SampleRate m_sampleRate;
    int m_iLastBufferSize;
    QSharedPointer<VisualPlayPosition> m_visualPlayPos;
};

#include "enginebuffer_shipped.inc"

EngineBuffer::EngineBuffer()
        : MIXPI_SHIPPED_INITIALIZERS {
}

namespace {
constexpr double kRate = 44100;
constexpr double kTrackSeconds = 300;

struct Deck {
    ControlObject playposition{ConfigKey("[Channel1]", "playposition")};
    ControlProxy sampleRate{"[App]", "samplerate"};
    ControlProxy passthrough{"[Channel1]", "passthrough"};
    LoopingControl looping;
    ClockControl clock;
    CueControl cue;
    ReadAheadManager readAhead;
    EngineBufferScale scale;
    alignas(EngineBuffer) unsigned char storage[sizeof(EngineBuffer)];
    EngineBuffer* buffer = nullptr;
    // WOverview stand-in.
    QObject context;
    ControlProxy overview{"[Channel1]", "playposition"};
    long long overviewChanges = 0;
    double overviewValue = -1;

    Deck() {
        // Garbage where the constructor leaves a member uninitialised.
        std::memset(storage, 0xA5, sizeof(storage));
        buffer = new (storage) EngineBuffer();
        buffer->m_pLoopingControl = &looping;
        buffer->m_pClockControl = &clock;
        buffer->m_pCueControl = &cue;
        buffer->m_pReadAheadManager = &readAhead;
        buffer->m_pScale = &scale;
        buffer->m_playposSlider = &playposition;
        buffer->m_pSampleRate = &sampleRate;
        buffer->m_pPassthroughEnabled = &passthrough;
        buffer->m_visualPlayPos = QSharedPointer<VisualPlayPosition>::create();
        overview.connectValueChanged(&context, [this](double value) {
            ++overviewChanges;
            overviewValue = value;
        });
    }
    ~Deck() { buffer->~EngineBuffer(); }

    // What a track load does (slotTrackLoaded, then the first processSeek).
    void load() {
        buffer->m_trackSampleRateOld = mixxx::audio::SampleRate(static_cast<unsigned>(kRate));
        buffer->m_sampleRate = buffer->m_trackSampleRateOld;
        buffer->m_trackEndPositionOld = mixxx::audio::FramePos(kTrackSeconds * kRate);
        buffer->setNewPlaypos(mixxx::audio::FramePos(0));
    }
    // One audio callback: process() moves the play position, then
    // postProcess() calls updateIndicators with the buffer size in samples
    // (PIN src/soundio/soundmanager.cpp:596-600, enginemixer.cpp:398).
    void callback(int frames, double speed) {
        buffer->m_playPos = mixxx::audio::FramePos(buffer->m_playPos.value() + frames * speed);
        buffer->m_iLastBufferSize = frames * 2;
        buffer->updateIndicators(speed, frames * 2);
    }
    double fraction() const { return buffer->m_playPos.value() / (kTrackSeconds * kRate); }
};

long long callbacksFor(double seconds, int frames) {
    return static_cast<long long>(seconds * kRate / frames + 0.5);
}
} // namespace

int main(int argc, char** argv) {
    QCoreApplication application(argc, argv);
    ControlObject sampleRate(ConfigKey("[App]", "samplerate"));
    sampleRate.set(kRate);
    ControlObject passthrough(ConfigKey("[Channel1]", "passthrough"));
    const int threshold = static_cast<int>(kSamplesPerFrame * kRate / kPlaypositionUpdateRate);
    std::cout << "THRESHOLD " << threshold << " samples\n";

    {
        Deck deck;
        require(deck.buffer->m_iSamplesSinceLastIndicatorUpdate == 0,
                "a new EngineBuffer starts its indicator counter at 0");
    }

    for (int frames : {256, 512, 1024}) {
        const std::string size = std::to_string(frames) + " frames: ";
        Deck deck;
        deck.load();
        const long long ten = callbacksFor(10, frames);
        const long long before = deck.overviewChanges;
        const long long cueBefore = deck.cue.indicatorUpdates;
        int peak = 0;
        for (long long i = 0; i < ten; ++i) {
            deck.callback(frames, 1.0);
            peak = std::max(peak, deck.buffer->m_iSamplesSinceLastIndicatorUpdate);
        }
        const long long changes = deck.overviewChanges - before;
        std::cout << size << "10 s plain play: " << changes << " playposition changes, "
                  << deck.cue.indicatorUpdates - cueBefore << " CueControl updates, peak counter "
                  << peak << '\n';
        require(changes >= 140 && changes <= 151,
                size + "playposition updates at about 15 per second (140-151 in 10 s)");
        require(deck.cue.indicatorUpdates - cueBefore == changes,
                size + "CueControl::updateIndicators runs with every playposition update");
        require(peak <= threshold + frames * 2,
                size + "the counter never passes the threshold by more than one buffer");

        // Prime the counter just below INT_MAX (test hook) and keep playing:
        // the old overflow point is passed within a few callbacks.
        deck.buffer->m_iSamplesSinceLastIndicatorUpdate = INT_MAX - 3 * frames * 2;
        const long long primed = deck.overviewChanges;
        bool wentNegative = false;
        for (long long i = 0; i < ten; ++i) {
            deck.callback(frames, 1.0);
            wentNegative = wentNegative || deck.buffer->m_iSamplesSinceLastIndicatorUpdate < 0;
        }
        const long long after = deck.overviewChanges - primed;
        std::cout << size << "10 s from INT_MAX - 3 buffers: " << after
                  << " playposition changes, overview at " << deck.overviewValue << " of "
                  << deck.fraction() << '\n';
        require(!wentNegative, size + "the counter never goes negative after INT_MAX");
        require(after >= 140, size + "playposition keeps updating past the old overflow point");
        require(std::abs(deck.overviewValue - deck.fraction()) * kTrackSeconds <= 0.1,
                size + "the overview is within 0.1 s of the play position past the old overflow point");
    }

    // The session F case: a track loaded, then 7 h without a seek (paused,
    // the engine still calls updateIndicators), then plain play.
    {
        const int frames = 1024;
        Deck deck;
        deck.load();
        deck.callback(frames, 1.0);
        const long long sevenHours = callbacksFor(7 * 3600, frames);
        bool wentNegative = false;
        for (long long i = 0; i < sevenHours; ++i) {
            deck.callback(frames, 0.0);
            wentNegative = wentNegative || deck.buffer->m_iSamplesSinceLastIndicatorUpdate < 0;
        }
        std::cout << "7 h paused (" << sevenHours << " callbacks, "
                  << static_cast<double>(sevenHours) * frames * 2 << " samples): counter "
                  << deck.buffer->m_iSamplesSinceLastIndicatorUpdate << '\n';
        require(!wentNegative, "7 h paused without a seek: the counter never goes negative");
        const long long before = deck.overviewChanges;
        const double start = deck.overviewValue;
        for (long long i = 0; i < callbacksFor(10, frames); ++i) {
            deck.callback(frames, 1.0);
        }
        const long long changes = deck.overviewChanges - before;
        const double moved = (deck.overviewValue - start) * kTrackSeconds;
        std::cout << "after 7 h: 10 s play gives " << changes << " playposition changes, overview moved "
                  << moved << " s\n";
        require(changes >= 140, "after 7 h without a seek, playposition updates while playing");
        require(std::abs(moved - 10.0) <= 0.1,
                "after 7 h without a seek, the overview moves 10 s in 10 s of play");

        // A seek still shows on the next callback.
        deck.buffer->setNewPlaypos(mixxx::audio::FramePos(kTrackSeconds * kRate / 2));
        deck.callback(frames, 0.0);
        require(deck.overviewValue == 0.5, "a seek shows in playposition on the next callback");
    }

    std::cout << "CHECKS " << checks << " FAILURES " << failures << '\n';
    return failures ? 1 : 0;
}
