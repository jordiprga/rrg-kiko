import json
import pytest
from scripts.prune_strategy_reports import prune


def test_only_unreferenced_generated_directories_are_removed(tmp_path):
    keep=tmp_path/('a'*20);keep.mkdir();(keep/'case.json').write_text('{}')
    old=tmp_path/('b'*20);old.mkdir();(old/'old.json').write_text('{}')
    notes=tmp_path/'notes';notes.mkdir();(notes/'keep.txt').write_text('user content')
    (tmp_path/'manifest.json').write_text(json.dumps(dict(version=1,cases=[dict(url='a'*20+'/case.json')])))
    assert prune(tmp_path)==['b'*20]
    assert (keep/'case.json').exists() and (notes/'keep.txt').exists()


def test_missing_live_artifact_preserves_every_previous_report(tmp_path):
    old=tmp_path/('b'*20);old.mkdir()
    (tmp_path/'manifest.json').write_text(json.dumps(dict(version=1,cases=[dict(url='a'*20+'/missing.json')])))
    with pytest.raises(ValueError):prune(tmp_path)
    assert old.exists()
