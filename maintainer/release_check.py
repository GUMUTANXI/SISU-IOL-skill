"""Read-only release scan. Private inputs stay external. Never prints matching secrets."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess

DEFAULT_ROOT=Path(__file__).resolve().parents[1]
TEXT_EXT={'.md','.json','.py','.txt','.yaml','.yml'}
WINDOW=48


def normalized(value):
    return re.sub(r'\s+','',value).casefold()


def evidence_windows(folder):
    windows=set()
    if folder is None: return windows
    folder=Path(folder)
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    for record in manifest:
        data=json.loads((folder/record['evidence_file']).read_text(encoding='utf-8'))
        for block in data.get('blocks',[])+data.get('comments',[])+data.get('revisions',[]):
            for field in ('text','before_tracked_changes'):
                s=normalized(block.get(field,''))
                windows.update(s[i:i+WINDOW] for i in range(max(0,len(s)-WINDOW+1)))
    return windows


def check_text(text, tokens=(), private_roots=(), windows=frozenset()):
    findings=[];s=normalized(text)
    if any(normalized(t) in s for t in tokens if t): findings.append('private_identity_or_title')
    if any(normalized(t).replace('\\','/') in s.replace('\\','/') for t in private_roots if t): findings.append('private_path')
    if re.search(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b',text): findings.append('email_address')
    if re.search(r'(?<!\d)\d{9,12}(?!\d)',text): findings.append('possible_student_id')
    # Formal rubric point allocations are allowed; personal-score labels are not.
    if re.search(r'(?:个人成绩|实际得分|样本得分|最终总分|总评成绩)\s*[:：=]?\s*\d+(?:\.\d+)?',text): findings.append('personal_grade')
    if re.search(r'\d+(?:\.\d+)?分[-_]',text): findings.append('grade_prefixed_filename')
    if windows and any(s[i:i+WINDOW] in windows for i in range(max(0,len(s)-WINDOW+1))): findings.append('source_excerpt_overlap')
    return findings


def git(root,*args):
    return subprocess.run(['git','-C',str(root),*args],capture_output=True,check=False)


def scan(root,denylist=None,evidence_dir=None,include_git=True):
    root=Path(root).resolve();findings=[]
    for input_path in (denylist,evidence_dir):
        if input_path is not None:
            p=Path(input_path).resolve()
            if p==root or root in p.parents:
                raise ValueError('Private scan inputs must be outside the public repository')
    deny=json.loads(Path(denylist).read_text(encoding='utf-8')) if denylist else {}
    windows=evidence_windows(evidence_dir)
    def inspect(label,blob):
        try: text=blob.decode('utf-8')
        except UnicodeDecodeError:
            findings.append({'file':label,'reason':'non_text_content'});return
        for reason in check_text(label+'\n'+text,deny.get('tokens',[]),deny.get('private_roots',[]),windows):
            findings.append({'file':label,'reason':reason})
    for p in root.rglob('*'):
        rel=p.relative_to(root)
        if '.git' in rel.parts or '__pycache__' in rel.parts: continue
        if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):
            findings.append({'file':str(rel),'reason':'link_or_junction_not_allowed'});continue
        if not p.is_file(): continue
        if p.suffix not in TEXT_EXT and p.name not in ('.gitignore','.gitattributes'):
            findings.append({'file':str(rel),'reason':'unexpected_file_type'});continue
        inspect(str(rel),p.read_bytes())
    if include_git and (root/'.git').exists():
        staged=git(root,'ls-files','--stage','-z')
        if staged.returncode: raise RuntimeError('Cannot inspect Git index')
        blobs={}
        for item in staged.stdout.split(b'\0'):
            if not item: continue
            meta,name=item.split(b'\t',1);mode,oid,_=meta.split()
            label='index:'+name.decode('utf-8','replace')
            if mode==b'120000':findings.append({'file':label,'reason':'git_symlink_not_allowed'})
            blobs[oid.decode()]=label
        hist=git(root,'rev-list','--all','--objects')
        if hist.returncode: raise RuntimeError('Cannot inspect Git history')
        for line in hist.stdout.decode('utf-8','replace').splitlines():
            oid,_,name=line.partition(' ')
            kind=git(root,'cat-file','-t',oid)
            if kind.returncode: raise RuntimeError('Cannot read Git object')
            if kind.stdout.strip()==b'blob':blobs.setdefault(oid,'history:'+name)
            elif kind.stdout.strip() in (b'commit',b'tag'):
                obj=git(root,'cat-file','-p',oid)
                # Exclude Git identity headers; scan user-written messages.
                message=obj.stdout.partition(b'\n\n')[2]
                inspect('git-message:'+oid[:12],message)
        for oid,label in blobs.items():
            obj=git(root,'cat-file','blob',oid)
            if obj.returncode:raise RuntimeError('Cannot read Git blob')
            name=label.split(':',1)[1]
            if Path(name).suffix not in TEXT_EXT and Path(name).name not in ('.gitignore','.gitattributes'):
                findings.append({'file':label,'reason':'unexpected_git_file_type'})
            inspect(label,obj.stdout)
    return {'ok':not findings,'mode':'private_evidence_scan' if denylist and evidence_dir else 'basic_scan_only',
            'findings':findings,'manual_review_required':True,
            'limitations':'词表和长片段扫描不能识别全部改写、短引用或组合身份线索。'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=DEFAULT_ROOT)
    p.add_argument('--denylist',type=Path)
    p.add_argument('--evidence-dir',type=Path)
    a=p.parse_args()
    result=scan(a.root,a.denylist,a.evidence_dir)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(not result['ok'])
