from pathlib import Path


class ScratchAdmission:
    def __init__(self, paths):
        self.paths = paths
        self.proofs = []
        for _, path in paths:
            ancestor = Path(path)
            while not ancestor.exists():
                ancestor = ancestor.parent
            self.proofs.append(str(ancestor.stat().st_dev))

    def __enter__(self):
        return self

    def __exit__(self, *error):
        return False

    def start_transfer(self):
        pass

    def transfer_progress(self, phase, progress):
        pass

    def finish_transfer(self, outcome):
        pass
