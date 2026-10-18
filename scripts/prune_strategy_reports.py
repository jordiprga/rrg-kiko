"""Remove only generated report directories no longer referenced by a valid manifest."""
import json
from pathlib import Path
import re
import shutil

from scripts.market import ROOT


def prune(output: Path=ROOT/'public/data/strategies') -> list[str]:
    root=output.resolve()
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('version')!=1: raise ValueError('Invalid manifest; preserve all reports')
    routes=[c['url'] for c in manifest['cases']]
    routes += [manifest[k] for k in ['currentStudyUrl','stockStudyUrl'] if manifest.get(k)]
    keep=set()
    for route in routes:
        if Path(route).is_absolute() or '..' in Path(route).parts:
            raise ValueError('Unsafe live artifact; preserve all reports')
        target=(root/route).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError('Missing or unsafe live artifact; preserve all reports')
        keep.add(Path(route).parts[0])
    targets=[]
    for child in root.iterdir():
        if not child.is_dir() or child.is_symlink() or child.name in keep or not re.fullmatch('[a-f0-9]{20,64}',child.name): continue
        target=child.resolve()
        # Verify absolute targets before recursive removal, including Windows
        # junctions. Never follow a generated-looking link to another directory.
        if target.parent!=root or target!=child.absolute(): continue
        targets.append(target)
    for target in targets:
        print('Remove unreferenced generated report:',str(target),flush=True)
        shutil.rmtree(target)
    return [t.name for t in targets]


if __name__=='__main__': prune()
