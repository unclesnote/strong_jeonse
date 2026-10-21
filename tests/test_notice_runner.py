"""Observable guarantees of the project-local skill: isolation and ID checks."""
import hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
RUNNER=ROOT/'.agents/skills/lh-notice-map/scripts/build_notice.py'

class NoticeRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.bundle=self.root/'bundle';shutil.copytree(ROOT/'tests/fixtures/tiny-bundle',self.bundle)
        p=self.bundle/'dataset.json';p.write_text(p.read_text().replace('fixture-mini','123456789010'))
        self.before=self.hashes(self.bundle);self.runs=self.root/'runs';self.runs.mkdir()
        self.sentinel=self.runs/'previous-site.txt';self.sentinel.write_text('keep previous site')
    def tearDown(self):self.temp.cleanup()
    def hashes(self,root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
    def run_build(self,url,*args):
        return subprocess.run([sys.executable,str(RUNNER),url,'--runs-dir',str(self.runs),'--no-install',*map(str,args)],capture_output=True,text=True)
    def reports(self):return [json.loads(p.read_text()) for p in self.runs.glob('*/reports/run.json')]
    def test_same_notice_twice_creates_independent_runs_without_mutating_input(self):
        url='https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId=123456789010'
        for _ in range(2):
            result=self.run_build(url,'--from-bundle',self.bundle);self.assertEqual(result.returncode,0,result.stderr)
        reports=self.reports();self.assertEqual(len(reports),2)
        self.assertEqual(len({r['runRoot'] for r in reports}),2)
        for report in reports:
            self.assertEqual(report['status'],'complete');self.assertEqual(report['validation']['units'],2)
            run=Path(report['runRoot'])
            for folder in ['docs','scripts','config','data','site','reports','tmp']:self.assertTrue((run/folder).is_dir())
            self.assertTrue((run/'site/dist/index.html').is_file());self.assertTrue((run/'site/dist/data.js').is_file())
            self.assertFalse((run/'.git').exists());self.assertFalse((run/'.openai').exists())
            self.assertFalse((run/'site/.openai').exists())
        self.assertEqual(self.hashes(self.bundle),self.before);self.assertEqual(self.sentinel.read_text(),'keep previous site')
    def test_bare_url_requires_browser_without_selecting_old_notice(self):
        result=self.run_build('https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do')
        self.assertEqual(result.returncode,2);report=self.reports()[0]
        self.assertEqual(report['status'],'needs_browser');self.assertIsNone(report['noticeId'])
        self.assertFalse((Path(report['runRoot'])/'site/dist/data.js').exists())
    def test_wrong_notice_bundle_fails_and_keeps_previous_run(self):
        result=self.run_build('https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId=999999999999','--from-bundle',self.bundle)
        self.assertEqual(result.returncode,1);self.assertEqual(self.reports()[0]['status'],'failed')
        self.assertEqual(self.sentinel.read_text(),'keep previous site');self.assertEqual(self.hashes(self.bundle),self.before)

if __name__=='__main__':unittest.main()
