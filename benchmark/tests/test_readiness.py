import argparse
import copy
import hashlib
import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
from benchmark import harness as h, negative_suite as n, review, screenshots, expand, coverage


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        y,x=np.mgrid[:96,:128]
        self.image=Image.fromarray(np.stack([x*2,y*2,(x+y)%256],axis=-1).astype('uint8'))
        self.data=h.jpeg(self.image)

    def test_negative_operations_are_30_unique_reproducible(self):
        self.assertEqual(len(n.operations()),30);self.assertEqual(len(set(n.operations())),30)
        for operation in n.operations():
            with self.subTest(operation=operation):
                self.assertEqual(n.transform(self.data,operation),n.transform(self.data,operation))

    def test_same_image_fingerprints_and_pair_flag(self):
        d,p=review.fingerprints(self.image)
        self.assertEqual((d,p),review.fingerprints(self.image.copy()))
        rows=[dict(id='a',source_id='one',split='tuning',dhash=d,phash=p),dict(id='b',source_id='two',split='heldout',dhash=d,phash=p)]
        result=review.candidate_pairs(rows)
        self.assertEqual(len(result),1);self.assertTrue(result[0]['cross_split'])
        self.assertIn('unreviewed',result[0]['review_status'])
        rows[1]['source_id']='one';self.assertEqual(review.candidate_pairs(rows),[])

    def test_cdn_url_allowlist(self):
        self.assertEqual(expand.validate_cdn_url('https://farm1.staticflickr.com/a.jpg'),'https://farm1.staticflickr.com/a.jpg')
        for value in ['http://farm1.staticflickr.com/a.jpg','https://staticflickr.com.evil.invalid/a.jpg',
                      'https://user:password@farm1.staticflickr.com/a.jpg','https://farm1.staticflickr.com:444/a.jpg','file:///tmp/a.jpg']:
            with self.assertRaises(ValueError):expand.validate_cdn_url(value)

    def test_original_requires_version_match_and_native_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'data/originals').mkdir(parents=True)
            (root/'data/originals/abc.jpg').write_bytes(self.data)
            item={'source_id':'abc','id':'oi-abc'}
            meta={'OriginalURL':'https://farm1.staticflickr.com/a.jpg','OriginalMD5':base64.b64encode(hashlib.md5(self.data,usedforsecurity=False).digest()).decode()}
            with patch.object(expand,'ROOT',root):
                with self.assertRaisesRegex(ValueError,'below_native'):expand.original(item,meta)
                meta['OriginalMD5']=base64.b64encode(b'x'*16).decode()
                with self.assertRaisesRegex(ValueError,'upstream_bytes'):expand.original(item,meta)

    def fixture_corpus(self,root):
        (root/'data').mkdir();(root/'data/a.jpg').write_bytes(self.data)
        manifest=root/'sources.jsonl'
        row=dict(id='source-a',source_id='a',source_group='author-a',split='negative',path='data/a.jpg',
                 sha256=h.digest(self.data),pixel_sha256=h.pixel_hash(self.image))
        manifest.write_text(json.dumps(row)+'\n');h.dump(manifest.with_suffix('.lock.json'),{'manifest_sha256':h.digest(manifest.read_bytes())})
        return manifest,row

    def test_negative_plan_stream_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manifest,row=self.fixture_corpus(root);plan=root/'plan.json'
            n.create_plan(manifest,plan)
            data=json.loads(plan.read_text());self.assertEqual(data['scheduled_inputs'],30)
            self.assertFalse(data['can_use_scheduled_count_as_independent_N'])
            with patch.object(h,'ROOT',root):
                generated=list(n.iter_inputs(plan,manifest,0,2,'unit-test'))
            self.assertEqual(len(generated),2)
            self.assertTrue(all(x[0]['expected_id'] is None for x in generated))
            data['harness_sha256']='bad';h.dump(plan,data)
            with self.assertRaisesRegex(ValueError,'changed'):n.load_plan(plan,manifest)

    def test_negative_plan_rejects_positive_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manifest,row=self.fixture_corpus(root);row['split']='heldout'
            manifest.write_text(json.dumps(row)+'\n');h.dump(manifest.with_suffix('.lock.json'),{'manifest_sha256':h.digest(manifest.read_bytes())})
            with self.assertRaisesRegex(ValueError,'negative-only'):n.create_plan(manifest,root/'plan.json')

    def screenshot_fixture(self,root):
        (root/'data').mkdir();data=h.png(self.image);(root/'data/screen.png').write_bytes(data)
        row={k:'example' for k in screenshots.REQUIRED}
        row.update(sample_id='sample',parent_source_id='source-a',parent_asset_id='a'*32,split='tuning',
                   media_path='data/screen.png',sha256=h.digest(data),display_scale_percent='100',media_long_edge_pixels='128',
                   region_selection='manual',actual_os_screenshot='true',review_status='approved',
                   media_left='0',media_top='0',media_width='128',media_height='96',evidence_kind='actual_device')
        # Only a validator fixture; never saved as actual device evidence.
        sources=[{'id':'source-a','split':'tuning'}];exports=[{'source_id':'source-a','expected_id':'a'*32}]
        return row,sources,exports,data

    def test_screenshot_import_preserves_full_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);row,sources,exports,data=self.screenshot_fixture(root)
            with patch.object(h,'ROOT',root):result=screenshots.validate_rows([row],sources,exports)
            self.assertEqual(result[0][1],data);self.assertEqual(result[0][3]['width'],128)

    def test_screenshot_rejects_fake_cross_split_bad_rectangle_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);row,sources,exports,_=self.screenshot_fixture(root)
            for changes in [{'evidence_kind':'synthetic'},{'actual_os_screenshot':'false'},{'split':'heldout'},
                            {'parent_asset_id':'b'*32},{'media_width':'9999'},{'sha256':'bad'},
                            {'sample_id':'../escape'},{'review_status':'unreviewed'}]:
                r=dict(row,**changes)
                with self.subTest(changes=changes),patch.object(h,'ROOT',root):
                    with self.assertRaises(ValueError):screenshots.validate_rows([r],sources,exports)

    def test_confidence_not_issued_for_correlated_or_identical_inputs(self):
        cases=[dict(case_id=str(i),source_id='one',source_group='same',sha256=str(i),transform='original',
                    device='test',kind='negative_candidate',expected_id=None) for i in range(2)]
        predictions=[dict(case_id=str(i),status='ok',search_complete=True,detected=False,decoded_ids=[],elapsed_ms=1) for i in range(2)]
        b=h.score(cases,predictions)['buckets'][0]
        self.assertIsNone(b['zero_detection_upper95']);self.assertTrue(b['repeated_sources_or_bytes'])
        cases[1]['source_group']='different';cases[1]['sha256']='0'
        self.assertIsNone(h.score(cases,predictions)['buckets'][0]['zero_detection_upper95'])

    def test_dataset_labels_preserve_unknown_and_reject_conflicting_annotations(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manifest,row=self.fixture_corpus(root)
            classes=root/'classes.csv';classes.write_text(''.join(k+','+v+'\n' for k,v in coverage.CATEGORIES.items()))
            labels=root/'labels.csv';labels.write_text('ImageID,Source,LabelName,Confidence\na,verification,/m/0dzct,1\na,verification,/m/07s6nbt,1\na,crowdsource-verification,/m/07s6nbt,0\n')
            coverage.summarize([manifest],labels,classes,root/'coverage')
            report=json.loads((root/'coverage/summary.json').read_text())
            self.assertEqual(report['counts_by_split']['negative']['faces'],1)
            self.assertEqual(report['counts_by_split']['negative']['text'],0)
            self.assertEqual(len(report['conflicts']),1)
            result=h.jsonl(root/'coverage/labels.jsonl')[0]
            self.assertEqual(result['local_review_status'],'unreviewed')
            self.assertEqual(result['absent_label_means'],'unknown_not_negative')

    def test_review_pages_escape_source_text_and_do_not_auto_approve(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            rows=[dict(id='image-'+str(i),split='tuning',author='<script>bad</script>',title='example',
                       width=128,height=96,heuristic_flags=[]) for i in range(201)]
            review.review_page(rows,root)
            self.assertTrue((root/'page-002.html').exists())
            page=(root/'page-001.html').read_text()
            self.assertEqual(page.count('<article '),200)
            self.assertIn('&lt;script&gt;',page)
            self.assertNotIn('<script>bad',page)
            self.assertIn('<option>unreviewed</option>',page)

    def test_capture_devices_and_selection_modes_not_pooled(self):
        cases=[dict(case_id=str(i),source_id=str(i),transform='actual_screenshot',device='decoder',
                    kind='watermarked_candidate',expected_id='a'*32,capture_device='phone-a',region_selection='manual',display_scale_percent=100) for i in range(3)]
        cases[1]['capture_device']='phone-b';cases[2]['region_selection']='auto'
        self.assertEqual(len(h.score(cases,[])['buckets']),3)


if __name__=='__main__':unittest.main()
