#pragma once
#include <QObject>
#include <QWidget>
#include <QHash>
#include <QDebug>
#include <QSharedPointer>
#include <QString>
#include <algorithm>
#include <bit>
#include <functional>
#include <stdexcept>

struct ConfigKey {
    QString group, item;
    ConfigKey() = default;
    ConfigKey(QString g, QString i) : group(g), item(i) {}
    bool isValid() const { return !group.isEmpty() && !item.isEmpty(); }
    bool operator==(const ConfigKey& other) const { return group == other.group && item == other.item; }
    bool operator!=(const ConfigKey& other) const { return !(*this == other); }
};
inline size_t qHash(const ConfigKey& k, size_t seed = 0) { return qHash(k.group + k.item, seed); }
inline QDebug operator<<(QDebug d, const ConfigKey& k) { return d << k.group << k.item; }
struct ConfigValue {
    int value;
    ConfigValue(int v) : value(v) {}
    ConfigValue(const QString& v) : value(v.toInt()) {}
};
struct UserSettings {
    QHash<ConfigKey, int> values;
    int writes = 0;
    int getValue(const ConfigKey& k, int fallback) const { return values.value(k, fallback); }
    double getValue(const ConfigKey& k, double fallback) const { return values.value(k, fallback); }
    void set(const ConfigKey& k, ConfigValue v) {
        if (++writes > 100) throw std::runtime_error("recursive settings write");
        values[k] = v.value;
    }
};
using UserSettingsPointer = QSharedPointer<UserSettings>;
enum class MidiOpCode { NoteOff, NoteOn, ControlChange };
struct Stat {
    enum StatType { UNSPECIFIED };
    enum ComputeFlags { COUNT = 1, SUM = 2, AVERAGE = 4, SAMPLE_VARIANCE = 8, MIN = 16, MAX = 32 };
    static void track(const QString&, StatType, ComputeFlags, double) {}
};
struct EngineBuffer {
    enum KeylockEngine { Zero, One, Two };
    static inline bool available[3] = {true, true, true};
    static bool isKeylockEngineAvailable(KeylockEngine e) { return available[e]; }
};
struct WaveformWidgetFactory {
    int fps = 45, writes = 0;
    static WaveformWidgetFactory* instance() { static WaveformWidgetFactory factory; return &factory; }
    void setFrameRate(int value) {
        if (++writes > 32) throw std::runtime_error("recursive waveform setter");
        fps = value;
    }
    int getFrameRate() const { return fps; }
};
struct SampleRate {
    double value = 48000;
    double toDouble() const { return value; }
    bool operator!=(const SampleRate& other) const { return value != other.value; }
};
struct SoundManagerConfig {
    static constexpr unsigned kMaxAudioBufferSizeIndex = 7;
    static constexpr unsigned kDefaultAudioBufferSizeIndex = 5;
    QString api = "ALSA";
    SampleRate rate;
    unsigned index = 3;
    static inline int diskWrites = 0;
    QString getAPI() const { return api; }
    SampleRate getSampleRate() const { return rate; }
    unsigned getAudioBufferSizeIndex() const { return index; }
    void setAudioBufferSizeIndex(unsigned value) {
        index = value != 0 ? std::min(value, kMaxAudioBufferSizeIndex) : 1;
    }
    unsigned getFramesPerBuffer() const {
        if (api == "JACK") {
            if (index == 7) return 4096;
            if (index == 6) return 2048;
            return 1024;
        }
        const unsigned effectiveIndex = index > 0 ? index : kDefaultAudioBufferSizeIndex;
        const unsigned sampleRateKhz = static_cast<unsigned>(rate.value / 1000);
        return std::bit_ceil(sampleRateKhz) << (effectiveIndex - 1);
    }
    void writeToDisk() const { ++diskWrites; }
};
enum class SoundDeviceStatus { Ok, Failed };
struct SoundManager {
    SoundManagerConfig cfg;
    int writes = 0, failures = 0;
    SoundManagerConfig getConfig() const { return cfg; }
    SoundDeviceStatus setConfig(const SoundManagerConfig& next) {
        ++writes;
        if (failures > 0) { --failures; return SoundDeviceStatus::Failed; }
        cfg = next;
        return SoundDeviceStatus::Ok;
    }
    QString getLastErrorMessage(SoundDeviceStatus) const { return "fixture failure"; }
};
struct QMessageBox {
    enum { Question, Ok = 1, Cancel = 2 };
    static inline int prompts = 0, infos = 0, warnings = 0, answer = Cancel;
    static inline std::function<void()> during;
    QMessageBox(int, QString, QString, int, QWidget*) { ++prompts; }
    void setDefaultButton(int value) { if (value != Cancel) throw std::runtime_error("unsafe default"); }
    void setStyleSheet(QString) {}
    int exec() { if (during) during(); return answer; }
    static void information(QWidget*, QString, QString) { ++infos; }
    static void warning(QWidget*, QString, QString) { ++warnings; }
};
