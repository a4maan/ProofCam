import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
from benchmark import harness as h
from benchmark.corpus import split_for


class HarnessTests(unittest.TestCase):
    def setUp(self):
        y,x=np.mgrid[:96,:128]
        self.image=Image.fromarray(np.stack([x*2,y*2,(x+y)%256],axis=-1).astype('uint8'))
        self.data=h.jpeg(self.image)

    def cases(self, kind='watermarked_candidate', count=2):
        return [{'case_id':str(i),'source_id':str(i),'transform':'original','device':'test',
                 'kind':kind,'expected_id':'a'*32 if kind=='watermarked_candidate' else None} for i in range(count)]

    def pred(self, case_id='0', ids=None, detected=False, status='ok', complete=True):
        return {'case_id':case_id,'decoded_ids':ids or [],'detected':detected,
                'status':status,'search_complete':complete,'elapsed_ms':5}

    def test_metadata_strip_preserves_pixels_and_changes_bytes(self):
        comment=b'example metadata'
        data=self.data[:2]+b'\xff\xfe'+(len(comment)+2).to_bytes(2,'big')+comment+self.data[2:]
        stripped=h.strip_metadata(data)
        self.assertEqual(stripped,self.data)
        self.assertNotEqual(h.digest(data),h.digest(stripped))
        self.assertEqual(h.pixel_hash(h.decode(data)),h.pixel_hash(h.decode(stripped)))

    def test_metadata_parser_rejects_truncation(self):
        for data in [b'bad',b'\xff\xd8\xff',b'\xff\xd8\xff\xe1\x00\x10abc']:
            with self.assertRaises(ValueError):h.strip_metadata(data)

    def test_transform_determinism_and_bounds(self):
        for name in h.transforms():
            with self.subTest(name=name):
                a,ext=h.transform(self.data,name);b,_=h.transform(self.data,name)
                self.assertEqual(a,b);self.assertIn(ext,('png','jpg'))
                self.assertGreater(min(h.decode(a).size),0)
        self.assertEqual(h.resize(self.image,2048).size,self.image.size)
        cropped=h.crop(self.image,.75,'br')
        self.assertAlmostEqual(cropped.width*cropped.height/(128*96),.75,delta=.02)
        self.assertEqual(h.decode(h.transform(self.data,'rotate_90')[0]).size,(96,128))

    def test_synthetic_screen_is_distinct(self):
        synthetic=h.decode(h.transform(self.data,'synthetic_screenshot_1024')[0])
        self.assertEqual(synthetic.size,(176,216))
        self.assertNotEqual(h.pixel_hash(synthetic),h.pixel_hash(self.image))

    def test_quality_equal_and_changed(self):
        self.assertAlmostEqual(h.quality(self.image,self.image)['ssim_rgb_gaussian11'],1)
        other=Image.new('RGB',self.image.size,'white')
        self.assertLess(h.quality(self.image,other)['ssim_rgb_gaussian11'],.9)
        with self.assertRaises(ValueError):h.quality(self.image,Image.new('RGB',(16,16)))

    def test_full_id_and_missing_denominator(self):
        result=h.score(self.cases(),[self.pred(ids=['a'*32],detected=True)])['buckets'][0]
        self.assertEqual(result['n'],2);self.assertEqual(result['correct_id'],1)
        self.assertEqual(result['recovery_rate'],.5);self.assertEqual(result['missing_or_error'],1)

    def test_wrong_id_and_ambiguous_not_success(self):
        result=h.score(self.cases(count=1),[self.pred(ids=['a'*32,'b'*32],detected=True)])['buckets'][0]
        self.assertEqual(result['correct_id'],0);self.assertEqual(result['wrong_id'],1)

    def test_negative_bound_requires_complete_search(self):
        cases=self.cases('negative_candidate')
        incomplete=h.score(cases,[self.pred()])['buckets'][0]
        self.assertIsNone(incomplete['zero_detection_upper95'])
        complete=h.score(cases,[self.pred(),self.pred('1')])['buckets'][0]
        self.assertAlmostEqual(complete['zero_detection_upper95'],1-.05**.5)
        self.assertAlmostEqual(h.zero_upper(300000),.0000099857,places=9)

    def test_false_detection_without_decoded_id(self):
        result=h.score(self.cases('negative_candidate',1),[self.pred(detected=True)])['buckets'][0]
        self.assertEqual(result['detected'],1);self.assertEqual(result['wrong_id'],0)
        self.assertIsNone(result['zero_detection_upper95'])

    def test_invalid_prediction_and_case_rejected(self):
        for changes in [{'case_id':'unknown'},{'decoded_ids':['abc']},{'elapsed_ms':float('nan')},
                        {'decoded_ids':['a'*32],'detected':False},{'search_complete':False},
                        {'detected':'false'}]:
            p=self.pred();p.update(changes)
            with self.assertRaises(ValueError):h.score(self.cases(),[p])
        with self.assertRaises(ValueError):h.score(self.cases(),[self.pred(),self.pred()])
        c=self.cases();c[0]['expected_id']='bad'
        with self.assertRaises(ValueError):h.score(c,[])

    def test_error_never_success(self):
        b=h.score(self.cases(count=1),[self.pred(ids=['a'*32],detected=True,status='timeout',complete=False)])['buckets'][0]
        self.assertEqual(b['correct_id'],0);self.assertEqual(b['missing_or_error'],1)

    def test_buckets_keep_devices_and_transforms_separate(self):
        c=self.cases(count=3);c[1]['device']='phone-b';c[2]['transform']='jpeg_q70'
        self.assertEqual(len(h.score(c,[])['buckets']),3)

    def test_size_buckets_are_separate(self):
        c=self.cases();c[0]['size_bucket']='below-512';c[1]['size_bucket']='1024+'
        self.assertEqual(len(h.score(c,[])['buckets']),2)

    def test_end_to_end_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'data').mkdir()
            source=root/'data/source.jpg';source.write_bytes(self.data)
            manifest=root/'inputs.jsonl'
            record={'id':'fixture','source_group':'test-source','split':'tuning',
                    'sha256':h.digest(self.data),'pixel_sha256':h.pixel_hash(h.decode(self.data)),
                    'license':'test-generated','review_status':'approved','path':'data/source.jpg',
                    'device':'generated-fixture'}
            manifest.write_text(json.dumps(record)+'\n')
            h.dump(manifest.with_suffix('.lock.json'),{'manifest_sha256':h.digest(manifest.read_bytes())})
            args=type('Args',(),{'manifest':str(manifest),'split':'tuning','allow_heldout':False,
                                'limit':0,'out':str(root/'run'),'exports':None,'device':'unit-test'})()
            with patch.object(h,'ROOT',root):h.build(args)
            rows=h.jsonl(root/'run/cases.jsonl')
            self.assertEqual(len(rows),29)
            self.assertTrue(all(r['expected_id'] is None for r in rows))
            self.assertTrue(all(r['device']=='unit-test' for r in rows))
            for r in rows:self.assertEqual(h.digest((root/'run'/r['path']).read_bytes()),r['sha256'])
            with patch.object(h,'ROOT',root):
                with self.assertRaises(FileExistsError):h.build(args)

    def test_duplicate_asset_ids_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manifest=root/'manifest.jsonl';exports=root/'exports.jsonl'
            manifest.write_text(json.dumps({'id':'source-a','split':'tuning'})+'\n')
            exports.write_text(''.join(json.dumps({'source_id':s,'expected_id':'a'*32})+'\n' for s in ['source-a','source-b']))
            args=type('Args',(),{'manifest':str(manifest),'split':'tuning','allow_heldout':False,
                                'limit':0,'out':str(root/'run'),'exports':str(exports),'device':'unit-test'})()
            with patch.object(h,'audit',return_value={}):
                with self.assertRaisesRegex(ValueError,'unique identifier'):h.build(args)

    def test_split_deterministic(self):
        for group in ['author-a','author-b','author-c']:
            self.assertEqual(split_for(group),split_for(group))
            self.assertIn(split_for(group),('tuning','heldout','negative'))

    def test_audit_detects_manifest_changes_duplicates_and_leakage(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'manifest.jsonl'
            base={'id':'a','source_group':'author-a','split':'tuning','sha256':'1','pixel_sha256':'p1',
                  'license':'test','review_status':'unreviewed','path':'data/a.jpg'}
            def write(rows):
                path.write_text(''.join(json.dumps(x)+'\n' for x in rows))
                h.dump(path.with_suffix('.lock.json'),{'manifest_sha256':h.digest(path.read_bytes())})
            write([base]);self.assertFalse(h.audit(path,False)['release_ready'])
            path.write_text(path.read_text()+'\n')
            with self.assertRaisesRegex(ValueError,'lock mismatch'):h.audit(path,False)
            write([base,base])
            with self.assertRaisesRegex(ValueError,'duplicate'):h.audit(path,False)
            second=copy.deepcopy(base);second.update(id='b',sha256='2',pixel_sha256='p2',split='heldout')
            write([base,second])
            with self.assertRaisesRegex(ValueError,'leakage'):h.audit(path,False)
            write([base])
            with patch.object(h,'safe_media_path',return_value=path):
                with self.assertRaisesRegex(ValueError,'content lock mismatch'):h.audit(path)

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):h.safe_media_path('../README.md')

    def test_heldout_build_requires_explicit_opt_in(self):
        with patch.object(h,'audit',return_value={}):
            args=type('Args',(),{'manifest':'unused','split':'heldout','allow_heldout':False})()
            with self.assertRaisesRegex(ValueError,'reserved'):h.build(args)

    def test_pixel_hash_binds_dimensions(self):
        a=Image.new('RGB',(12,24));b=Image.new('RGB',(24,12))
        self.assertEqual(a.tobytes(),b.tobytes())
        self.assertNotEqual(h.pixel_hash(a),h.pixel_hash(b))


if __name__=='__main__':unittest.main()
