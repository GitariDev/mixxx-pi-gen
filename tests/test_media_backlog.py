from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

from test_media_completion import function_text
from test_media_identity import added_header
from test_media_ownership import PATCH, ROOT, production_file


@unittest.skipUnless(shutil.which('c++'), 'C++ required')
class NativeBacklogTests(unittest.TestCase):
    def test_production_pending_cancel_retry(self):
        override = os.environ.get('MEDIA_BACKLOG_SOURCE')
        def source(path):
            candidate = Path(override) / path if override else None
            return candidate.read_text() if candidate and candidate.exists() else production_file(path)
        with tempfile.TemporaryDirectory(prefix='mixpi-backlog-') as directory:
            target = Path(directory)
            (target / 'mediauseregistry.h').write_text(added_header(PATCH, 'src/library/media/mediauseregistry.h'))
            text = (ROOT / 'tests/native/media_backlog_test.cpp.in').read_text()
            methods = {
                'ACQUIRE_PATH': ('src/library/media/mediause.h', 'inline Lease acquirePath('),
                'SCHEDULE': ('src/analyzer/trackanalysisscheduler.cpp', 'bool TrackAnalysisScheduler::scheduleTrack('),
                'SUBMIT': ('src/analyzer/trackanalysisscheduler.cpp', 'bool TrackAnalysisScheduler::submitNextTrack('),
                'STOP': ('src/analyzer/trackanalysisscheduler.cpp', 'void TrackAnalysisScheduler::stop('),
                'WORKER_SUBMIT': ('src/analyzer/analyzerthread.cpp', 'bool AnalyzerThread::submitNextTrack('),
                'SCAN': ('src/library/scanner/libraryscanner.cpp', 'void LibraryScanner::scan('),
                'TASK_CREATE': ('src/library/scanner/scannertask.cpp', 'ScannerTask::ScannerTask('),
                'TASK_DESTROY': ('src/library/scanner/scannertask.cpp', 'ScannerTask::~ScannerTask('),
            }
            for marker, (path, signature) in methods.items():
                body = added_header(PATCH, path) if path.endswith('mediause.h') else source(path)
                text = text.replace('PRODUCTION_' + marker, function_text(body, signature))
            unit = target / 'backlog.cpp'
            unit.write_text(text)
            executable = target / 'backlog'
            result = subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                                     '-pthread', '-I' + str(target), str(unit), '-o', str(executable)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS backlog', result.stdout)

    def test_scanner_handoff_and_cleanup_order(self):
        source = production_file('src/library/scanner/libraryscanner.cpp')
        start = function_text(source, 'void LibraryScanner::slotStartScan(')
        self.assertLess(start.index('m_scanMediaUse.reset()'), start.index('changeScannerState(IDLE)'))
        self.assertLess(start.index('m_scannerGlobal->mediaUse ='), start.index('rootDir.exists()'))
        finish = function_text(source, 'void LibraryScanner::slotFinishUnhashedScan(')
        self.assertLess(finish.index('cleanUpScan()'), finish.index('m_scanMediaUse.reset()'))
        self.assertLess(finish.index('m_scanMediaUse.reset()'), finish.index('changeScannerState(FINISHED)'))
        queue = function_text(source, 'void LibraryScanner::queueTask(')
        self.assertNotIn('watchTask()', queue)
        self.assertLess(queue.index('!pTask->hasMediaUse()'), queue.index('m_pool.start(pTask)'))
        for name in ['importfilestask', 'recursivescandirectorytask']:
            run = production_file('src/library/scanner/' + name + '.cpp')
            self.assertIn('if (!m_mediaUse)', run)
