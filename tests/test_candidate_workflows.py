"""Keep provenance alongside packages through each publication route."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CandidateWorkflowTests(unittest.TestCase):
    def test_package_container_has_python_and_transfers_sidecar_before_verification(self):
        workflow = (ROOT / '.github/workflows/mixxx-deb.yml').read_text()
        bootstrap = workflow.index('ca-certificates git sudo python3')
        recipe = workflow.index('bash /workspace/stage3/01-install-packages/01-run.sh')
        transfer = workflow.index('cp /code/build/*.deb.candidate.json /workspace/deploy/')
        verification = workflow.index('mixxx-candidate.py verify --output-dir deploy')
        upload = workflow.index('uses: actions/upload-artifact@v4')
        self.assertLess(bootstrap, recipe)
        self.assertLess(recipe, transfer)
        self.assertLess(transfer, verification)
        self.assertLess(verification, upload)
        self.assertIn('deploy/*.deb.candidate.json', workflow[upload:])
        self.assertIn('sha256sum *.deb *.deb.candidate.json > SHA256SUMS', workflow)

    def test_explicit_package_job_limits_reach_container(self):
        workflow = (ROOT / '.github/workflows/mixxx-deb.yml').read_text()
        for name in ('CMAKE_BUILD_PARALLEL_LEVEL', 'CTEST_PARALLEL_LEVEL',
                     'CCACHE_MAXSIZE', 'CCACHE_COMPRESS'):
            self.assertIn(name + ':', workflow)
            self.assertIn('-e ' + name + ' \\', workflow)

    def test_image_and_nightly_routes_preserve_and_verify_sidecars(self):
        for name in ('main.yml', 'touchscreen-build.yml'):
            workflow = (ROOT / '.github/workflows' / name).read_text()
            verification = workflow.index('mixxx-candidate.py verify --output-dir deploy')
            upload = re.search(r'^\s+- uses: actions/upload-artifact@v4',
                               workflow, re.MULTILINE).start()
            self.assertLess(verification, upload)
            self.assertIn('deploy/*.deb.candidate.json', workflow[upload:])
        nightly = (ROOT / '.github/workflows/main.yml').read_text()
        self.assertIn('mixxx-candidate.py verify --output-dir debs', nightly)
        self.assertLess(nightly.index('mixxx-candidate.py verify --output-dir debs'),
                        nightly.index('name: Delete existing nightly release'))


if __name__ == '__main__':
    unittest.main()
