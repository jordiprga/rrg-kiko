#!/usr/bin/env python3
"""Build the two installable WordPress ZIPs and the client handoff bundle."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT.parent / 'public' / 'inframarinos' / 'descargas'


def add_bytes(archive, name, data):
    # Stable timestamps and portable read permissions, including on Windows.
    info = ZipInfo(name, (2026, 11, 7, 0, 0, 0))
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.compress_type = ZIP_DEFLATED
    archive.writestr(info, data)


def package(source, filename):
    path = OUTPUT / filename
    with ZipFile(path, 'w', ZIP_DEFLATED) as archive:
        for item in sorted(source.rglob('*')):
            if item.is_file():
                add_bytes(archive, str(item.relative_to(ROOT)), item.read_bytes())
    return path


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    theme = package(ROOT / 'inframarinos', 'inframarinos-tema.zip')
    plugin = package(ROOT / 'inframarinos-gestion', 'inframarinos-gestion.zip')
    bundle = OUTPUT / 'inframarinos-wordpress.zip'
    with ZipFile(bundle, 'w', ZIP_DEFLATED) as archive:
        add_bytes(archive, theme.name, theme.read_bytes())
        add_bytes(archive, plugin.name, plugin.read_bytes())
        add_bytes(archive, 'LEEME.txt', (ROOT / 'README.md').read_bytes())
    for path in (theme, plugin, bundle):
        with ZipFile(path) as archive:
            assert archive.testzip() is None
        print(f'{path.relative_to(ROOT.parent)}: {path.stat().st_size:,} bytes')


if __name__ == '__main__':
    main()
