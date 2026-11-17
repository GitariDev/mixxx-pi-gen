#pragma once
// Interface doubles for the save_on_change fixture (R-13). Production code
// compiled with them: preferences/configobject.cpp, the control framework
// (control.cpp, controlobject.cpp, controlproxy.cpp) and mixer/samplerbank.cpp.
// The doubles stand in for the players, the library lookup, tracks, the
// media-use registry and the file dialogs.
#include <QDomNode>
#include <QHash>
#include <QList>
#include <QObject>
#include <QString>
#include <QTimer>
#include <QtDebug>
#include <memory>

#ifndef MIXPI_PINNED_SAVE
#include "control/controlobject.h"
#include "control/controlproxy.h"
#endif

// util/cmdlineargs.h
class CmdlineArgs {
  public:
    static CmdlineArgs& Instance() {
        static CmdlineArgs args;
        return args;
    }
    QString getResourcePath() const {
        return QStringLiteral("/nonexistent-mixpi-resources/");
    }
};

// util/xml.h
class XmlParse {
  public:
    static QString selectNodeQString(const QDomNode&, const QString&) {
        return QString();
    }
};

#ifndef MIXPI_PINNED_SAVE
// track/track.h
class Track {
  public:
    explicit Track(QString location)
            : m_location(std::move(location)) {
    }
    QString getLocation() const {
        return m_location;
    }

  private:
    QString m_location;
};
using TrackPointer = std::shared_ptr<Track>;

// mixer/basetrackplayer.h: the three signals SamplerBank watches.
class BaseTrackPlayer : public QObject {
    Q_OBJECT
  public:
    BaseTrackPlayer(QString group, QObject* pParent)
            : QObject(pParent),
              m_group(std::move(group)) {
    }
    QString getGroup() const {
        return m_group;
    }
    TrackPointer getLoadedTrack() const {
        return m_pTrack;
    }
    // Same order as BaseTrackPlayerImpl: loadingTrack when the load starts,
    // then newTrackLoaded, or playerEmpty for an eject.
    void load(TrackPointer pTrack) {
        TrackPointer pOld = m_pTrack;
        m_pTrack = pTrack;
        emit loadingTrack(pTrack, pOld);
        if (pTrack) {
            emit newTrackLoaded(pTrack);
        } else {
            emit playerEmpty();
        }
    }

  signals:
    void newTrackLoaded(TrackPointer pLoadedTrack);
    void loadingTrack(TrackPointer pNewTrack, TrackPointer pOldTrack);
    void playerEmpty();

  private:
    const QString m_group;
    TrackPointer m_pTrack;
};

class Sampler : public BaseTrackPlayer {
  public:
    using BaseTrackPlayer::BaseTrackPlayer;
};

// mixer/playermanager.h. The library lookup behind a location load can be
// slowed down per location (libraryDelayMs).
class PlayerManager : public QObject {
  public:
    explicit PlayerManager(int samplers) {
        for (int i = 0; i < samplers; ++i) {
            m_samplers.append(new Sampler(
                    QStringLiteral("[Sampler%1]").arg(i + 1), this));
        }
    }
    int numberOfSamplers() const {
        return static_cast<int>(m_samplers.size());
    }
    Sampler* getSampler(int index) const {
        return m_samplers.value(index);
    }
    bool isSamplerGroup(const QString& group, int* pNumber) const {
        for (int i = 0; i < m_samplers.size(); ++i) {
            if (m_samplers.at(i)->getGroup() == group) {
                *pNumber = i + 1;
                return true;
            }
        }
        return false;
    }
    Sampler* sampler(const QString& group) const {
        int number = 0;
        return isSamplerGroup(group, &number) ? m_samplers.at(number - 1) : nullptr;
    }
    void slotLoadTrackToPlayer(TrackPointer pTrack, const QString& group, bool) {
        if (Sampler* pSampler = sampler(group)) {
            pSampler->load(pTrack);
        }
    }
    void slotLoadLocationToPlayer(const QString& location, const QString& group, bool) {
        Sampler* pSampler = sampler(group);
        if (!pSampler) {
            return;
        }
        const int delay = libraryDelayMs.value(location, 0);
        if (delay <= 0) {
            pSampler->load(std::make_shared<Track>(location));
            return;
        }
        QTimer::singleShot(delay, this, [pSampler, location] {
            pSampler->load(std::make_shared<Track>(location));
        });
    }

    QHash<QString, int> libraryDelayMs;

  private:
    QList<Sampler*> m_samplers;
};

// control/controlpushbutton.h
class ControlPushButton : public ControlObject {
  public:
    explicit ControlPushButton(const ConfigKey& key, bool bPersist = false)
            : ControlObject(key, false, false, bPersist) {
    }
};

// util/file.h
inline QString getFilePathWithVerifiedExtensionFromFileDialog(
        const QString&, const QString&, const QString&, const QString&) {
    return QString();
}

// library/media/mediause.h: every use is granted.
namespace mixxx::media {
enum class Producer {
    Import,
    Load,
};
class UnknownUseScope final {
  public:
    explicit UnknownUseScope(Producer) {
    }
    explicit operator bool() const {
        return true;
    }
};
} // namespace mixxx::media
#endif
