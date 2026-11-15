#pragma once

#include <QCoreApplication>
#include <QFileInfo>
#include <QHash>
#include <QSharedPointer>
#include <QString>
#include <QtDebug>
#include <memory>

using CSAMPLE = float;
namespace mixxx::audio {
class SampleRate {
  public:
    static SampleRate fromDouble(double value) { return SampleRate(value); }
    SampleRate(double value = 48000) : m_value(value) {}
    operator double() const { return m_value; }
  private:
    double m_value;
};
}

struct ConfigKey {
    ConfigKey(QString group, QString item) : key(group + item) {}
    QString key;
};
class UserSettings {
  public:
    QString getValueString(const ConfigKey& key) const { return values.value(key.key); }
    int getValue(const ConfigKey& key, int fallback) const {
        return values.contains(key.key) ? values.value(key.key).toInt() : fallback;
    }
    void set(const ConfigKey& key, int value) { values[key.key] = QString::number(value); }
    QHash<QString, QString> values;
};
using UserSettingsPointer = QSharedPointer<UserSettings>;

inline double recordingLifecycleStatus = 0;
inline bool recordingLifecycleInitFailure = false;
inline int recordingLifecycleFlushes = 0;
inline int recordingLifecycleDestructors = 0;
inline int recordingLifecycleDialogs = 0;
inline double recordingLifecycleSampleRate = 48000;

class ControlProxy {
  public:
    ControlProxy(const char*, const char*, QObject*) {}
    double get() const { return recordingLifecycleStatus; }
    void set(double value) { recordingLifecycleStatus = value; }
};
class PollingControlProxy {
  public:
    PollingControlProxy(const QString&, const QString&) {}
    double get() const { return recordingLifecycleSampleRate; }
};

class TrackId {
  public:
    bool isValid() const { return false; }
    bool operator==(const TrackId&) const { return true; }
};
class Track {
  public:
    TrackId getId() const { return {}; }
    QString getTitle() const { return {}; }
    QString getArtist() const { return {}; }
};
using TrackPointer = std::shared_ptr<Track>;
class PlayerInfo {
  public:
    static PlayerInfo& instance() { static PlayerInfo info; return info; }
    TrackPointer getCurrentPlayingTrack() const { return {}; }
};
class Event {
  public:
    static void start(const QString&) {}
    static void end(const QString&) {}
};
constexpr int DLG_WARNING = 1;
class ErrorDialogProperties {
  public:
    void setType(int) {}
    void setTitle(const QString&) {}
    void setText(const QString&) {}
};
class ErrorDialogHandler {
  public:
    static ErrorDialogHandler* instance() { static ErrorDialogHandler handler; return &handler; }
    ErrorDialogProperties* newDialogProperties() { return &properties; }
    void requestErrorDialog(ErrorDialogProperties*) { ++recordingLifecycleDialogs; }
  private:
    ErrorDialogProperties properties;
};

#define DEBUG_ASSERT(condition) Q_ASSERT(condition)
#define VERIFY_OR_DEBUG_ASSERT(condition) if (!(condition))
using ConfigValue = int;
