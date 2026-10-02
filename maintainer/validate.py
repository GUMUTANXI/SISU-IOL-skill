"""Validate public links, stable relationships, rule IDs, and skill frontmatter."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

DEFAULT_ROOT=Path(__file__).resolve().parents[1]


def validate(root):
    root=Path(root).resolve(); errors=[]
    skill=root/'skills'/'course-grade-guide'
    catalog=json.loads((skill/'courses'/'catalog.json').read_text(encoding='utf-8'))
    text=(skill/'SKILL.md').read_text(encoding='utf-8')
    if not text.startswith('---\n') or '\n---\n' not in text[4:]: errors.append('Invalid frontmatter')
    front=text.split('---',2)[1]
    if not re.search(r'^name: course-grade-guide$',front,re.M): errors.append('Invalid skill name')
    if not re.search(r'^description: .+',front,re.M): errors.append('Missing skill description')
    fields={}
    for line in front.strip().splitlines():
        if ': ' not in line:
            errors.append('Frontmatter must use simple scalar fields');continue
        key,value=line.split(': ',1)
        if key in fields:errors.append('Duplicate frontmatter key')
        fields[key]=value
    if set(fields)!={'name','description'}:errors.append('Unexpected frontmatter field')
    if len(fields.get('name',''))>64 or len(fields.get('description',''))>1024:errors.append('Frontmatter length exceeded')
    if any(ch in fields.get('description','') for ch in '<>'):errors.append('Invalid description characters')
    tids=[t['teacher_id'] for t in catalog['teachers']]
    if len(set(tids))!=len(tids): errors.append('Duplicate teacher IDs')
    cids=[]; oids=[]; all_rules=set()
    for t in catalog['teachers']:
        if not re.fullmatch(r'T\d{3,}',t['teacher_id']): errors.append('Invalid teacher ID')
        if not (skill/t['path']).is_file(): errors.append(f"Missing teacher profile: {t['teacher_id']}")
    for c in catalog['courses']:
        cid=c['course_id'];cids.append(cid)
        path=skill/c['path']
        if not path.is_file(): errors.append(f'Missing course: {cid}');continue
        body=path.read_text(encoding='utf-8')
        rules=re.findall(r'^### (C\d+-R\d+) · ',body,re.M)
        if not rules or len(rules)!=len(set(rules)): errors.append(f'Absent or repeated rules: {cid}')
        if any(not r.startswith(cid+'-') for r in rules): errors.append(f'Wrong rule scope: {cid}')
        all_rules.update(rules)
        for o in c['offerings']:
            oids.append(o['offering_id'])
            if not set(o['teacher_ids'])<=set(tids): errors.append(f'Unknown teacher: {cid}')
            if not re.fullmatch(r'\d{4}-\d{4}',o['academic_year']): errors.append(f'Invalid year: {cid}')
            if o.get('semester') not in (None,1,2): errors.append(f'Invalid semester: {cid}')
            aids=[a['assignment_id'] for a in o['assignments']]
            if not aids or len(aids)!=len(set(aids)): errors.append(f'Invalid assignments: {cid}')
            if o['offering_id'] not in body: errors.append(f'Offering absent from course text: {cid}')
            for tid in o['teacher_ids']:
                tp=next(t['path'] for t in catalog['teachers'] if t['teacher_id']==tid)
                if o['offering_id'] not in (skill/tp).read_text(encoding='utf-8'):
                    errors.append(f'Teacher/course reverse link absent: {cid}/{tid}')
    if len(cids)!=len(set(cids)): errors.append('Duplicate course IDs')
    if len(oids)!=len(set(oids)): errors.append('Duplicate offering IDs')
    for path in root.rglob('*.md'):
        if '.git' in path.parts: continue
        text=path.read_text(encoding='utf-8')
        for target in re.findall(r'\]\(([^)]+)\)',text):
            if target.startswith(('https://','http://','#')): continue
            rel=target.split('#')[0]
            dest=(path.parent/rel).resolve()
            if root not in dest.parents or not dest.is_file(): errors.append(f'Invalid local link: {path.relative_to(root)} -> {rel}')
        if path.parent.name=='teachers':
            for rid in set(re.findall(r'C\d+-R\d+',text)):
                if rid not in all_rules: errors.append(f'Unknown teacher rule reference: {rid}')
    if catalog.get('score_prediction_enabled') is not False:
        errors.append('Prediction cannot be enabled without a separate reviewed calibration change')
    return errors


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=DEFAULT_ROOT);a=p.parse_args()
    errors=validate(a.root)
    print(json.dumps({'ok':not errors,'errors':errors},ensure_ascii=False,indent=2))
    raise SystemExit(bool(errors))
