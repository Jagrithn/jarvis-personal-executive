import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/executive'))
from knowledge import read_workspace, verify_knowledge, natural_memory_request
from policy import route
from server import Executive


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name).resolve()
        self.root = self.data / 'workspace'
        self.root.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_explicit_routes_and_empty_queries(self):
        for command, cap in [('chat: hello', 'chat.local'), ('search memory: budget', 'memory.search'),
                             ('ask memory: goal?', 'memory.answer'), ('index workspace', 'memory.index')]:
            self.assertEqual(route(command), cap)
        with self.assertRaises(ValueError):
            route('chat: ')

    def test_natural_note_queries_and_boundaries(self):
        examples = {
            'Hey Jarvis, search my notes for chemistry': ('memory.search', 'chemistry'),
            'Please find memory for physics': ('memory.search', 'physics'),
            'What do my notes say about gravity?': ('memory.answer', 'gravity'),
            'Could you answer from my notes: photosynthesis?': ('memory.answer', 'photosynthesis'),
        }
        for command, expected in examples.items():
            with self.subTest(command=command):
                self.assertEqual(natural_memory_request(command), expected)
                self.assertEqual(route(command, True), expected[0])
        for command in ["don't search my notes for passwords", 'send my notes to Alice', 'what is gravity?', 'forget my memory']:
            self.assertIsNone(natural_memory_request(command))

    def test_reader_skips_links_and_subfolders(self):
        (self.data / 'private.txt').write_text('secret')
        (self.root / 'escape.txt').symlink_to(self.data / 'private.txt')
        (self.root / 'notes.md').write_text('local knowledge')
        (self.root / 'nested').mkdir()
        (self.root / 'nested/private.txt').write_text('nested')
        docs, skipped = read_workspace(self.root)
        self.assertEqual([d['source'] for d in docs], ['notes.md'])
        self.assertEqual(set(skipped), {'escape.txt', 'nested'})

    def test_reader_indexes_pdf_text_with_original_byte_hash(self):
        raw = b'%PDF-1.4 sample'
        (self.root / 'lecture.pdf').write_bytes(raw)
        with patch('knowledge.extract_pdf_text', return_value='Quantum chemistry notes'):
            docs, skipped = read_workspace(self.root)
        self.assertEqual(skipped, [])
        self.assertEqual(docs[0]['content'], 'Quantum chemistry notes')
        self.assertEqual(docs[0]['source'], 'lecture.pdf')
        self.assertEqual(docs[0]['sha256'], hashlib.sha256(raw).hexdigest())

    def test_reader_never_follows_pdf_symlink(self):
        (self.data / 'private.pdf').write_bytes(b'%PDF private')
        (self.root / 'escape.pdf').symlink_to(self.data / 'private.pdf')
        with patch('knowledge.extract_pdf_text') as extract:
            docs, skipped = read_workspace(self.root)
        self.assertEqual(docs, [])
        self.assertEqual(skipped, ['escape.pdf'])
        extract.assert_not_called()

    def test_selected_folder_is_read_and_cited_with_full_path(self):
        from knowledge import set_memory_folder
        selected = self.data / 'personal'
        selected.mkdir()
        (selected / 'chemistry.md').write_text('Chemistry notes')
        set_memory_folder(self.root, str(selected))
        docs, skipped = read_workspace(self.root)
        self.assertEqual(skipped, [])
        self.assertEqual(docs[0]['source'], str(selected / 'chemistry.md'))
        self.assertEqual(docs[0]['content'], 'Chemistry notes')

    def test_selected_folder_recurses_without_following_directory_symlinks(self):
        from knowledge import set_memory_folder
        selected = self.data / 'personal'
        selected.mkdir()
        nested = selected / 'chemistry'
        nested.mkdir()
        (nested / 'chapter.md').write_text('Atomic orbitals')
        outside = self.data / 'outside'
        outside.mkdir()
        (outside / 'secret.md').write_text('Outside the selection')
        (selected / 'escape').symlink_to(outside, target_is_directory=True)
        set_memory_folder(self.root, str(selected))
        docs, skipped = read_workspace(self.root)
        self.assertEqual([item['source'] for item in docs], [str(nested / 'chapter.md')])
        self.assertIn('escape', skipped)

    def test_selected_folder_rejects_symlink_and_can_restore_workspace(self):
        from knowledge import set_memory_folder
        selected = self.data / 'personal'
        selected.mkdir()
        link = self.data / 'link'
        link.symlink_to(selected)
        with self.assertRaises(ValueError):
            set_memory_folder(self.root, str(link))
        set_memory_folder(self.root, str(selected))
        set_memory_folder(self.root, '')
        (self.root / 'demo.txt').write_text('demo')
        docs, _ = read_workspace(self.root)
        self.assertEqual(docs[0]['source'], 'demo.txt')

    def test_folder_change_is_blocked_during_active_tasks(self):
        executive = Executive(self.data, Path('/unused'))
        try:
            task = executive.submit({'command': 'index workspace'})
            self.assertEqual(task['state'], 'awaiting_approval')
            with self.assertRaisesRegex(ValueError, 'active tasks'):
                executive.change_memory_folder({'path': str(self.data)})
            executive.cancel(task['id'])
            choice = executive.change_memory_folder({'path': str(self.data)})
            self.assertEqual(choice['path'], str(self.data))
        finally:
            executive.close()

    def test_reader_rejects_large_files_and_root_link(self):
        (self.root / 'large.txt').write_bytes(b'x' * 65537)
        with self.assertRaises(ValueError):
            read_workspace(self.root)
        link = self.data / 'link'
        link.symlink_to(self.root)
        with self.assertRaises(ValueError):
            read_workspace(link)

    def test_index_requires_confirmation_and_stop_revokes(self):
        executive = Executive(self.data, Path('/unused'))
        try:
            task = executive.submit({'command': 'index workspace'})
            self.assertEqual(task['state'], 'awaiting_approval')
            self.assertFalse((self.data / 'knowledge.sqlite3').exists())
            executive.stop()
            with self.assertRaises(ValueError):
                executive.approve(task['id'])
            self.assertEqual(executive.tasks[task['id']]['state'], 'cancelled')
        finally:
            executive.close()

    def test_independent_verification_rejects_false_index_claim(self):
        content = 'note'
        (self.root / 'notes.md').write_text(content)
        sha = hashlib.sha256(content.encode()).hexdigest()
        with sqlite3.connect(self.data / 'knowledge.sqlite3') as conn:
            conn.execute('CREATE TABLE documents(content, source, metadata)')
            conn.execute('INSERT INTO documents VALUES (?,?,?)', ('wrong', 'notes.md', json.dumps({'sha256': sha, 'offset': 0})))
        with self.assertRaises(RuntimeError):
            verify_knowledge('memory.index', {'indexed': [{'source': 'notes.md', 'sha256': sha}], 'chunks': 1}, self.root)

    def test_answer_verification_does_not_claim_factual_accuracy(self):
        evidence = verify_knowledge('chat.local', {'answer': 'A model answer.'}, self.root)
        self.assertFalse(evidence[0]['factual_accuracy_verified'])

    def test_fabricated_retrieval_is_rejected(self):
        with sqlite3.connect(self.data / 'knowledge.sqlite3') as conn:
            conn.execute('CREATE TABLE documents(content, source, metadata)')
        with self.assertRaises(RuntimeError):
            verify_knowledge('memory.search', {'matches': [{'source': 'fake', 'content': 'invented'}]}, self.root)

class AnswerPresentationTests(unittest.TestCase):
    def test_model_reasoning_markup_is_not_presented_as_answer(self):
        import knowledge
        self.assertTrue(hasattr(knowledge, 'visible_answer'))
        self.assertEqual(knowledge.visible_answer('<think>draft</think>\nHello.'), 'Hello.')
        self.assertEqual(knowledge.visible_answer('draft without opening tag</think>\nHello.'), 'Hello.')
        with self.assertRaises(ValueError):
            knowledge.visible_answer('<think>unfinished')
