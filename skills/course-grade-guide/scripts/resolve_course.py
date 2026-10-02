"""Resolve an offering without guessing a year, teacher or assignment. No private data."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

DEFAULT_CATALOG = Path(__file__).resolve().parents[1]/'courses'/'catalog.json'


def resolve(catalog, course, year=None, teacher=None, semester=None, section=None, assignment=None):
    matches = [c for c in catalog['courses'] if course in [c['course_id'], c['name'], *c.get('aliases',[])]]
    if not matches:
        return {'status':'unknown_course','mode':'general','general_path':'general/guide.md',
                'message':'暂无这门课的独立数据；使用全课程汇总的 general 分析，结合本次要求继续评价，不代表该课教师偏好。','candidates':[]}
    candidates = []
    for c in matches:
        for o in c['offerings']:
            if year is not None and o['academic_year'] != year: continue
            if teacher is not None and teacher not in o['teacher_ids']: continue
            # Unknown metadata is not a wildcard for a confirmed match.
            if semester is not None and o.get('semester') not in (None,semester): continue
            if section is not None and o.get('section') not in (None,section): continue
            candidates.append({'course_id':c['course_id'],'course_name':c['name'],
                               'course_path':c['path'], **o})
    if not candidates:
        return {'status':'no_matching_offering','mode':'general','general_path':'general/guide.md',
                'message':'暂无本批次独立数据；使用 general 分析继续帮助，不沿用旧教师；结合本次要求与任课信息更新。','candidates':[]}
    if year is None or len(candidates)!=1:
        return {'status':'needs_clarification','mode':'general_pending_clarification','general_path':'general/guide.md',
                'message':'请确定学年及必要的教师／班级，不能默认最新批次；期间先用 general 分析。','candidates':candidates}
    chosen=candidates[0]
    if ((semester is not None and chosen.get('semester') is None) or
        (section is not None and chosen.get('section') is None)):
        return {'status':'needs_clarification','message':'资料中该学期或班级未知，请核对是否为同一批次。','candidates':candidates}
    assigned=chosen['assignments']
    if assignment is not None:
        assigned=[a for a in assigned if assignment in (a['assignment_id'],a['name'])]
    if len(assigned)!=1:
        return {'status':'needs_assignment','message':'请指定本批次中对应的作业。','candidates':candidates}
    tpaths={t['teacher_id']:t['path'] for t in catalog['teachers']}
    return {'status':'resolved','offering':chosen,'assignment':assigned[0],
            'teacher_paths':[tpaths[t] for t in chosen['teacher_ids']],
            'grading_teacher':'unknown_unless_explicitly_confirmed',
            'requirements_status':chosen.get('requirements_status','historical'),
            'message':'先读课程中对应作业，再读任课代号档案；本次要求优先。'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalog',type=Path,default=DEFAULT_CATALOG)
    p.add_argument('--course',required=True)
    p.add_argument('--year')
    p.add_argument('--teacher')
    p.add_argument('--semester',type=int)
    p.add_argument('--section')
    p.add_argument('--assignment')
    a=p.parse_args()
    catalog=json.loads(a.catalog.read_text(encoding='utf-8'))
    print(json.dumps(resolve(catalog,a.course,a.year,a.teacher,a.semester,a.section,a.assignment),ensure_ascii=False,indent=2))


if __name__=='__main__': main()
