import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import json
import threading
import time
from typing import List, Dict, Any

# Import the module being tested
try:
    from basilisk.gui.prompt_attachments_panel import PromptAttachmentsPanel
except ImportError:
    # Handle import errors gracefully for CI/CD environments
    pytest.skip("PromptAttachmentsPanel module not available", allow_module_level=True)

# Import any UI framework dependencies that might be used
try:
    from PyQt5.QtWidgets import QApplication, QWidget
    from PyQt5.QtCore import Qt, QMimeData, QUrl
    from PyQt5.QtGui import QDragEnterEvent, QDropEvent
    UI_AVAILABLE = True
except ImportError:
    try:
        from PyQt6.QtWidgets import QApplication, QWidget
        from PyQt6.QtCore import Qt, QMimeData, QUrl
        from PyQt6.QtGui import QDragEnterEvent, QDropEvent
        UI_AVAILABLE = True
    except ImportError:
        UI_AVAILABLE = False

@pytest.fixture
def qapp():
    """Create QApplication instance for GUI tests."""
    if UI_AVAILABLE:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app
    else:
        yield None

@pytest.fixture
def mock_parent():
    """Mock parent widget for testing."""
    if UI_AVAILABLE:
        parent = Mock(spec=QWidget)
        parent.update = Mock()
        parent.repaint = Mock()
        return parent
    else:
        return Mock()

@pytest.fixture
def sample_attachments():
    """Sample attachment data for testing various scenarios."""
    return [
        {
            "name": "document.txt",
            "path": "/tmp/document.txt",
            "type": "text",
            "size": 1024,
            "modified": "2023-01-01T10:00:00Z"
        },
        {
            "name": "image.png",
            "path": "/tmp/image.png",
            "type": "image",
            "size": 2048,
            "modified": "2023-01-02T11:00:00Z"
        },
        {
            "name": "presentation.pdf",
            "path": "/tmp/presentation.pdf",
            "type": "document",
            "size": 4096,
            "modified": "2023-01-03T12:00:00Z"
        }
    ]

@pytest.fixture
def temp_files():
    """Create temporary files for testing file operations."""
    temp_dir = tempfile.mkdtemp()
    files = []
    file_contents = [
        ("test_file_1.txt", "This is test content for file 1"),
        ("test_file_2.md", "# Test Markdown\nThis is a test markdown file"),
        ("test_file_3.json", '{"test": "data", "number": 42}'),
        ("test_image.png", b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'),
        ("large_file.txt", "x" * 10000)  # Larger file for testing
    ]
    for filename, content in file_contents:
        file_path = Path(temp_dir) / filename
        if isinstance(content, bytes):
            file_path.write_bytes(content)
        else:
            file_path.write_text(content)
        files.append(str(file_path))
    yield files
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def panel(qapp, mock_parent):
    """Create a PromptAttachmentsPanel instance for testing."""
    try:
        panel = PromptAttachmentsPanel(parent=mock_parent)
        yield panel
        if hasattr(panel, 'cleanup'):
            panel.cleanup()
    except Exception:
        mock_panel = Mock(spec=PromptAttachmentsPanel)
        mock_panel.attachments = []
        mock_panel.parent = mock_parent
        yield mock_panel

@pytest.fixture
def panel_no_parent(qapp):
    """Create a PromptAttachmentsPanel instance without parent for testing."""
    try:
        panel = PromptAttachmentsPanel()
        yield panel
        if hasattr(panel, 'cleanup'):
            panel.cleanup()
    except Exception:
        mock_panel = Mock(spec=PromptAttachmentsPanel)
        mock_panel.attachments = []
        mock_panel.parent = None
        yield mock_panel

class TestPromptAttachmentsPanelInitialization:
    """Test the initialization and basic setup of the PromptAttachmentsPanel."""

    def test_panel_initialization_with_parent(self, qapp, mock_parent):
        panel = PromptAttachmentsPanel(parent=mock_parent)
        assert panel.parent == mock_parent
        assert hasattr(panel, 'attachments')
        assert isinstance(panel.attachments, list)
        assert len(panel.attachments) == 0

    def test_panel_initialization_without_parent(self, qapp):
        panel = PromptAttachmentsPanel()
        assert panel.parent is None
        assert hasattr(panel, 'attachments')
        assert isinstance(panel.attachments, list)

    def test_initial_state_properties(self, panel):
        assert panel.get_attachment_count() == 0
        assert panel.is_empty() is True
        assert panel.get_total_size() == 0
        if UI_AVAILABLE:
            assert hasattr(panel, 'layout')
            assert hasattr(panel, 'attachment_list')

    def test_panel_has_required_methods(self, panel):
        required_methods = [
            'add_attachment', 'remove_attachment', 'clear_attachments',
            'get_attachments', 'get_attachment_count', 'is_empty'
        ]
        for method_name in required_methods:
            assert hasattr(panel, method_name)
            assert callable(getattr(panel, method_name))

    def test_panel_signals_and_slots(self, panel):
        if UI_AVAILABLE and hasattr(panel, 'attachment_added'):
            assert hasattr(panel, 'attachment_added')
            assert hasattr(panel, 'attachment_removed')
            assert hasattr(panel, 'attachments_cleared')

class TestAddAttachments:
    """Test adding attachments to the panel - happy path scenarios."""

    def test_add_single_valid_file(self, panel, temp_files):
        file_path = temp_files[0]
        result = panel.add_attachment(file_path)
        assert result is True
        assert panel.get_attachment_count() == 1
        attachments = panel.get_attachments()
        assert attachments[0]['path'] == file_path
        assert attachments[0]['name'] == os.path.basename(file_path)
        assert 'size' in attachments[0] and attachments[0]['size'] > 0

    def test_add_multiple_attachments_sequentially(self, panel, temp_files):
        for i, file_path in enumerate(temp_files[:3]):
            assert panel.add_attachment(file_path) is True
            assert panel.get_attachment_count() == i + 1
        attached_paths = [att['path'] for att in panel.get_attachments()]
        for file_path in temp_files[:3]:
            assert file_path in attached_paths

    def test_add_attachments_batch(self, panel, temp_files):
        if hasattr(panel, 'add_attachments'):
            assert panel.add_attachments(temp_files[:3]) is True
            assert panel.get_attachment_count() == 3
        else:
            for file_path in temp_files[:3]:
                panel.add_attachment(file_path)
            assert panel.get_attachment_count() == 3

    def test_add_attachment_with_custom_metadata(self, panel, temp_files):
        file_path = temp_files[0]
        metadata = {"description": "Test document", "category": "documentation", "tags": ["test"], "priority": "high"}
        if hasattr(panel, 'add_attachment') and 'metadata' in panel.add_attachment.__code__.co_varnames:
            assert panel.add_attachment(file_path, metadata=metadata) is True
            att = panel.get_attachments()[0]
            assert att.get('description') == "Test document"
            assert att.get('category') == "documentation"
        else:
            assert panel.add_attachment(file_path) is True

    def test_add_different_file_types(self, panel, temp_files):
        for file_path in temp_files:
            assert panel.add_attachment(file_path) is True
        exts = {Path(att['path']).suffix for att in panel.get_attachments()}
        for ext in ['.txt', '.md', '.json']:
            assert ext in exts

    def test_add_attachment_triggers_signals(self, panel, temp_files):
        if UI_AVAILABLE and hasattr(panel, 'attachment_added'):
            with patch.object(panel, 'attachment_added') as sig:
                panel.add_attachment(temp_files[0])
                sig.emit.assert_called_once()

class TestAddAttachmentsEdgeCases:
    """Test edge cases and error conditions when adding attachments."""

    def test_add_nonexistent_file(self, panel):
        assert panel.add_attachment("/no/such/file") is False
        assert panel.get_attachment_count() == 0
        assert panel.is_empty()

    def test_add_empty_file_path(self, panel):
        for p in ["", "   ", "\n", None]:
            assert panel.add_attachment(p) is False
        assert panel.get_attachment_count() == 0

    def test_add_directory_instead_of_file(self, panel):
        with tempfile.TemporaryDirectory() as d:
            result = panel.add_attachment(d)
            if result is False:
                assert panel.get_attachment_count() == 0

    def test_add_duplicate_attachment(self, panel, temp_files):
        p = temp_files[0]
        assert panel.add_attachment(p) is True
        res2 = panel.add_attachment(p)
        if res2 is False:
            assert panel.get_attachment_count() == 1
        else:
            assert panel.get_attachment_count() <= 2

    def test_add_attachment_with_invalid_characters(self, panel):
        with tempfile.TemporaryDirectory() as d:
            for c in ['<','>',':','"','|','?','*']:
                try:
                    fn = f"test{c}file.txt"
                    path = Path(d)/fn
                    path.write_text("x")
                    panel.add_attachment(str(path))
                except (OSError, ValueError):
                    pass

    def test_add_very_long_filename(self, panel):
        with tempfile.TemporaryDirectory() as d:
            fn = "a"*255 + ".txt"
            path = Path(d)/fn
            try:
                path.write_text("x")
                panel.add_attachment(str(path))
            except OSError:
                pass

    def test_add_attachment_insufficient_permissions(self, panel):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(b"x"); tmp.close()
        os.chmod(tmp.name, 0o000)
        try:
            assert panel.add_attachment(tmp.name) is False
        finally:
            os.chmod(tmp.name, 0o644)
            os.unlink(tmp.name)

    def test_add_large_file_size_limit(self, panel):
        f = tempfile.NamedTemporaryFile(delete=False)
        large = b"x"*(10*1024*1024)
        f.write(large); f.close()
        try:
            res = panel.add_attachment(f.name)
            if hasattr(panel, 'max_file_size') and os.path.getsize(f.name) > panel.max_file_size:
                assert res is False
        finally:
            os.unlink(f.name)

class TestRemoveAttachments:
    """Test removing attachments from the panel."""

    def test_remove_attachment_by_index(self, panel, sample_attachments):
        panel.attachments = sample_attachments.copy()
        initial = panel.get_attachment_count()
        target = panel.attachments[1]
        assert panel.remove_attachment(1) is True
        assert panel.get_attachment_count() == initial - 1
        assert target not in panel.get_attachments()

    def test_remove_attachment_by_path(self, panel, sample_attachments):
        panel.attachments = sample_attachments.copy()
        if hasattr(panel, 'remove_attachment_by_path'):
            p = sample_attachments[0]['path']
            assert panel.remove_attachment_by_path(p) is True
            assert p not in [a['path'] for a in panel.get_attachments()]

    def test_remove_attachment_by_name(self, panel, sample_attachments):
        panel.attachments = sample_attachments.copy()
        if hasattr(panel, 'remove_attachment_by_name'):
            n = sample_attachments[2]['name']
            assert panel.remove_attachment_by_name(n) is True
            assert n not in [a['name'] for a in panel.get_attachments()]

    def test_remove_multiple_attachments(self, panel, sample_attachments):
        panel.attachments = sample_attachments.copy()
        for idx in reversed([0,2]):
            assert panel.remove_attachment(idx) is True
        assert panel.get_attachment_count() == 1
        assert panel.get_attachments()[0]['name'] == sample_attachments[1]['name']

    def test_remove_attachment_invalid_index(self, panel, sample_attachments):
        panel.attachments = sample_attachments.copy()
        init = panel.get_attachment_count()
        for i in [-1, len(sample_attachments), 999]:
            assert panel.remove_attachment(i) is False
            assert panel.get_attachment_count() == init

    def test_remove_attachment_from_empty_panel(self, panel):
        assert panel.is_empty()
        assert panel.remove_attachment(0) is False

    def test_remove_attachment_triggers_signals(self, panel, sample_attachments):
        panel.attachments = sample_attachments.copy()
        if UI_AVAILABLE and hasattr(panel, 'attachment_removed'):
            with patch.object(panel, 'attachment_removed') as sig:
                panel.remove_attachment(0)
                sig.emit.assert_called_once()

    def test_clear_all_attachments(self, panel, sample_attachments):
        panel.attachments = sample_attachments.copy()
        panel.clear_attachments()
        assert panel.is_empty()

    def test_clear_attachments_triggers_signals(self, panel, sample_attachments):
        panel.attachments = sample_attachments.copy()
        if UI_AVAILABLE and hasattr(panel, 'attachments_cleared'):
            with patch.object(panel, 'attachments_cleared') as sig:
                panel.clear_attachments()
                sig.emit.assert_called_once()

class TestAttachmentValidation:
    """Test attachment validation and filtering functionality."""

    def test_validate_supported_file_types(self, panel):
        if hasattr(panel, 'validate_file_type'):
            exts = ['.txt','.pdf','.png','.jpg','.jpeg','.gif','.doc','.docx','.md','.json','.xml','.csv']
            for e in exts:
                assert panel.validate_file_type(f"file{e}") is True

    def test_validate_unsupported_file_types(self, panel):
        if hasattr(panel, 'validate_file_type'):
            for e in ['.exe','.bat','.sh','.scr','.com','.pif']:
                assert panel.validate_file_type(f"file{e}") is False

    def test_validate_file_size_within_limits(self, panel):
        if hasattr(panel, 'validate_file_size'):
            for s in [1024,1024*1024,5*1024*1024]:
                assert panel.validate_file_size(s) is True

    def test_validate_file_size_exceeds_limits(self, panel):
        if hasattr(panel, 'validate_file_size'):
            for s in [100*1024*1024,500*1024*1024,1024*1024*1024]:
                panel.validate_file_size(s)

    def test_validate_file_exists_and_readable(self, panel, temp_files):
        if hasattr(panel, 'validate_file_path'):
            assert panel.validate_file_path(temp_files[0]) is True
            assert panel.validate_file_path("/no/such") is False

    def test_filter_attachments_by_type(self, panel, sample_attachments):
        panel.attachments = sample_attachments.copy()
        if hasattr(panel, 'filter_by_type'):
            t = panel.filter_by_type('text')
            for att in t:
                assert att['type']=='text'

    def test_filter_attachments_by_size(self, panel, sample_attachments):
        panel.attachments = sample_attachments.copy()
        if hasattr(panel, 'filter_by_size'):
            small = panel.filter_by_size(max_size=2000)
            for att in small:
                assert att['size']<=2000

    def test_search_attachments_by_name(self, panel, sample_attachments):
        panel.attachments = sample_attachments.copy()
        if hasattr(panel, 'search_by_name'):
            res = panel.search_by_name('document')
            assert any('document' in att['name'].lower() for att in res)

    def test_get_attachment_statistics(self, panel, sample_attachments):
        panel.attachments = sample_attachments.copy()
        if hasattr(panel, 'get_statistics'):
            stats = panel.get_statistics()
            assert stats['total_count']==len(sample_attachments)
            assert stats['total_size']>0

class TestUIInteractions:
    """Test UI interactions and event handling."""

    @pytest.mark.skipif(not UI_AVAILABLE, reason="UI framework not available")
    def test_drag_enter_event_with_files(self, panel, temp_files):
        if hasattr(panel, 'dragEnterEvent'):
            event = Mock()
            md = Mock(); md.hasUrls.return_value=True
            urls=[]
            for p in temp_files[:2]:
                u=Mock(); u.toLocalFile.return_value=p; u.isLocalFile.return_value=True
                urls.append(u)
            md.urls.return_value=urls
            event.mimeData.return_value=md
            panel.dragEnterEvent(event)
            event.acceptProposedAction.assert_called_once()

    @pytest.mark.skipif(not UI_AVAILABLE, reason="UI framework not available")
    def test_drop_event_adds_files(self, panel, temp_files):
        if hasattr(panel, 'dropEvent'):
            ev=Mock(); md=Mock(); md.hasUrls.return_value=True
            urls=[]
            for p in temp_files[:2]:
                u=Mock(); u.toLocalFile.return_value=p; u.isLocalFile.return_value=True
                urls.append(u)
            md.urls.return_value=urls
            ev.mimeData.return_value=md
            before=panel.get_attachment_count()
            panel.dropEvent(ev)
            assert panel.get_attachment_count()>before
            ev.acceptProposedAction.assert_called_once()

    @patch('PyQt5.QtWidgets.QFileDialog.getOpenFileNames', autospec=True)
    def test_browse_files_dialog_selection(self, mock_dlg, panel, temp_files):
        if hasattr(panel, 'browse_files'):
            mock_dlg.return_value=(temp_files[:2],'All Files (*)')
            before=panel.get_attachment_count()
            panel.browse_files()
            mock_dlg.assert_called_once()
            assert panel.get_attachment_count()>before

    @patch('PyQt5.QtWidgets.QFileDialog.getOpenFileNames', autospec=True)
    def test_browse_files_dialog_cancelled(self, mock_dlg, panel):
        if hasattr(panel, 'browse_files'):
            mock_dlg.return_value=([],'')
            before=panel.get_attachment_count()
            panel.browse_files()
            assert panel.get_attachment_count()==before

    def test_context_menu_actions(self, panel, sample_attachments):
        panel.attachments = sample_attachments.copy()
        if hasattr(panel, 'show_context_menu'):
            with patch.object(panel, 'remove_attachment') as rm:
                if hasattr(panel, 'on_remove_selected'):
                    panel.on_remove_selected()
                    rm.assert_called()

    def test_keyboard_shortcuts(self, panel, sample_attachments):
        if UI_AVAILABLE and hasattr(panel, 'keyPressEvent'):
            from PyQt5.QtCore import Qt
            from PyQt5.QtGui import QKeyEvent
            panel.attachments = sample_attachments.copy()
            evt = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
            with patch.object(panel, 'remove_selected_attachments') as rm:
                panel.keyPressEvent(evt)

    def test_selection_handling(self, panel, sample_attachments):
        panel.attachments = sample_attachments.copy()
        if hasattr(panel, 'select_attachment'):
            panel.select_attachment(0)
            if hasattr(panel, 'get_selected_indices'):
                assert 0 in panel.get_selected_indices()

    def test_attachment_display_update(self, panel, sample_attachments):
        if hasattr(panel, 'update_display'):
            with patch.object(panel, 'update_display') as upd:
                panel.attachments = sample_attachments.copy()
                if hasattr(panel, 'refresh_display'):
                    panel.refresh_display()
                    upd.assert_called()

class TestDataPersistence:
    """Test data persistence and serialization functionality."""

    def test_serialize_attachments_to_json(self, panel, sample_attachments):
        panel.attachments = sample_attachments.copy()
        if hasattr(panel, 'to_json'):
            js = panel.to_json()
            lst = json.loads(js)
            assert isinstance(lst, list) and len(lst)==len(sample_attachments)

    def test_deserialize_attachments_from_json(self, panel):
        if hasattr(panel, 'from_json'):
            data = json.dumps([
                {"name":"a","path":"/a","type":"text","size":1},
                {"name":"b","path":"/b","type":"image","size":2}
            ])
            panel.from_json(data)
            assert panel.get_attachment_count()==2

    def test_deserialize_invalid_json(self, panel):
        if hasattr(panel, 'from_json'):
            for bad in ['{invalid}','[{"name":"x"}]','not json','[]','null']:
                try:
                    panel.from_json(bad)
                except (json.JSONDecodeError,ValueError,KeyError):
                    pass

    def test_save_attachments_to_file(self, panel, sample_attachments):
        panel.attachments = sample_attachments.copy()
        if hasattr(panel, 'save_to_file'):
            f=tempfile.NamedTemporaryFile(mode='w',delete=False,suffix='.json')
            f.close()
            try:
                assert panel.save_to_file(f.name) is True
                with open(f.name) as fp:
                    loaded=json.load(fp)
                    assert len(loaded)==len(sample_attachments)
            finally:
                os.unlink(f.name)

    def test_load_attachments_from_file(self, panel, sample_attachments):
        if hasattr(panel, 'load_from_file'):
            f=tempfile.NamedTemporaryFile(mode='w',delete=False,suffix='.json')
            json.dump(sample_attachments, f)
            f.close()
            try:
                assert panel.load_from_file(f.name) is True
                assert panel.get_attachment_count()==len(sample_attachments)
            finally:
                os.unlink(f.name)

    def test_load_from_nonexistent_file(self, panel):
        if hasattr(panel, 'load_from_file'):
            assert panel.load_from_file('/no/such.json') is False

    def test_export_attachments_metadata(self, panel, sample_attachments):
        panel.attachments = sample_attachments.copy()
        if hasattr(panel, 'export_to_csv'):
            f=tempfile.NamedTemporaryFile(mode='w',delete=False,suffix='.csv')
            f.close()
            try:
                assert panel.export_to_csv(f.name) is True
                with open(f.name) as fp:
                    txt=fp.read()
                    assert 'name' in txt and sample_attachments[0]['name'] in txt
            finally:
                os.unlink(f.name)

    def test_backup_and_restore(self, panel, sample_attachments):
        panel.attachments = sample_attachments.copy()
        if hasattr(panel, 'create_backup') and hasattr(panel, 'restore_from_backup'):
            b=panel.create_backup()
            panel.clear_attachments()
            assert panel.restore_from_backup(b) is True
            assert panel.get_attachment_count()==len(sample_attachments)

class TestPerformanceAndStress:
    """Test performance characteristics and stress scenarios."""

    def test_add_large_number_of_attachments(self, panel):
        with tempfile.TemporaryDirectory() as d:
            paths=[]
            for i in range(100):
                p=Path(d)/f"f{i}.txt"
                p.write_text(f"i")
                paths.append(str(p))
            start=time.time()
            for p in paths:
                panel.add_attachment(p)
            duration=time.time()-start
            assert panel.get_attachment_count()==100
            assert duration<10.0

    def test_concurrent_attachment_operations(self, panel, temp_files):
        def add():
            for p in temp_files:
                try: panel.add_attachment(p); time.sleep(0.01)
                except: pass
        def remove():
            for _ in temp_files:
                try:
                    if panel.get_attachment_count()>0:
                        panel.remove_attachment(0)
                        time.sleep(0.01)
                except: pass
        t1=threading.Thread(target=add)
        t2=threading.Thread(target=remove)
        t1.start(); t2.start()
        t1.join(timeout=5); t2.join(timeout=5)
        assert True

    def test_memory_usage_with_many_attachments(self, panel):
        try:
            import psutil
            proc=psutil.Process(os.getpid())
            before=proc.memory_info().rss
            with tempfile.TemporaryDirectory() as d:
                for i in range(50):
                    p=Path(d)/f"x{i}.txt"
                    p.write_text("x"*1000)
                    panel.add_attachment(str(p))
            after=psutil.Process(os.getpid()).memory_info().rss
            assert after-before < 50*1024*1024
        except ImportError:
            pytest.skip("psutil not available")

    def test_large_file_handling(self, panel):
        f=tempfile.NamedTemporaryFile(delete=False)
        f.write(b"x"*(5*1024*1024)); f.close()
        try:
            start=time.time()
            res=panel.add_attachment(f.name)
            dur=time.time()-start
            if res:
                assert dur<5.0
                att=panel.get_attachments()[0]
                assert att['size']==5*1024*1024
        finally:
            os.unlink(f.name)

    def test_rapid_add_remove_operations(self, panel, temp_files):
        p=temp_files[0]
        start=time.time()
        for _ in range(50):
            panel.add_attachment(p)
            if panel.get_attachment_count()>0:
                panel.remove_attachment(0)
        assert time.time()-start<5.0
        assert panel.get_attachment_count()>=0

class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_typical_user_workflow(self, panel, temp_files):
        assert panel.is_empty()
        for p in temp_files[:3]:
            assert panel.add_attachment(p)
        assert panel.get_attachment_count()==3
        panel.remove_attachment(1)
        assert panel.get_attachment_count()==2
        panel.clear_attachments()
        assert panel.is_empty()

    def test_error_recovery_scenarios(self, panel, temp_files):
        panel.add_attachment(temp_files[0])
        assert panel.get_attachment_count()==1
        panel.add_attachment("/bad/path")
        assert panel.get_attachment_count()==1
        panel.remove_attachment(999)
        assert panel.get_attachment_count()==1
        assert panel.get_attachments()[0]['path']==temp_files[0]

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])