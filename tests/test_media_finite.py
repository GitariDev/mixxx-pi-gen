from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

from test_media_completion import function_text
from test_media_identity import added_header
from test_media_ownership import PATCH, ROOT, production_file


def source(relative):
    override = os.environ.get('MEDIA_FINITE_SOURCE')
    candidate = Path(override) / relative if override else None
    if candidate and candidate.exists():
        return candidate.read_text()
    return production_file(relative)


class FiniteOwnershipTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('c++'), 'C++ required')
    def test_production_cover_helpers_cross_volume_and_cleanup(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-finite-') as directory:
            target = Path(directory)
            (target / 'mediauseregistry.h').write_text(added_header(
                PATCH, 'src/library/media/mediauseregistry.h'))
            template = (ROOT / 'tests/native/media_finite_test.cpp.in').read_text()
            cover = source('src/library/coverartutils.cpp')
            template = template.replace('PRODUCTION_ACQUIRE', function_text(
                added_header(PATCH, 'src/library/media/mediause.h'), 'inline Lease acquirePath('))
            template = template.replace('PRODUCTION_BROWSE', function_text(
                source('src/library/browse/browsetablemodel.cpp'), 'TrackPointer BrowseTableModel::getTrack('))
            template = template.replace('PRODUCTION_SAVE', function_text(
                source('src/mixer/samplerbank.cpp'), 'bool SamplerBank::saveSamplerBankToPath('))
            for marker, signature in [
                ('FIND', 'QList<QFileInfo> CoverArtUtils::findPossibleCoversInFolder('),
                ('SELECT', 'CoverInfoRelative CoverArtUtils::selectCoverArtForTrack(\n        const mixxx::FileInfo&'),
            ]:
                template = template.replace('PRODUCTION_' + marker, function_text(cover, signature))
            unit = target / 'finite.cpp'
            unit.write_text(template)
            executable = target / 'finite'
            compiled = subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                                       '-pthread', '-I' + str(target), str(unit), '-o', str(executable)],
                                      capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(executable), str(target)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS finite cover', result.stdout)

    def test_finite_file_boundaries_admit_before_io(self):
        boundaries = [
            ('library/dao/trackdao', 'QList<TrackRef> TrackDAO::getAllTrackRefs(', 'locationPathPrefixFromRootDir'),
            ('library/dao/trackdao', 'mixxx::FileAccess TrackDAO::relocateCachedTrack(', 'getTrackLocation'),
            ('track/globaltrackcache', 'void GlobalTrackCache::relocateTracks(', 'TrackRef::fromFileInfo'),
            ('library/basesqltablemodel', 'QList<TrackRef> BaseSqlTableModel::getTrackRefs(', 'TrackRef::fromFilePath'),
            ('library/coverart', 'CoverInfo::LoadedImage CoverInfo::loadImage(', 'mixxx::FileInfo('),
            ('mixer/samplerbank', 'bool SamplerBank::loadSamplerBankFromPath(', 'QFile file'),
            ('mixer/samplerbank', 'bool SamplerBank::saveSamplerBankToPath(', 'QFile file'),
            ('library/parser', 'QList<QString> Parser::parse(', 'parseAllLocations'),
            ('library/parserm3u', 'QList<QString> ParserM3u::parseAllLocations(', 'QFile '),
            ('library/parserpls', 'QList<QString> ParserPls::parseAllLocations(', 'QFile '),
            ('library/parsercsv', 'QList<QString> ParserCsv::parseAllLocations(', 'QFile '),
            ('library/parserm3u', 'bool ParserM3u::writeM3UFile(const QString &file_str, const QList<QString> &items, bool useRelativePath, bool useUtf8)', 'QFile '),
            ('library/parserpls', 'bool ParserPls::writePLSFile(', 'QFile '),
            ('library/parsercsv', 'bool ParserCsv::writeCSVFile(', 'QFile '),
            ('library/parsercsv', 'bool ParserCsv::writeReadableTextFile(', 'QFile '),
            ('library/export/engineprimeexportjob', 'void EnginePrimeExportJob::run()', 'QDir().mkpath'),
            ('library/libraryfeature', 'bool LibraryFeature::exportPlaylistItemsIntoFile(', 'QFileInfo::exists'),
            ('util/file', 'QString getFilePathWithVerifiedExtensionFromFileDialog(', 'QFileInfo::exists'),
        ]
        for name, signature, first_io in boundaries:
            with self.subTest(name=name, signature=signature):
                method = function_text(source('src/' + name + '.cpp'), signature)
                self.assertLess(method.index('UnknownUseScope'), method.index(first_io))
                self.assertLess(method.index('if (!operationUse)'), method.index(first_io))

    def test_pre_dao_paths_and_engine_callback_ownership(self):
        for name, signature in [
            ('library/browse/browsetablemodel', 'TrackPointer BrowseTableModel::getTrack('),
            ('library/baseexternalplaylistmodel', 'TrackPointer BaseExternalPlaylistModel::getTrack('),
            ('library/baseexternaltrackmodel', 'TrackPointer BaseExternalTrackModel::getTrack('),
            ('library/banshee/bansheeplaylistmodel', 'TrackPointer BansheePlaylistModel::getTrack('),
            ('library/tabledelegates/coverartdelegate', 'void CoverArtDelegate::requestUncachedCover('),
        ]:
            with self.subTest(name=name):
                method = function_text(source('src/' + name + '.cpp'), signature)
                self.assertLess(method.index('acquirePath'), method.index('TrackRef::fromFilePath'))
                self.assertLess(method.index('PathUseScope'), method.index('TrackRef::fromFilePath'))
        run = function_text(source('src/library/export/engineprimeexportjob.cpp'),
                            'void EnginePrimeExportJob::run()')
        self.assertEqual(run.count('mediaUse = operationUse.lease()'), 3)
        self.assertEqual(run.count('UnknownUseScope operationScope(mediaUse)'), 3)
        self.assertIn('emit failed(tr("Media is draining"))', run)
        for signature in [
            'void TrackCollectionManager::afterTracksUpdated(',
            'void TrackCollectionManager::afterTracksRelocated(',
            'void TrackCollectionManager::afterTrackAdded(',
            'void TrackCollectionManager::purgeTracks(',
            'void TrackCollectionManager::purgeAllTracks(',
            'DirectoryDAO::RelocateResult TrackCollectionManager::relocateDirectory(',
        ]:
            method = function_text(source('src/library/trackcollectionmanager.cpp'), signature)
            self.assertIn('UnknownUseScope operationUse', method)
            self.assertLess(method.index('if (!operationUse)'), method.index('m_externalCollections'))
        save = function_text(source('src/library/trackcollectionmanager.cpp'),
                'TrackCollectionManager::SaveTrackResult TrackCollectionManager::saveTrack(\n        Track*')
        self.assertIn('operationUse ? exportTrackMetadataBeforeSaving', save)
        self.assertEqual(save.count('operationUse && !m_externalCollections.isEmpty()'), 2)
        self.assertNotIn('if (!operationUse)', save)
        playlist = source('src/library/trackset/baseplaylistfeature.cpp')
        for signature in ['void BasePlaylistFeature::slotImportPlaylist()',
                          'void BasePlaylistFeature::slotCreateImportPlaylist()',
                          'void BasePlaylistFeature::slotExportPlaylist()']:
            method = function_text(playlist, signature)
            self.assertLess(method.index('if (!operationUse)'), method.index('QFileInfo'))
