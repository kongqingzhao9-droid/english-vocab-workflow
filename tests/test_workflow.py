import contextlib
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import vocab
import package_release

PROJECT = Path(__file__).resolve().parents[1]
TEMP_ROOT = PROJECT / '.local/test-runs'
CHAT = '11111111-1111-4111-8111-111111111111'
OWNER = '22222222-2222-4222-8222-222222222222'


def word(name='sustain'):
    return dict(word=name, phonetic='/test/', pos='v.', defEn='To keep something going.',
                meanings=['维持'], usage='sustain interest', example='Regular practice can sustain interest.',
                exampleCn='经常练习能保持兴趣。', prefix='sus-', root='tain', suffix='无',
                synonyms=['maintain'], derivatives=['sustainable'], phrase='sustain interest')


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(vocab, 'ROOT', self.root); self.root_patch.start()
        vocab.local('').mkdir()
        vocab.atomic(vocab.local('config.json'), dict(version=1, pdf_directory=str(self.root / 'OneDrive'),
                     conversation_id=CHAT, supabase_url='https://' + 'a' * 20 + '.supabase.co',
                     public_key='sb_publishable_test_only', owner_id=OWNER))
        (self.root / 'OneDrive').mkdir()
        vocab.save_state(dict(version=1, library={'vocab': [], 'sentences': []}, chat_checkpoint=None, pdf_processed={}))

    def tearDown(self):
        self.root_patch.stop()
        assert self.root.resolve().is_relative_to(TEMP_ROOT.resolve())
        self.temp.cleanup()

    def baseline(self):
        st = vocab.state(); st['chat_checkpoint'] = vocab.checkpoint('2026-10-31T01:00:00Z', 'real-message-start'); vocab.save_state(st)

    def batch(self, entries=None, source=None):
        source = source or dict(kind='chat', conversation_id=CHAT, previous=vocab.state()['chat_checkpoint'],
                               upper=dict(timestamp='2026-10-31T01:01:00Z', id='real-message-upper'), complete=True)
        path = vocab.local('batch.json'); vocab.atomic(path, dict(source=source, vocab=entries or [], sentences=[])); return path

    def test_initial_state_has_no_words_or_history(self):
        self.assertEqual(vocab.state()['library'], {'vocab': [], 'sentences': []})
        self.baseline(); self.assertEqual(vocab.state()['library']['vocab'], [])

    def test_rerunning_init_or_start_cannot_skip_messages(self):
        self.baseline(); before = vocab.local('state.json').read_bytes()
        with patch('sys.argv', ['vocab.py', 'init']): vocab.main()
        self.assertEqual(before, vocab.local('state.json').read_bytes())
        with patch('sys.argv', ['vocab.py', 'record-start', '--timestamp', '2026-11-01T01:00:00Z', '--message-id', 'later']):
            with self.assertRaises(ValueError): vocab.main()
        self.assertEqual(before, vocab.local('state.json').read_bytes())

    def test_commit_and_checkpoint_are_atomic_and_duplicates_preserve_entries(self):
        self.baseline(); vocab.apply_batch(self.batch([word()]))
        old = copy.deepcopy(vocab.state()['library'])
        st = vocab.state(); new = self.batch([word('SUSTAIN')]); data = vocab.read_json(new)
        data['source']['upper'] = dict(timestamp='2026-10-31T01:02:00Z', id='next'); vocab.atomic(new, data)
        vocab.apply_batch(new)
        self.assertEqual(vocab.state()['library'], old)
        self.assertEqual(vocab.state()['chat_checkpoint']['id'], 'next')

    def test_incomplete_and_stale_batches_do_not_advance(self):
        self.baseline(); before = vocab.local('state.json').read_bytes()
        data = vocab.read_json(self.batch([word()])); data['source']['complete'] = False
        vocab.atomic(vocab.local('bad.json'), data)
        with self.assertRaises(ValueError): vocab.apply_batch(vocab.local('bad.json'))
        self.assertEqual(before, vocab.local('state.json').read_bytes())
        data['source']['complete'] = True; data['source']['previous']['id'] = 'stale'
        vocab.atomic(vocab.local('bad.json'), data)
        with self.assertRaises(ValueError): vocab.apply_batch(vocab.local('bad.json'))
        self.assertEqual(before, vocab.local('state.json').read_bytes())

    def test_invalid_word_does_not_advance_checkpoint(self):
        self.baseline(); before = vocab.local('state.json').read_bytes()
        bad = word(); del bad['defEn']
        with self.assertRaises(ValueError): vocab.apply_batch(self.batch([bad]))
        self.assertEqual(before, vocab.local('state.json').read_bytes())

    def test_subsecond_timestamp_is_not_compared_lexically(self):
        self.baseline(); data = vocab.read_json(self.batch())
        data['source']['upper'] = {'timestamp': '2026-10-31T01:00:00.100Z', 'id': 'fractional'}
        vocab.atomic(vocab.local('batch.json'), data); vocab.apply_batch(vocab.local('batch.json'))
        self.assertEqual(vocab.state()['chat_checkpoint']['id'], 'fractional')

    def test_no_baseline_refuses_historical_import(self):
        with self.assertRaises(ValueError): vocab.apply_batch(self.batch([word()]))
        self.assertEqual(vocab.state()['library']['vocab'], [])

    def test_shared_links_and_unreliable_time_are_rejected(self):
        with self.assertRaises(ValueError): vocab.conversation_id('https://chatgpt.com/share/' + CHAT)
        with self.assertRaises(ValueError): vocab.checkpoint('2026-10-31T01:00:00', 'm')
        self.assertEqual(vocab.conversation_id('https://chatgpt.com/c/' + CHAT), CHAT)

    def test_pdf_scan_snapshot_and_change_detection(self):
        path = self.root / 'OneDrive/test.pdf'; path.write_bytes(b'first synthetic PDF')
        with contextlib.redirect_stdout(io.StringIO()): vocab.scan()
        manifest_path = next(vocab.local('batches').glob('*.json')); manifest = vocab.read_json(manifest_path)
        batch = self.batch([word()], dict(kind='pdf', manifest_id=manifest['id'], complete=True))
        path.write_bytes(b'changed while processing')
        with self.assertRaises(ValueError): vocab.apply_batch(batch)
        self.assertEqual(vocab.state()['pdf_processed'], {})
        with contextlib.redirect_stdout(io.StringIO()): vocab.scan()
        manifests = [vocab.read_json(p) for p in vocab.local('batches').glob('*.json')]
        latest = next(m for m in manifests if m['files'][0]['sha256'] != manifest['files'][0]['sha256'])
        vocab.apply_batch(self.batch([word()], dict(kind='pdf', manifest_id=latest['id'], complete=True)))
        with contextlib.redirect_stdout(io.StringIO()): vocab.scan()
        all_scans = [vocab.read_json(p) for p in vocab.local('batches').glob('*.json')]
        self.assertTrue(any(not m['files'] for m in all_scans))

    @unittest.skipUnless(os.name == 'nt', 'DPAPI is Windows-only')
    def test_credential_is_encrypted_and_bound_to_destination(self):
        secret = vocab.credential(create=True)
        self.assertNotIn(secret.encode(), vocab.local('publisher.dpapi').read_bytes())
        self.assertEqual(vocab.credential(), secret)
        c = vocab.config(); c['supabase_url'] = 'https://' + 'b' * 20 + '.supabase.co'; vocab.atomic(vocab.local('config.json'), c)
        with self.assertRaises(ValueError): vocab.credential()

    def test_upload_failure_retains_local_batch_and_does_not_retry(self):
        self.baseline(); vocab.apply_batch(self.batch([word()]))
        before = vocab.local('state.json').read_bytes()
        with patch.object(vocab, 'credential', return_value='test-only'), patch.object(vocab, 'api', side_effect=ValueError('network')) as api:
            with self.assertRaises(ValueError): vocab.publish()
            self.assertEqual(api.call_count, 1)
        self.assertEqual(before, vocab.local('state.json').read_bytes())

    def test_upload_requires_matching_ack_and_second_status_check(self):
        self.baseline(); vocab.apply_batch(self.batch([word()]))
        before = dict(hash='old', words=0, sentences=0); after = dict(hash='new', words=1, sentences=0)
        with patch.object(vocab, 'credential', return_value='test-only'), patch.object(vocab, 'api', side_effect=[before, after, after]) as api:
            vocab.publish(); self.assertEqual(api.call_count, 3)
            self.assertEqual(vocab.read_json(vocab.local('last_upload.json')), after)
        with patch.object(vocab, 'credential', return_value='test-only'), patch.object(vocab, 'api', side_effect=[before, dict(hash='bad', words=99, sentences=0)]):
            with self.assertRaises(ValueError): vocab.publish()

    def test_release_excludes_runtime_data_and_detects_embedded_keys(self):
        (self.root / 'README.md').write_text('test', encoding='utf-8')
        self.assertEqual([p.name for p in package_release.source_files(self.root)], ['README.md'])
        scripts = self.root / 'scripts'; scripts.mkdir()
        (scripts / 'leak.py').write_text('key = "sb_secret_' + 'x' * 40 + '"')
        with self.assertRaises(ValueError): package_release.source_files(self.root)

    def test_public_shell_contains_no_private_state(self):
        import shutil
        shutil.copytree(PROJECT / 'templates', self.root / 'templates')
        vocab.build_site(); vocab.site_zip()
        files = {p.relative_to(vocab.local('site')).as_posix() for p in vocab.local('site').rglob('*') if p.is_file()}
        self.assertEqual(files, vocab.SITE_FILES)
        for p in vocab.local('site').rglob('*'):
            if p.is_file(): self.assertNotIn(OWNER, p.read_text(encoding='utf-8'))


class PdfTests(unittest.TestCase):
    def test_marked_text_and_page_render(self):
        import pymupdf
        import extract_pdf
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as folder:
            root = Path(folder); document = pymupdf.open(); page = document.new_page()
            page.insert_text((40, 70), 'Reluctant learners sustain effort.', fontsize=18)
            target = page.search_for('Reluctant')[0]
            page.draw_rect(target, color=None, fill=(.85, .74, 1), fill_opacity=.55, overlay=True)
            target = page.search_for('sustain effort')[0]
            page.draw_rect(target, color=None, fill=(.5, 1, .5), fill_opacity=.5, overlay=True)
            pdf = root / 'synthetic.pdf'; document.save(pdf); document.close()
            result = extract_pdf.extract(pdf, root / 'out')
            self.assertIn('Reluctant', result['pages'][0]['vocab'])
            self.assertTrue(any('sustain effort' in x for x in result['pages'][0]['phrases']))
            self.assertTrue(Path(result['pages'][0]['render']).is_file())


if __name__ == '__main__': unittest.main()
