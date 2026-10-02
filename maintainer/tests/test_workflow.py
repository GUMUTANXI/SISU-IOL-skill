import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[2]

def module(name,rel):
    spec=importlib.util.spec_from_file_location(name,ROOT/rel)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

resolver=module('resolver','skills/course-grade-guide/scripts/resolve_course.py')
release=module('release','maintainer/release_check.py')
extract=module('extract','maintainer/extract_case.py')
contribution=module('contribution','maintainer/check_contribution.py')
validator=module('validator','maintainer/validate.py')

class Routing(unittest.TestCase):
    def setUp(self):
        self.cat=json.loads((ROOT/'skills/course-grade-guide/courses/catalog.json').read_text(encoding='utf-8'))

    def test_current_assignments(self):
        for c in self.cat['courses']:
            for o in c['offerings']:
                for a in o['assignments']:
                    r=resolver.resolve(self.cat,c['name'],o['academic_year'],assignment=a['assignment_id'])
                    self.assertEqual(r['status'],'resolved')
                    self.assertEqual(r['offering']['teacher_ids'],o['teacher_ids'])

    def test_year_required_even_if_one_historical_offering(self):
        self.assertEqual(resolver.resolve(self.cat,'形态学')['status'],'needs_clarification')

    def test_changed_teacher_across_years(self):
        c=self.cat['courses'][0];new=copy.deepcopy(c['offerings'][0]);new.update(academic_year='2027-2028',offering_id='synthetic-new',teacher_ids=['T007'])
        c['offerings'].append(new)
        self.assertEqual(resolver.resolve(self.cat,c['name'],'2027-2028')['offering']['teacher_ids'],['T007'])
        self.assertEqual(resolver.resolve(self.cat,c['name'],'2024-2025')['offering']['teacher_ids'],['T001'])
        self.assertEqual(resolver.resolve(self.cat,c['name'],'2028-2029')['status'],'no_matching_offering')

    def test_same_year_different_sections(self):
        c=self.cat['courses'][0];c['offerings'][0]['section']='甲班'
        new=copy.deepcopy(c['offerings'][0]);new.update(offering_id='synthetic-section',section='乙班',teacher_ids=['T007']);c['offerings'].append(new)
        self.assertEqual(resolver.resolve(self.cat,c['name'],'2024-2025')['status'],'needs_clarification')
        self.assertEqual(resolver.resolve(self.cat,c['name'],'2024-2025',section='乙班')['offering']['teacher_ids'],['T007'])

    def test_unknown_section_not_confirmed(self):
        self.assertEqual(resolver.resolve(self.cat,'形态学','2024-2025',section='乙班')['status'],'needs_clarification')

    def test_wrong_teacher_and_multiple_assignments(self):
        self.assertEqual(resolver.resolve(self.cat,'形态学','2024-2025',teacher='T007')['status'],'no_matching_offering')
        self.assertEqual(resolver.resolve(self.cat,'心理语言学研究方法','2025-2026')['status'],'needs_assignment')

    def test_alias_and_multiple_teachers(self):
        r=resolver.resolve(self.cat,'语言与社会研究经典导读','2025-2026')
        self.assertEqual(r['offering']['course_id'],'C007')
        self.cat['courses'][0]['offerings'][0]['teacher_ids']=['T001','T007']
        r=resolver.resolve(self.cat,'形态学','2024-2025')
        self.assertEqual(len(r['teacher_paths']),2)
        self.assertEqual(r['grading_teacher'],'unknown_unless_explicitly_confirmed')

class Privacy(unittest.TestCase):
    def test_identity_and_contact(self):
        self.assertIn('private_identity_or_title',release.check_text('内部人名测试甲',['内部人名测试甲']))
        email='someone'+'@'+'example.invalid'
        self.assertIn('email_address',release.check_text(email))

    def test_personal_score_vs_rubric(self):
        self.assertIn('personal_grade',release.check_text('个人成绩：'+'87.25'))
        self.assertEqual(release.check_text('题目一 20分；参考文献不少于15条；90及以上是历史档位。'),[])

    def test_source_overlap(self):
        source='这是一段仅用于测试的合成来源文字，其目的在于检查跨越空白的重复片段是否会被检测，而不是引用任何真实学生论文。'
        s=release.normalized(source);windows={s[i:i+release.WINDOW] for i in range(len(s)-release.WINDOW+1)}
        self.assertIn('source_excerpt_overlap',release.check_text(source,windows=windows))

    def test_git_history_and_index_are_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'repo';root.mkdir()
            def git(*args):return subprocess.run(['git','-C',str(root),*args],capture_output=True,check=True)
            git('init','-q');p=root/'note.md';p.write_text('合成私密身份甲',encoding='utf-8')
            git('add','note.md');git('-c','user.name=Test','-c','user.email='+'test'+'@'+'example.invalid','commit','-qm','synthetic fixture')
            p.write_text('safe',encoding='utf-8')
            deny=Path(tmp)/'deny.json';deny.write_text(json.dumps({'tokens':['合成私密身份甲']}),encoding='utf-8')
            result=release.scan(root,deny)
            self.assertFalse(result['ok']);self.assertTrue(any(f['file'].startswith(('index:','history:')) for f in result['findings']))

class Intake(unittest.TestCase):
    def package(self,root):
        data=json.loads((ROOT/'maintainer/contribution-template.json').read_text(encoding='utf-8'))
        (root/'paper.docx').write_bytes(b'synthetic')
        data.update(course={'name':'合成课程','academic_year':'2027-2028'},teacher={'known_code':'T001'},assignment={'type':'essay'},
          files={'paper':'paper.docx'},version={'is_the_graded_version':True},
          permission={'right_to_submit':True,'private_analysis':True,'publish_abstract_rules':True},
          grade={'value':81,'scope':'assignment','maximum':100})
        return data

    def test_total_never_becomes_assignment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);d=self.package(root)
            self.assertTrue(contribution.validate_contribution(d,root)['eligible_for_single_paper_comparison'])
            d['grade']['scope']='course_total'
            r=contribution.validate_contribution(d,root)
            self.assertEqual(r['status'],'course_total_only');self.assertFalse(r['eligible_for_single_paper_comparison'])

    def test_missing_grade_and_wrong_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);d=self.package(root);d['grade'].update(value=None,scope='unknown')
            self.assertFalse(contribution.validate_contribution(d,root)['eligible_for_single_paper_comparison'])
            d['version']['is_the_graded_version']=False
            self.assertFalse(contribution.validate_contribution(d,root)['ok'])

    def test_package_cannot_reference_external_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);d=self.package(root);d['files']['paper']='../outside.docx'
            self.assertIn('path_outside_package',contribution.validate_contribution(d,root)['errors'])

    def test_component_needs_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);d=self.package(root);d['grade']['scope']='component'
            self.assertIn('grade_targets_required',contribution.validate_contribution(d,root)['errors'])

    def test_comments_revisions_and_duplicates(self):
        w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        body=f'<w:document xmlns:w="{w}"><w:body><w:p><w:commentRangeStart w:id="0"/><w:r><w:t>原文</w:t></w:r><w:del w:author="Reviewer"><w:r><w:delText>旧词</w:delText></w:r></w:del><w:ins w:author="Reviewer"><w:r><w:t>新词</w:t></w:r></w:ins><w:commentRangeEnd w:id="0"/></w:p></w:body></w:document>'
        comments=f'<w:comments xmlns:w="{w}"><w:comment w:id="0" w:author="Reviewer"><w:p><w:r><w:t>解释概念</w:t></w:r></w:p></w:comment></w:comments>'
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'in';source.mkdir();p=source/'one.docx'
            with ZipFile(p,'w') as z:z.writestr('word/document.xml',body);z.writestr('word/comments.xml',comments)
            d=extract.extract_docx(p)
            self.assertEqual(d['blocks'][0]['text'],'原文新词')
            self.assertEqual(d['blocks'][0]['before_tracked_changes'],'原文旧词')
            self.assertEqual(d['comments'][0]['anchors'],['body:p1'])
            (source/'two.docx').write_bytes(p.read_bytes())
            records=extract.extract_directory(source,Path(tmp)/'out')
            self.assertEqual(len(records),2);self.assertIsNotNone(records[1]['duplicate_of'])
            self.assertEqual(records[0]['sha256'],records[1]['sha256'])

    def test_private_output_cannot_be_public(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):extract.extract_directory(tmp,ROOT/'evidence')

class PublicPackage(unittest.TestCase):
    def test_links_and_relationships(self):
        self.assertEqual(validator.validate(ROOT),[])

    def test_standalone_resolver_needs_no_private_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            import shutil
            path=Path(tmp)/'skill';shutil.copytree(ROOT/'skills/course-grade-guide',path,ignore=shutil.ignore_patterns('__pycache__'))
            r=subprocess.run([sys.executable,'-X','utf8',str(path/'scripts/resolve_course.py'),'--course','逻辑学','--year','2025-2026'],capture_output=True,check=True)
            self.assertEqual(json.loads(r.stdout)['status'],'resolved')

if __name__=='__main__':unittest.main()
