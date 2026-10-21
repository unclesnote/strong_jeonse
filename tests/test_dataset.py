"""Contract checks and add-only site writes using an isolated, different-size fixture."""
from pathlib import Path
import copy, importlib.util, json, shutil, tempfile, unittest
from unittest import mock

PROJECT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('notice_dataset',PROJECT/'scripts/dataset.py')
ds=importlib.util.module_from_spec(spec);spec.loader.exec_module(ds)
FIXTURE=PROJECT/'tests/fixtures/tiny-bundle'

class DatasetContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.bundle=self.root/'different-source-bundle';shutil.copytree(FIXTURE,self.bundle)
        self.data=ds.read_json(self.bundle/'dataset.json')
        self.path=self.bundle/'dataset.json';self.dist=self.root/'site';self.state=self.root/'config'
    def tearDown(self):self.temp.cleanup()
    def save(self,data=None):self.path.write_bytes(ds.encode_json(self.data if data is None else data))
    def active(self):return ds.activate(self.path,self.bundle,self.dist,self.state)
    def site_files(self):
        return {str(p.relative_to(self.root)):ds.digest(p) for parent in (self.dist,self.state) if parent.exists() for p in parent.rglob('*') if p.is_file()}
    def assert_no_site(self):
        # A failed write must not leave anything that looks like a site or its state.
        self.assertEqual({},self.site_files())
    def test_fixture_different_counts_and_original_images(self):
        report=ds.validate(self.data,self.bundle)
        self.assertEqual((report['units'],report['buildings'],report['groups'],report['media'],report['previewPages']),(2,2,1,3,4))
        self.assertEqual({m['type'] for m in self.data['media']},{'pdf','jpg','png'})
        runtime=ds.compile_runtime(self.data)
        self.assertIsNone(runtime['buildings'][1]['units'][0]['area']);self.assertIsNone(runtime['buildings'][1]['units'][0]['elevator'])
        self.assertIsNone(runtime['buildings'][1]['elevator'])
        self.assertEqual(runtime['buildings'][0]['units'][0]['id'],1001)
        self.assertEqual(runtime['buildings'][1]['units'][0]['rawFields']['I'],'')
    def test_binding_scopes_and_many_to_many(self):
        runtime=ds.compile_runtime(self.data);b1,b2=runtime['buildings']
        jpg=next(m for m in b1['media'] if m['type']=='jpg')
        self.assertEqual({r['targetType'] for r in jpg['bindings']},{'unit','group'})
        self.assertEqual(next(r['originalUnitId'] for r in jpg['bindings'] if r['targetType']=='unit'),1001)
        png=next(m for m in b2['media'] if m['type']=='png')
        self.assertEqual(len(png['bindings']),1);self.assertEqual(png['bindings'][0]['originalUnitId'],1002)
        self.assertNotIn('png',[m['type'] for m in b1['media']])
    def test_same_media_target_different_roles_are_preserved_in_one_card(self):
        relation=copy.deepcopy(self.data['relations'][0]);relation['role']='floorplan'
        relation['id']=ds.stable(self.data['notice']['id'],'relation',relation['mediaId'],relation['targetType'],relation['targetId'],relation['role'])
        self.data['relations'].append(relation);ds.validate(self.data,self.bundle)
        runtime=ds.compile_runtime(self.data)
        for building in runtime['buildings']:
            cards=[m for m in building['media'] if m['type']=='pdf']
            self.assertEqual(len(cards),1)
            self.assertEqual({r['role'] for r in cards[0]['bindings']},{'brochure','floorplan'})
    def test_stable_id_cli(self):
        import contextlib,io
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            status=ds.main(['ids','--notice-id','fixture-mini','--kind','unit','--values-json',json.dumps(['테스트 주택군','원문 주소',1001],ensure_ascii=False)])
        self.assertEqual(status,0)
        self.assertEqual(json.loads(out.getvalue())['id'],ds.stable('fixture-mini','unit','테스트 주택군','원문 주소',1001))
    def test_array_reordering_preserves_stable_ids(self):
        changed=copy.deepcopy(self.data)
        for key in ('units','buildings','groups','media','relations'):changed[key].reverse()
        ds.validate(changed,self.bundle)
        self.assertEqual({b['id'] for b in changed['buildings']},{b['id'] for b in self.data['buildings']})
    def test_invalid_inputs_leave_no_site(self):
        def foreign(d):d['relations'][0]['targetId']='fixture-mini:group:missing'
        def parent(d):d['media'][0]['preview']['pages'][0]['derivedFromMediaId']=d['media'][1]['id']
        def missing(d):d['media'][0]['original']['url']='assets/files/not-present.pdf'
        def version(d):d['schemaVersion']='99.0.0'
        def duplicate(d):d['groups'].append(copy.deepcopy(d['groups'][0]))
        def unsafe(d):d['media'][0]['original']['url']='assets/../../private.pdf'
        def encoded(d):d['media'][0]['original']['url']='assets/%2e%2e/private.pdf'
        def checksum(d):d['media'][0]['original']['sha256']='0'*64
        def page_order(d):d['media'][0]['preview']['pages'][0]['pageNumber']=2
        def duplicate_relation(d):
            r=copy.deepcopy(d['relations'][0]);r['id']+='-duplicate';d['relations'].append(r)
        def numeric(d):d['units'][0]['area']='77'
        def unit_group(d):d['units'][0]['group']='wrong'
        def partial_pdf(d):d['media'][0]['preview']['pages'].pop();d['media'][0]['preview']['pageCount']=1
        def bad_dimensions(d):d['media'][0]['preview']['pages'][0]['width']=999
        for mutation in (foreign,parent,missing,version,duplicate,unsafe,encoded,checksum,page_order,duplicate_relation,numeric,unit_group,partial_pdf,bad_dimensions):
            with self.subTest(mutation=mutation.__name__):
                changed=copy.deepcopy(self.data);mutation(changed);self.save(changed)
                with self.assertRaises((ds.DatasetError,ValueError)):self.active()
                self.assert_no_site()
    def test_new_site_written_once_and_never_replaced(self):
        result=ds.activate(self.path,self.bundle,self.dist,self.state,dry_run=True)
        self.assertTrue(result['dryRun']);self.assertFalse(self.dist.exists());self.assertFalse(self.state.exists())
        result=self.active();prefix=result['assetPrefix']
        for url in ds.asset_urls(self.data):self.assertEqual(ds.digest(self.bundle/url),ds.digest(self.dist/prefix/url))
        payload=(self.dist/'data.js').read_text();self.assertIn(prefix+'assets/files/document.pdf',payload)
        self.assertEqual(ds.read_json(self.dist/'competition-config.json')['id'],'fixture-mini')
        config=ds.read_json(self.state/'active-dataset.json');self.assertEqual(config['noticeId'],'fixture-mini')
        before=self.site_files()
        self.data['notice']['title']='다른 공고 데이터';self.save()
        with self.assertRaisesRegex(ds.DatasetError,'already has data'):self.active()
        self.assertEqual(before,self.site_files())
        self.assertEqual(ds.main(['activate','--dataset',str(self.path),'--asset-root',str(self.bundle),'--dist',str(self.dist),'--state-dir',str(self.state)]),1)
        self.assertEqual(before,self.site_files())
    def test_copy_failure_leaves_no_site(self):
        with mock.patch.object(ds,'copy_assets',side_effect=OSError('simulated unavailable source disk')):
            with self.assertRaises(OSError):self.active()
        self.assert_no_site()
    def test_last_write_failure_leaves_no_site(self):
        original=ds.atomic_write
        def flaky(path,content):
            if Path(path)==self.dist/'data.js':raise OSError('simulated data.js write failure')
            return original(path,content)
        with mock.patch.object(ds,'atomic_write',side_effect=flaky):
            with self.assertRaises(OSError):self.active()
        self.assert_no_site()
    def test_build_is_isolated_and_rejects_existing_output(self):
        output=self.root/'build';ds.build(self.path,self.bundle,output)
        self.assertTrue((output/'data.js').is_file());self.assertFalse(self.dist.exists())
        with self.assertRaises(ds.DatasetError):ds.build(self.path,self.bundle,output)

if __name__=='__main__':unittest.main()
