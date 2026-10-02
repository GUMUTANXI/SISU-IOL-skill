"""Extract PRIVATE evidence; never writes inside this public repository.

Python 3.10+. DOCX uses the standard library; PDF requires pypdf.
No network, no model calls, no automatic grading or publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
M = '{http://schemas.openxmlformats.org/officeDocument/2006/math}'
PUBLIC_ROOT = Path(__file__).resolve().parents[1]


def read_text(node, deleted=False, original=False):
    parts = []
    def visit(n):
        if original and n.tag in (W+'ins', W+'moveTo'):
            return
        if n.tag in (W+'del', W+'moveFrom') and not (deleted or original):
            return
        if n.tag in (W+'t', M+'t', W+'delText'):
            parts.append(n.text or '')
        elif n.tag == W+'tab':
            parts.append('\t')
        elif n.tag in (W+'br', W+'cr'):
            parts.append('\n')
        else:
            for child in n:
                visit(child)
    visit(node)
    return ''.join(parts)


def extract_docx(path):
    blocks, comments, revisions, warnings = [], [], [], []
    with ZipFile(path) as z:
        root = ET.fromstring(z.read('word/document.xml'))
        body = root.find(W+'body')
        active, anchors = set(), {}
        for i, p in enumerate(body.iter(W+'p'), 1):
            locator = f'body:p{i}'
            attached = set(active)
            for node in p.iter():
                key = node.get(W+'id')
                if node.tag == W+'commentRangeStart':
                    active.add(key)
                    attached.add(key)
                elif node.tag == W+'commentRangeEnd':
                    attached.add(key)
                    active.discard(key)
                elif node.tag == W+'commentReference':
                    attached.add(key)
            text = read_text(p)
            blocks.append({'locator': locator, 'text': text,
                           'before_tracked_changes': read_text(p, original=True),
                           'comment_ids': sorted(attached)})
            for key in attached:
                anchors.setdefault(key, []).append(locator)
            for rev in p.iter():
                if rev.tag in (W+'ins', W+'del', W+'moveFrom', W+'moveTo'):
                    revisions.append({'locator': locator, 'kind': rev.tag.split('}')[1],
                                      'author': rev.get(W+'author'), 'date': rev.get(W+'date'),
                                      'text': read_text(rev, deleted=True)})
        for name in z.namelist():
            if name == 'word/comments.xml':
                for c in ET.fromstring(z.read(name)).findall(W+'comment'):
                    key = c.get(W+'id')
                    comments.append({'id': key, 'author': c.get(W+'author'),
                                     'date': c.get(W+'date'), 'text': read_text(c),
                                     'anchors': anchors.get(key, [])})
            elif name in ('word/footnotes.xml', 'word/endnotes.xml') or (
                name.startswith(('word/header', 'word/footer')) and name.endswith('.xml')
            ):
                for i, p in enumerate(ET.fromstring(z.read(name)).iter(W+'p'), 1):
                    blocks.append({'locator': f'{name}:p{i}', 'text': read_text(p)})
        images = [n for n in z.namelist() if n.startswith('word/media/')]
        tables = len(list(body.iter(W+'tbl')))
        math = len(list(body.iter(M+'oMath')))
        if images:
            warnings.append('含图片：未 OCR，图中文字和图表内容需人工核查。')
        if tables:
            warnings.append('表格已按 XML 单元格顺序提取；空间关系需核查原件。')
        if math:
            warnings.append('Office Math 仅提取文字，公式结构需核查原件。')
        if list(body.iter(W+'altChunk')):
            warnings.append('存在未展开的 altChunk 嵌入内容，需人工核查。')
        if any(not c['anchors'] for c in comments):
            warnings.append('部分批注没有正文锚点，需人工定位。')
    return dict(blocks=blocks, comments=comments, revisions=revisions,
                image_count=len(images), table_count=tables, warnings=warnings,
                extraction_status='text_extracted_visual_unverified')


def extract_pdf(path):
    from pypdf import PdfReader
    reader = PdfReader(path)
    blocks, warnings = [], []
    for i, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ''
        blocks.append({'locator': f'page:{i}', 'text': text})
        if not text.strip():
            warnings.append(f'第 {i} 页无可提取文字，需 OCR 或人工读取。')
    return dict(blocks=blocks, comments=[], revisions=[], warnings=warnings,
                extraction_status='text_extracted_visual_unverified')


def extract_directory(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == PUBLIC_ROOT or PUBLIC_ROOT in output.parents:
        raise ValueError('Private evidence cannot be written inside the public repository')
    if output == source or source in output.parents or output in source.parents:
        raise ValueError('Source and output directories must not overlap')
    if not source.is_dir():
        raise ValueError('Source must be an existing directory')
    paths = sorted(p for p in source.rglob('*') if p.is_file() and
                   p.suffix.lower() in ('.docx', '.pdf') and not p.name.startswith('~$'))
    output.mkdir(parents=True, exist_ok=True)
    records = []
    seen = {}
    for path in paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        doc_id = 'D' + digest[:16]
        record = dict(document_id=doc_id, sha256=digest, source=str(path),
                      relative_path=str(path.relative_to(source)), duplicate_of=seen.get(digest))
        try:
            data = extract_docx(path) if path.suffix.lower() == '.docx' else extract_pdf(path)
            record['status'] = data['extraction_status']
        except Exception as exc:
            data = dict(blocks=[], comments=[], revisions=[], warnings=[str(exc)], extraction_status='failed')
            record['status'] = 'failed'
        evidence = output / (doc_id + '.v2.json')
        # Content-addressed files are immutable. Changed sources produce new records.
        if not evidence.exists():
            evidence.write_text(json.dumps(dict(document_id=doc_id, extractor_version=2, **data), ensure_ascii=False, indent=2), encoding='utf-8')
        record['evidence_file'] = evidence.name
        record['comments'] = len(data['comments'])
        record['revisions'] = len(data['revisions'])
        record['warnings'] = data['warnings']
        records.append(record)
        seen.setdefault(digest, str(path.relative_to(source)))
    manifest = output / 'manifest.json'
    # Do not discard an earlier inventory when new material arrives.
    if manifest.exists():
        old = manifest.read_bytes()
        backup = output / ('manifest-' + hashlib.sha256(old).hexdigest()[:12] + '.json')
        if not backup.exists():
            backup.write_bytes(old)
    manifest.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--private-output', required=True)
    args = parser.parse_args()
    records = extract_directory(args.source, args.private_output)
    print(json.dumps({'documents': len(records), 'failed': sum(r['status']=='failed' for r in records),
                      'comments': sum(r['comments'] for r in records),
                      'revisions': sum(r['revisions'] for r in records)}, ensure_ascii=False))
    if any(r['status']=='failed' for r in records):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
