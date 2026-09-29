"""Check local handbook links, generated contracts, source hashes and SVG syntax."""
from pathlib import Path
from urllib.parse import unquote, urlsplit
import hashlib
import json
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    errors, links = [], 0
    files = sorted(HERE.rglob('*.md')) + [ROOT / 'README.md', HERE.parent / 'MILKY_WAY_2_ARCHITECTURE.md']
    for p in files:
        for raw in re.findall(r'!?\[[^\]]*\]\(([^\n)]+)\)', p.read_text()):
            target = raw.strip().strip('<>')
            parsed = urlsplit(target)
            if parsed.scheme or not parsed.path: continue
            target_path = (p.parent / unquote(parsed.path)).resolve()
            links += 1
            if not target_path.exists(): errors.append(f'{p.name}: missing {raw}')
            elif not target_path.is_relative_to(ROOT.resolve()):
                errors.append(f'{p.name}: unintended link outside Milky Way 2.0: {raw}')
    json_count = 0
    for p in HERE.rglob('*.json'):
        json.loads(p.read_text()); json_count += 1
    ET.parse(HERE / 'diagrams/system-architecture.svg')
    manifest = json.loads((HERE / 'reference/source-manifest.json').read_text())
    for relative, expected in manifest['source_hashes'].items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        if actual != expected: errors.append(f'Stale generated reference for {relative}')
    tools = json.loads((HERE / 'reference/tools.json').read_text())
    if len(tools) != len({t['name'] for t in tools}): errors.append('Duplicate tool names')
    if len(tools) != manifest['tool_count']: errors.append('Tool count differs from manifest')
    report = {'passed': not errors, 'markdown_files_checked': len(files), 'local_links_checked': links,
              'json_files_parsed': json_count, 'svg_xml_parsed': True,
              'source_hashes_checked': len(manifest['source_hashes']), 'errors': errors}
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
