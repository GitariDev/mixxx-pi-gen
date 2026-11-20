"""Wave J6: build and run the external-table sort fixture.

Compiles the shipped ColumnCache, KeyUtils (with its generated keys.pb),
DbConnection (with the SQLite collation Mixxx sorts text by), the library
preferences and the control framework from the patched stack, with real Qt
and SQLite. BaseTrackCache is the patched basetrackcache.cpp with only the
methods that need a Track object (the cached-track path, which external
tables do not use) replaced by empty doubles. Each external track table is
made with its production schema and column list, read from the patched
source: rekordbox and Serato from their features' createLibraryTable(),
iTunes, Traktor and Rhythmbox from res/schema.xml, Banshee from its playlist
model's temporary table.

--baseline leaves mixxx-external-sort.patch out, to show the checks fail
without it.
"""
import argparse
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from library_interface_runner import (PATCH_DIR, ROOT, reconstruct, populate_pinned, qt_flags,
                                      qt_environment, moc_path)
from shared_columns_runner import CONFIG_FILES, CONFIG_DOUBLES

PATCH = 'mixxx-external-sort.patch'

SOURCES = [
    'library/basetrackcache.h', 'library/basetrackcache.cpp', 'library/columncache.h',
    'library/columncache.cpp', 'library/dao/trackschema.h', 'library/dao/playlistdao.h',
    'library/dao/dao.h', 'library/library_prefs.h', 'library/library_prefs.cpp',
    'library/queryutil.h', 'util/db/dbconnection.h', 'util/db/dbconnection.cpp',
    'util/db/sqllikewildcards.h', 'util/db/dbid.h', 'util/string.h', 'util/assert.h',
    'util/math.h', 'util/types.h', 'util/class.h', 'util/fpclassify.h', 'audio/types.h',
    'track/keyutils.h', 'track/keyutils.cpp', 'track/keys.h', 'track/keys.cpp',
    'track/trackid.h', 'track/track_decl.h', 'proto/keys.proto',
    'preferences/keydetectionsettings.h',
    'library/rekordbox/rekordboxfeature.cpp', 'library/serato/seratofeature.cpp',
    'library/itunes/itunesfeature.cpp', 'library/traktor/traktorfeature.cpp',
    'library/rhythmbox/rhythmboxfeature.cpp', 'library/banshee/bansheeplaylistmodel.cpp',
]

DOUBLES = {
    'library/searchquery.h': '''#pragma once
#include <QString>
#include "track/track_decl.h"
class QueryNode {
  public:
    virtual ~QueryNode() = default;
    QString toSql() const { return QString(); }
    bool match(const TrackPointer&) const { return true; }
};
''',
    'library/searchqueryparser.h': '''#pragma once
#include <QStringList>
#include <memory>
#include "library/searchquery.h"
class TrackCollection;
class SearchQueryParser {
  public:
    SearchQueryParser(TrackCollection*, QStringList) {}
    std::unique_ptr<QueryNode> parseQuery(const QString&, const QString&) const {
        return std::make_unique<QueryNode>();
    }
};
''',
    'library/trackcollection.h': '''#pragma once
#include <QSqlDatabase>
class TrackCollection {
  public:
    explicit TrackCollection(QSqlDatabase database) : m_database(database) {}
    QSqlDatabase database() const { return m_database; }
  private:
    QSqlDatabase m_database;
};
''',
    'track/globaltrackcache.h': '''#pragma once
#include "track/track_decl.h"
#include "track/trackid.h"
class GlobalTrackCacheLocker {
  public:
    TrackPointer lookupTrackById(TrackId) const { return {}; }
};
''',
    'track/track.h': '''#pragma once
// The real headers reach these through util/fileinfo.h and the track DAO;
// stock basetrackcache.cpp (the baseline) relies on them.
#include <QDir>
#include <QSqlQuery>
#include <QSqlRecord>
#include "track/track_decl.h"
''',
    'util/performancetimer.h': '''#pragma once
#include <QString>
struct PerformanceTimerElapsed { QString debugMillisWithUnit() const { return QString(); } };
class PerformanceTimer {
  public:
    void start() {}
    PerformanceTimerElapsed elapsed() const { return {}; }
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
    bool debugEnabled() const { return false; }
};
}
''',
}

# The BaseTrackCache methods that need a Track object; external tables are
# not cached (isCaching false), so these are never reached for them.
TRACK_DOUBLES = {
    'void BaseTrackCache::slotTracksAddedOrChanged(': 'void BaseTrackCache::slotTracksAddedOrChanged(const QSet<TrackId>&) {}\n',
    'void BaseTrackCache::slotScanTrackAdded(': 'void BaseTrackCache::slotScanTrackAdded(TrackPointer) {}\n',
    'void BaseTrackCache::slotTracksRemoved(': 'void BaseTrackCache::slotTracksRemoved(const QSet<TrackId>&) {}\n',
    'void BaseTrackCache::slotTrackDirty(': 'void BaseTrackCache::slotTrackDirty(TrackId) {}\n',
    'void BaseTrackCache::slotTrackClean(': 'void BaseTrackCache::slotTrackClean(TrackId) {}\n',
    'bool BaseTrackCache::isCached(': 'bool BaseTrackCache::isCached(TrackId) const { return false; }\n',
    'void BaseTrackCache::ensureCached(': 'void BaseTrackCache::ensureCached(TrackId) {}\n',
    'const TrackPointer& BaseTrackCache::getCachedTrack(':
        'const TrackPointer& BaseTrackCache::getCachedTrack(TrackId) const { return m_recentTrackPtr; }\n',
    'void BaseTrackCache::replaceRecentTrack(TrackPointer pTrack)':
        'void BaseTrackCache::replaceRecentTrack(TrackPointer) const {}\n',
    'void BaseTrackCache::replaceRecentTrack(TrackId trackId, TrackPointer pTrack)':
        'void BaseTrackCache::replaceRecentTrack(TrackId, TrackPointer) const {}\n',
    'void BaseTrackCache::resetRecentTrack(': 'void BaseTrackCache::resetRecentTrack() const {}\n',
    'bool BaseTrackCache::updateTrackInIndex(\n':
        'bool BaseTrackCache::updateTrackInIndex(const TrackPointer&) { return false; }\n',
    'void BaseTrackCache::updateTrackInIndex(TrackId':
        'void BaseTrackCache::updateTrackInIndex(TrackId) {}\n',
    'void BaseTrackCache::updateTracksInIndex(':
        'void BaseTrackCache::updateTracksInIndex(const QSet<TrackId>&) {}\n',
    'QVariant BaseTrackCache::getTrackValueForColumn(':
        'QVariant BaseTrackCache::getTrackValueForColumn(TrackPointer, int) const { return {}; }\n',
    'int BaseTrackCache::findSortInsertionPoint(':
        'int BaseTrackCache::findSortInsertionPoint(TrackPointer, const QList<SortColumn>&, const int,'
        ' const QVector<TrackId>&) const { return 0; }\n',
}


def function(source, signature):
    start = source.index(signature)
    return source[start:source.index('\n}\n', start) + 3]


def braced(source, start_marker, after=None):
    """The text from start_marker to its closing '};' (a brace list)."""
    origin = source.index(after) if after else 0
    start = source.index(start_marker, origin)
    return source[start:source.index('};', start) + 2]


def raw(text):
    return 'R"MIXPISQL(' + text + ')MIXPISQL"'


def schema_statements(schema, table):
    statements = [re.search(r'CREATE TABLE IF NOT EXISTS ' + table + r' \(.*?\);', schema, re.DOTALL).group(0)]
    statements += re.findall(r'ALTER TABLE ' + table + r' ADD COLUMN [^;]*;', schema, re.IGNORECASE)
    return statements


def table_entry(label, name, id_column, columns_code, create_code):
    return ('    {QStringLiteral("%s"), %s, %s, []() { %s return columns; }(),\n'
            '            [](QSqlDatabase& database) { %s }},\n'
            % (label, name, id_column, columns_code, create_code))


def tables_code(target):
    src = target / 'src/library'
    code = []
    entries = []
    for label, path, feature, constant in (
            ('rekordbox', 'rekordbox/rekordboxfeature.cpp', 'RekordboxFeature::RekordboxFeature(',
             'kRekordboxLibraryTable'),
            ('Serato', 'serato/seratofeature.cpp', 'SeratoFeature::SeratoFeature(', 'kSeratoLibraryTable')):
        source = (src / path).read_text()
        space = 'mixpi_' + label.lower()
        table = re.search(r'^const QString ' + constant + r' = QStringLiteral\("(\w+)"\);$',
                          source, re.MULTILINE).group(1)
        code.append('namespace %s {\n%s}\n' % (space, function(source, 'bool createLibraryTable(')))
        entries.append(table_entry(label, 'QStringLiteral("%s")' % table, 'LIBRARYTABLE_ID',
                                   braced(source, 'QStringList columns = {', feature),
                                   'return %s::createLibraryTable(database, QStringLiteral("%s"));'
                                   % (space, table)))
    schema = (target / 'res/schema.xml').read_text()
    for label, path, feature in (('iTunes', 'itunes/itunesfeature.cpp', 'ITunesFeature::ITunesFeature('),
                                 ('Traktor', 'traktor/traktorfeature.cpp', 'TraktorFeature::TraktorFeature('),
                                 ('Rhythmbox', 'rhythmbox/rhythmboxfeature.cpp',
                                  'RhythmboxFeature::RhythmboxFeature(')):
        source = (src / path).read_text()
        start = source.index(feature)
        table = re.compile(r'QString tableName = "(\w+)";').search(source, start).group(1)
        id_column = re.compile(r'QString idColumn = "(\w+)";').search(source, start).group(1)
        create = ' '.join('if (!QSqlQuery(database).exec(QStringLiteral(%s))) { return false; }' % raw(statement)
                          for statement in schema_statements(schema, table)) + ' return true;'
        entries.append(table_entry(label, 'QStringLiteral("%s")' % table, 'QStringLiteral("%s")' % id_column,
                                   braced(source, 'QStringList columns = {', feature), create))
    source = (src / 'banshee/bansheeplaylistmodel.cpp').read_text()
    defines = '\n'.join(re.findall(r'^#define CLM_\w+ "\w+"$', source, re.MULTILINE))
    constants = '\n'.join(re.findall(r'^const QString k\w+ = QStringLiteral\(CLM_\w+\);$', source, re.MULTILINE))
    statement_at = source.index('"CREATE TEMP TABLE IF NOT EXISTS %1 ("')
    literal = source[source.rindex('QStringLiteral(', 0, statement_at):source.index('.arg(m_tempTableName)',
                                                                                    statement_at)]
    code.append('namespace mixpi_banshee {\n%s\n%s\n}\n' % (defines, constants))
    entries.append(table_entry('Banshee', 'QStringLiteral("mixpi_banshee_playlist")', 'mixpi_banshee::kTrackId',
                               'using namespace mixpi_banshee; ' + braced(source, 'QStringList trackSourceColumns = {')
                               + ' QStringList columns = trackSourceColumns;',
                               'return QSqlQuery(database).exec(%s.arg(QStringLiteral("mixpi_banshee_playlist")));'
                               % literal))
    return ('\n'.join(code) + '\nnamespace {\nQList<Table> productionTables() {\n    return {\n'
            + ''.join(entries) + '    };\n}\n} // namespace\n')


def build(target, baseline):
    names, _ = reconstruct(target, exclude=(PATCH,) if baseline else ())
    populate_pinned(target, ['src/' + name for name in SOURCES] + ['res/schema.xml'])
    populate_pinned(target, ['src/' + name for name in CONFIG_FILES])
    if not baseline and PATCH not in names:
        subprocess.run(['git', 'apply', str(PATCH_DIR / PATCH)], cwd=target, check=True, timeout=15)
        names.append(PATCH)
    print('PATCHES', len(names), 'BASELINE' if baseline else PATCH, flush=True)
    doubles = target / 'doubles'
    for name, text in {**CONFIG_DOUBLES, **DOUBLES}.items():
        (doubles / name).parent.mkdir(parents=True, exist_ok=True)
        (doubles / name).write_text(text)
    # util/string.h's QStringRef overload needs Qt 5 Compat; nothing here uses it.
    string = target / 'src/util/string.h'
    text = string.read_text()
    overload = ('    int compare(const QStringRef& s1, const QStringRef& s2) const {\n'
                '        return m_collator.compare(s1, s2);\n    }\n')
    if '#include <QStringRef>\n' not in text or overload not in text:
        raise SystemExit('util/string.h changed: QStringRef overload not found')
    string.write_text(text.replace('#include <QStringRef>\n', '').replace(overload, ''))
    cache = target / 'src/library/basetrackcache.cpp'
    source = cache.read_text()
    for signature, double in TRACK_DOUBLES.items():
        source = source.replace(function(source, signature), double)
    cache.write_text(source)
    template = (ROOT / 'tests/native/external_sort_test.cpp.in').read_text()
    (target / 'test.cpp').write_text(template.replace('PRODUCTION_TABLES', tables_code(target)))
    generated = target / 'generated'
    (generated / 'proto').mkdir(parents=True)
    subprocess.run(['protoc', '--proto_path=' + str(target / 'src/proto'), '--cpp_out=' + str(generated / 'proto'),
                    str(target / 'src/proto/keys.proto')], check=True, timeout=30)
    includes = ['-I' + str(doubles), '-I' + str(target / 'src'), '-I' + str(generated), '-I' + str(target)]
    for header in ('library/basetrackcache.h', 'library/columncache.h', 'control/control.h',
                   'control/controlobject.h', 'control/controlproxy.h'):
        path = target / 'src' / header
        subprocess.run([moc_path(), *includes, str(path), '-o', str(path.parent / ('moc_' + path.stem + '.cpp'))],
                       check=True, timeout=20)
    sources = [target / 'test.cpp', *[target / 'src' / name for name in (
        'library/basetrackcache.cpp', 'library/columncache.cpp', 'library/library_prefs.cpp',
        'util/db/dbconnection.cpp', 'track/keyutils.cpp', 'track/keys.cpp',
        'preferences/configobject.cpp', 'control/control.cpp', 'control/controlobject.cpp',
        'control/controlproxy.cpp')], generated / 'proto/keys.pb.cc']
    binary = target / 'external-sort-test'
    command = ['c++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-Wno-deprecated-declarations',
               '-Wno-unused-parameter', '-Wno-unused-function', '-DMIXXX_DEBUG_ASSERTIONS_ENABLED',
               '-D__SQLITE3__', *includes, *map(str, sources), '-o', str(binary), '-pthread',
               *qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtSql', 'QtXml')),
               *shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'protobuf', 'sqlite3'],
                                                    text=True, timeout=15))]
    print('COMMAND', repr(command), flush=True)
    subprocess.run(command, check=True, timeout=600)
    return binary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-external-sort-') as temporary:
        target = Path(temporary)
        binary = build(target, arguments.baseline)
        result = subprocess.run([str(binary)], env=qt_environment(), timeout=120)
        return result.returncode


if __name__ == '__main__':
    sys.exit(main())
