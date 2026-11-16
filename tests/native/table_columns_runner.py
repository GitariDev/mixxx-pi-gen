"""Real WTrackTableViewHeader, ProxyTrackModel, BrowseTableModel and SettingsDAO TUs.

The header swap is the exact block from WTrackTableView::loadTrackModel. Settings
go to a real SQLite `settings` table through the real TrackModel/SettingsDAO code.
Doubles replace only the track object, player/recording singletons, the browse
thread and the clipboard. --baseline builds without mixxx-table-columns.patch and
must fail: it reproduces the field fault.
"""
import argparse
import hashlib
from pathlib import Path
import shlex
import subprocess
import tempfile

from library_interface_runner import (ROOT, reconstruct, populate_pinned, qt_flags,
                                      qt_environment, moc_path)

STUBS = {
    'track/track_decl.h': '''#pragma once
#include <QList>
#include <QMetaType>
#include <memory>
class Track;
typedef std::shared_ptr<Track> TrackPointer;
typedef QList<TrackPointer> TrackPointerList;
''',
    'track/trackid.h': '''#pragma once
#include <QtGlobal>
class TrackId {
  public:
    bool isValid() const { return false; }
    friend bool operator==(const TrackId&, const TrackId&) { return true; }
};
inline size_t qHash(const TrackId&, size_t seed = 0) { return seed; }
''',
    'track/trackref.h': '''#pragma once
// The real header reaches these through util/fileinfo.h.
#include <QDir>
#include <QString>
#include "track/trackid.h"
#include "util/assert.h"
class TrackRef {
  public:
    static TrackRef fromFilePath(const QString& path) { TrackRef ref; ref.m_location = path; return ref; }
    QString getLocation() const { return m_location; }
  private:
    QString m_location;
};
''',
    'library/coverart.h': '''#pragma once
#include <QString>
class CoverInfoRelative {};
class CoverInfo : public CoverInfoRelative {
  public:
    CoverInfo() = default;
    CoverInfo(const CoverInfoRelative&, const QString&) {}
};
''',
    'track/track.h': '''#pragma once
#include <QString>
#include "library/coverart.h"
#include "track/track_decl.h"
#include "track/trackid.h"
class Track {
  public:
    TrackId getId() const { return {}; }
    CoverInfoRelative getCoverInfo() const { return {}; }
    QString getLocation() const { return {}; }
    void setArtist(const QString&) {}
    void setTitle(const QString&) {}
    void setAlbum(const QString&) {}
    bool trySetBpm(double) { return true; }
    void setKeyText(const QString&) {}
    void setTrackNumber(const QString&) {}
    void setComment(const QString&) {}
    void setComposer(const QString&) {}
    void setYear(const QString&) {}
    void setAlbumArtist(const QString&) {}
    void setGrouping(const QString&) {}
};
''',
    'util/logger.h': '''#pragma once
#include <QtDebug>
namespace mixxx {
class Logger {
  public:
    explicit Logger(const char*) {}
    QDebug info() const { return qInfo(); }
    QDebug warning() const { return qWarning(); }
    QDebug debug() const { return qDebug(); }
};
}
''',
    'util/clipboard.h': '''#pragma once
#include <QUrl>
struct Clipboard { static void start() {} static void add(const QUrl&) {} static void finish() {} };
''',
    'util/fileaccess.h': '''#pragma once
#include <QString>
namespace mixxx {
class FileInfo {
  public:
    bool hasLocation() const { return false; }
    bool isDir() const { return false; }
    QString location() const { return {}; }
};
class FileAccess {
  public:
    const FileInfo& info() const { return m_info; }
  private:
    FileInfo m_info;
};
}
''',
    'library/browse/browsethread.h': '''#pragma once
#include <QList>
#include <QObject>
#include <QSharedPointer>
#include "util/fileaccess.h"
class BrowseTableModel;
class QStandardItem;
class BrowseThread;
typedef QSharedPointer<BrowseThread> BrowseThreadPointer;
class BrowseThread : public QObject {
    Q_OBJECT
  public:
    static BrowseThreadPointer getInstanceRef() {
        static BrowseThreadPointer instance(new BrowseThread);
        return instance;
    }
    void executePopulation(mixxx::FileAccess, BrowseTableModel*) {}
  signals:
    void rowsAppended(const QList<QList<QStandardItem*>>&, BrowseTableModel*);
    void clearModel(BrowseTableModel*);
};
''',
    'library/tabledelegates/previewbuttondelegate.h': '''#pragma once
#include <QStyledItemDelegate>
class WLibraryTableView;
class PreviewButtonDelegate : public QStyledItemDelegate {
  public:
    PreviewButtonDelegate(WLibraryTableView*, int) {}
};
''',
    'widget/wlibrarytableview.h': '''#pragma once
#include <QTableView>
class WLibraryTableView : public QTableView {
    Q_OBJECT
};
''',
    'library/trackcollection.h': '''#pragma once
#include <QSqlDatabase>
class TrackCollection {
  public:
    QSqlDatabase database() const { return QSqlDatabase::database(QStringLiteral("table-columns")); }
};
''',
    'library/trackcollectionmanager.h': '''#pragma once
#include <QString>
#include "library/trackcollection.h"
#include "track/track_decl.h"
#include "track/trackref.h"
class TrackCollectionManager {
  public:
    TrackCollection* internalCollection() const { return &m_collection; }
    bool updateTrackGenre(Track*, const QString&) const { return true; }
    TrackPointer getOrAddTrack(const TrackRef&) { return {}; }
  private:
    mutable TrackCollection m_collection;
};
''',
    'mixer/playerinfo.h': '''#pragma once
#include <QObject>
#include "track/track_decl.h"
class PlayerInfo : public QObject {
    Q_OBJECT
  public:
    static PlayerInfo& instance() { static PlayerInfo info; return info; }
    TrackPointer getTrackInfo(const QString&) { return {}; }
    int numPreviewDecks() const { return 0; }
  signals:
    void trackChanged(const QString& group, TrackPointer pNewTrack, TrackPointer pOldTrack);
};
''',
    'mixer/playermanager.h': '''#pragma once
#include <QString>
struct PlayerManager { static QString groupForPreviewDeck(int i) { return QStringLiteral("[PreviewDeck%1]").arg(i + 1); } };
''',
    'recording/recordingmanager.h': '''#pragma once
#include <QString>
class RecordingManager {
  public:
    const QString& getRecordingLocation() const { return m_location; }
  private:
    QString m_location;
};
''',
    'library/searchqueryparser.h': '''#pragma once
#include <QStringList>
struct SearchQueryParser {
    static QStringList splitQueryIntoWords(const QString& query) {
        return query.split(QChar(' '), Qt::SkipEmptyParts);
    }
};
''',
}


def extract_header_swap(source):
    start = source.index("    // Save the previous track model's header state")
    marker = '    header->setDefaultAlignment(Qt::AlignLeft);\n'
    end = source.index(marker, start) + len(marker)
    return source[start:end]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    # Evidence: the stack without mixxx-acceptance-fixes.patch must fail the
    # readable-width checks (an added column is about 26 px).
    parser.add_argument('--without-acceptance-fixes', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-table-columns-') as temporary:
        target = Path(temporary)
        # mixxx-council-fixes.patch applies on top of touch-dialogs and
        # acceptance-fixes, so it leaves with them.
        exclude = ('mixxx-table-columns.patch', 'mixxx-touch-dialogs.patch',
                   'mixxx-acceptance-fixes.patch', 'mixxx-council-fixes.patch') if args.baseline else ()
        if args.without_acceptance_fixes:
            exclude = ('mixxx-acceptance-fixes.patch', 'mixxx-council-fixes.patch')
        reconstruct(target, exclude=exclude)
        populate = ['src/library/proxytrackmodel.cpp', 'src/library/proxytrackmodel.h',
                    'src/library/browse/browsetablemodel.cpp', 'src/library/browse/browsetablemodel.h',
                    'src/library/trackmodel.h', 'src/library/dao/settingsdao.h',
                    'src/library/dao/settingsdao.cpp', 'src/proto/headers.proto',
                    'src/util/assert.h', 'src/util/math.h',
                    'src/util/parented_ptr.h', 'src/widget/wmenucheckbox.h',
                    'src/widget/wmenucheckbox.cpp', 'src/widget/wtracktableviewheader.h',
                    'src/widget/wtracktableviewheader.cpp', 'src/widget/wtracktableview.cpp',
                    'src/widget/libraryinterface.h', 'src/library/media/mediause.h',
                    'src/library/media/mediauseregistry.h', 'src/library/rekordbox/sourceidentity.h',
                    'src/library/rekordbox/removablemounts.h']
        populate_pinned(target, populate)
        stubs = target / 'stubs'
        for name, text in STUBS.items():
            (stubs / name).parent.mkdir(parents=True, exist_ok=True)
            (stubs / name).write_text(text)
        (target / 'header_swap.inc').write_text(
            extract_header_swap((target / 'src/widget/wtracktableview.cpp').read_text()))
        generated = target / 'generated'
        (generated / 'proto').mkdir(parents=True)
        subprocess.run(['protoc', '--proto_path=' + str(target / 'src/proto'),
                        '--cpp_out=' + str(generated / 'proto'),
                        str(target / 'src/proto/headers.proto')], check=True, timeout=30)
        includes = ['-I' + str(stubs), '-I' + str(target / 'src'), '-I' + str(generated), '-I' + str(target)]
        for header, output in (
                (target / 'src/widget/wtracktableviewheader.h', target / 'src/widget/moc_wtracktableviewheader.cpp'),
                (target / 'src/widget/wmenucheckbox.h', target / 'src/widget/moc_wmenucheckbox.cpp'),
                (target / 'src/library/proxytrackmodel.h', target / 'src/library/moc_proxytrackmodel.cpp'),
                (target / 'src/library/browse/browsetablemodel.h', target / 'src/library/browse/moc_browsetablemodel.cpp'),
                (stubs / 'library/browse/browsethread.h', target / 'moc_browsethread.cpp'),
                (stubs / 'mixer/playerinfo.h', target / 'moc_playerinfo.cpp'),
                (stubs / 'widget/wlibrarytableview.h', target / 'moc_wlibrarytableview.cpp')):
            subprocess.run([moc_path(), *includes, str(header), '-o', str(output)], check=True, timeout=20)
        sources = [ROOT / 'tests/native/table_columns_test.cpp',
                   target / 'src/widget/wtracktableviewheader.cpp',
                   target / 'src/widget/wmenucheckbox.cpp',
                   target / 'src/library/proxytrackmodel.cpp',
                   target / 'src/library/browse/browsetablemodel.cpp',
                   target / 'src/library/dao/settingsdao.cpp',
                   generated / 'proto/headers.pb.cc',
                   target / 'moc_browsethread.cpp', target / 'moc_playerinfo.cpp',
                   target / 'moc_wlibrarytableview.cpp']
        for path in sources[1:6] + [target / 'header_swap.inc', target / 'src/widget/libraryinterface.h']:
            print('PRODUCTION_INPUT', path.relative_to(target),
                  hashlib.sha256(path.read_bytes()).hexdigest(), flush=True)
        command = ['c++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-Wno-deprecated-declarations',
                   '-DMIXXX_DEBUG_ASSERTIONS_ENABLED', *includes, *map(str, sources),
                   '-o', str(target / 'test'),
                   *qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtSql', 'QtTest')),
                   *shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'protobuf'],
                                                        text=True, timeout=15))]
        print('COMMAND', repr(command), flush=True)
        subprocess.run(command, check=True, timeout=300)
        result = subprocess.run([str(target / 'test'), *(['baseline'] if args.baseline else [])],
                                env=qt_environment(), timeout=60)
        if args.without_acceptance_fixes:
            if result.returncode == 0:
                raise SystemExit('Unexpectedly passed without mixxx-acceptance-fixes.patch')
            print('WITHOUT_ACCEPTANCE_FIXES_FAILS exit', result.returncode, flush=True)
        elif args.baseline:
            if result.returncode == 0:
                raise SystemExit('Baseline unexpectedly passed: the fixture does not detect the fault')
            print('BASELINE_REPRODUCED exit', result.returncode, flush=True)
        elif result.returncode:
            raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
