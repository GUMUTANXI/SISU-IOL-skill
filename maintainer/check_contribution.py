"""Validate a PRIVATE contribution package without publishing or editing it."""
import argparse
import json
import math
from pathlib import Path


def validate_contribution(data, package):
    package=Path(package).resolve();errors=[]
    for key in ('name','academic_year'):
        if not data.get('course',{}).get(key):errors.append('missing_course_'+key)
    teacher=data.get('teacher',{})
    if not (teacher.get('known_code') or teacher.get('private_real_name')):errors.append('missing_teacher')
    if not data.get('assignment',{}).get('type'):errors.append('missing_assignment_type')
    version=data.get('version',{})
    if version.get('is_the_graded_version') is not True:errors.append('graded_version_unconfirmed')
    for key in ('right_to_submit','private_analysis'):
        if data.get('permission',{}).get(key) is not True:errors.append('permission_'+key+'_required')
    files=data.get('files',{})
    if not files.get('paper'):errors.append('missing_paper')
    for key,value in files.items():
        values=value if isinstance(value,list) else ([value] if value else [])
        for rel in values:
            path=(package/rel).resolve()
            if package not in path.parents:errors.append('path_outside_package');continue
            if not path.is_file():errors.append('missing_file_'+key)
            if key=='paper' and path.suffix.lower() not in ('.docx','.pdf'):errors.append('unsupported_paper_type')
    grade=data.get('grade',{});value=grade.get('value');maximum=grade.get('maximum')
    scope=grade.get('scope')
    if scope not in ('assignment','component','assignment_group','course_total','unknown'):errors.append('invalid_grade_scope')
    if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0):errors.append('invalid_grade_value')
    if maximum is not None:
        if isinstance(maximum,bool) or not isinstance(maximum,(int,float)) or not math.isfinite(maximum) or maximum<=0:errors.append('invalid_grade_maximum')
        elif isinstance(value,(int,float)) and value>maximum:errors.append('grade_exceeds_maximum')
    if scope in ('component','assignment_group') and not grade.get('components'):errors.append('grade_targets_required')
    status='graded_assignment' if value is not None and scope=='assignment' else ('course_total_only' if value is not None and scope=='course_total' else 'pending_grade_or_scope')
    return {'ok':not errors,'status':status,'eligible_for_single_paper_comparison':not errors and status=='graded_assignment',
            'abstract_publication_allowed':data.get('permission',{}).get('publish_abstract_rules') is True,
            'errors':errors}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest',type=Path);a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    if root in a.manifest.resolve().parents:raise SystemExit('Private contribution must be outside the public repository')
    result=validate_contribution(json.loads(a.manifest.read_text(encoding='utf-8')),a.manifest.parent)
    print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(not result['ok'])
