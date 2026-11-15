#pragma once
// Labeled doubles: only the members the pinned LibraryScanner constructor
// wiring names. The real wiring text is included from the patched source.
#include <QObject>
#include <QScopedPointer>
#include <QString>
#include "library/scanner/libraryscannerdlg.h"

class TrackDAO : public QObject {
    Q_OBJECT
  signals:
    void progressVerifyTracksOutside(const QString&);
    void progressCoverArt(const QString&);
};

class LibraryScanner : public QObject {
    Q_OBJECT
  public:
    LibraryScanner();
    int cancelled = 0;
    TrackDAO m_trackDao;
    QScopedPointer<LibraryScannerDlg> m_pProgressDlg;
  signals:
    void scanStarted();
    void scanFinished();
    void progressHashing(const QString&);
    void progressLoading(const QString& path);
  public slots:
    void slotCancel() { ++cancelled; }
};
