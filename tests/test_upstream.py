"""Run with the fork's Python to exercise real native components and patched tools."""
import importlib.util
import json
from pathlib import Path
import shlex
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/executive'))
AVAILABLE = importlib.util.find_spec('openjarvis') is not None


@unittest.skipUnless(AVAILABLE, 'Run scripts/test-openjarvis.sh for native integration tests')
class UpstreamTests(unittest.TestCase):
    def test_real_memory_index_search_reindex(self):
        from knowledge import run, verify_knowledge
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / 'workspace'
            root.mkdir()
            (root / 'project.md').write_text('The aurora launch date is November 12.')
            result = run('memory.index', 'index workspace', root)
            verify_knowledge('memory.index', result, root)
            found = run('memory.search', 'search memory: aurora', root)
            self.assertIn('November 12', found['matches'][0]['content'])
            verify_knowledge('memory.search', found, root)
            (root / 'project.md').unlink()
            run('memory.index', 'index workspace', root)
            self.assertEqual(run('memory.search', 'search memory: aurora', root)['matches'], [])

    def test_shell_nonzero_and_environment(self):
        from openjarvis.tools.shell_exec import ShellExecTool
        tool = ShellExecTool()
        result = tool.execute(command='exit 7')
        self.assertFalse(result.success)
        self.assertEqual(result.metadata['returncode'], 7)
        with patch.dict('os.environ', {'JARVIS_TEST_SECRET': 'not-for-child'}):
            result = tool.execute(command='printf "%s" "${JARVIS_TEST_SECRET-unset}"')
        self.assertIn('unset', result.content)
        self.assertNotIn('not-for-child', result.content)

    def test_shell_timeout_reaps_descendants(self):
        from openjarvis.tools.shell_exec import ShellExecTool
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'should-not-exist'
            result = ShellExecTool().execute(command=f'(sleep 2; touch {shlex.quote(str(marker))}) & wait', timeout=1)
            self.assertFalse(result.success)
            time.sleep(1.3)
            self.assertFalse(marker.exists())

    def test_output_limit_and_write_gate(self):
        from openjarvis.tools.shell_exec import ShellExecTool
        from openjarvis.tools.file_write import FileWriteTool
        result = ShellExecTool().execute(command="yes x | head -c 200000")
        self.assertLess(len(result.content), 103000)
        self.assertTrue(FileWriteTool().spec.requires_confirmation)

    def test_unattended_routes_do_not_autoapprove(self):
        import openjarvis
        source = Path(openjarvis.__file__).parent / 'server/agent_manager_routes.py'
        self.assertNotIn('confirm_callback=lambda _prompt: True', source.read_text())

@unittest.skipUnless(AVAILABLE, 'Requires OpenJarvis runtime')
class MemoryLifecycleTests(unittest.TestCase):
    def test_stale_notes_are_not_returned(self):
        from knowledge import run
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / 'workspace'
            root.mkdir()
            note = root / 'facts.md'
            note.write_text('Aurora deadline November 12')
            run('memory.index', 'index workspace', root)
            note.write_text('Aurora deadline December 20')
            result = run('memory.search', 'search memory: Aurora', root)
            self.assertEqual(result['matches'], [])
            self.assertIn('facts.md', result['stale_sources'])

    def test_review_export_forget_preserves_originals(self):
        from knowledge import run, verify_knowledge
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / 'workspace'
            root.mkdir()
            (root / 'facts.md').write_text('Aurora deadline November 12')
            run('memory.index', 'index workspace', root)
            review = run('memory.review', 'review memory', root)
            self.assertEqual(review['sources'][0]['source'], 'facts.md')
            exported = run('memory.export', 'export memory', root)
            verify_knowledge('memory.export', exported, root)
            self.assertIn('Aurora', (root / exported['filename']).read_text())
            forgotten = run('memory.forget', 'forget memory', root)
            verify_knowledge('memory.forget', forgotten, root)
            self.assertEqual(run('memory.search', 'search memory: Aurora', root)['matches'], [])
            self.assertTrue((root / 'facts.md').exists())

@unittest.skipUnless(AVAILABLE, 'Requires OpenJarvis runtime')
class RetrievalAcceptanceTests(unittest.TestCase):
    def test_ten_source_grounded_queries_and_deleted_source(self):
        from knowledge import run, verify_knowledge
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / 'workspace'
            root.mkdir()
            for i in range(10):
                (root / f'note{i}.md').write_text(f'Project auroracase{i} deadline day {i + 1}.')
            run('memory.index', 'index workspace', root)
            for i in range(10):
                with self.subTest(case=i):
                    result = run('memory.search', f'search memory: auroracase{i}', root)
                    self.assertEqual([m['source'] for m in result['matches']], [f'note{i}.md'])
                    self.assertTrue(verify_knowledge('memory.search', result, root))
            (root / 'note0.md').unlink()
            result = run('memory.search', 'search memory: auroracase0', root)
            self.assertEqual(result['matches'], [])
            self.assertEqual(result['stale_sources'], ['note0.md'])
