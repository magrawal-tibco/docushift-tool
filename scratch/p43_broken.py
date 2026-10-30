"""Counts relative references that resolve to no file, in a version tree."""
import sys
from pathlib import Path, PurePosixPath
from docushift.transforms import fragments, links
from docushift.utils.longpath import walk_files

def broken(root: Path) -> int:
    files = {PurePosixPath(r.as_posix()) for r, _ in walk_files(root)}
    count = 0
    for rel, absolute in walk_files(root):
        if rel.suffix != ".md":
            continue
        rel = PurePosixPath(rel.as_posix())
        for _s, _e, raw in fragments._destinations(absolute.read_text(encoding="utf-8")):
            ref = links.classify(raw)
            if ref.resolvable and links.resolve(rel.parent, ref.path) not in files:
                count += 1
    return count

for arg in sys.argv[1:]:
    print(arg, broken(Path(arg)))
