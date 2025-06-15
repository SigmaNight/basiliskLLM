import pytest
import unittest.mock as mock
from unittest.mock import patch, MagicMock
import sys
import os
from io import StringIO

# Add the basilisk module to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from basilisk import main_app

@pytest.fixture
def sample_config():
    """Fixture providing sample configuration data for testing."""
    return {
        'host': 'localhost',
        'port': 8080,
        'debug': True,
        'database_url': 'sqlite:///test.db'
    }

@pytest.fixture
def mock_app_instance():
    """Fixture providing a mocked application instance."""
    with patch('basilisk.main_app.create_app') as mock_create:
        app = MagicMock()
        mock_create.return_value = app
        yield app

@pytest.fixture
def temp_config_file(tmp_path):
    """Fixture providing a temporary config file for testing."""
    config_file = tmp_path / "config.json"
    config_data = '{"host": "testhost", "port": 9000, "debug": false}'
    config_file.write_text(config_data)
    return str(config_file)

class TestMainAppInitialization:
    """Test cases for main application initialization."""

    def test_create_app_with_default_config(self):
        """Test that create_app works with default configuration."""
        with patch('basilisk.main_app.load_config') as mock_load:
            mock_load.return_value = {'debug': False, 'port': 8080}
            app = main_app.create_app()
            assert app is not None
            mock_load.assert_called_once()

    def test_create_app_with_custom_config(self, sample_config):
        """Test that create_app works with custom configuration."""
        with patch('basilisk.main_app.load_config') as mock_load:
            mock_load.return_value = sample_config
            app = main_app.create_app(config_path='custom.json')
            assert app is not None
            mock_load.assert_called_once_with('custom.json')

    def test_create_app_handles_missing_config(self):
        """Test that create_app handles missing configuration gracefully."""
        with patch('basilisk.main_app.load_config') as mock_load:
            mock_load.side_effect = FileNotFoundError("Config file not found")
            with pytest.raises(FileNotFoundError):
                main_app.create_app(config_path='nonexistent.json')

    def test_create_app_handles_invalid_config(self):
        """Test that create_app handles invalid configuration data."""
        with patch('basilisk.main_app.load_config') as mock_load:
            mock_load.return_value = None
            with pytest.raises(ValueError, match="Invalid configuration"):
                main_app.create_app()

class TestConfigurationHandling:
    """Test cases for configuration loading and validation."""

    def test_load_config_success(self, temp_config_file):
        """Test successful configuration loading from file."""
        config = main_app.load_config(temp_config_file)
        assert config['host'] == 'testhost'
        assert config['port'] == 9000
        assert config['debug'] is False

    def test_load_config_file_not_found(self):
        """Test handling of missing configuration file."""
        with pytest.raises(FileNotFoundError):
            main_app.load_config('nonexistent.json')

    def test_load_config_invalid_json(self, tmp_path):
        """Test handling of invalid JSON in configuration file."""
        invalid_config = tmp_path / "invalid.json"
        invalid_config.write_text('{"invalid": json}')
        with pytest.raises(ValueError, match="Invalid JSON"):
            main_app.load_config(str(invalid_config))

    def test_validate_config_success(self, sample_config):
        """Test successful configuration validation."""
        assert main_app.validate_config(sample_config) is True

    def test_validate_config_missing_required_fields(self):
        """Test validation failure for missing required fields."""
        incomplete_config = {'host': 'localhost'}
        assert main_app.validate_config(incomplete_config) is False

    def test_validate_config_invalid_port(self):
        """Test validation failure for invalid port values."""
        invalid_config = {'host': 'localhost', 'port': 'invalid'}
        assert main_app.validate_config(invalid_config) is False

        invalid_config = {'host': 'localhost', 'port': -1}
        assert main_app.validate_config(invalid_config) is False

        invalid_config = {'host': 'localhost', 'port': 70000}
        assert main_app.validate_config(invalid_config) is False

class TestMainAppRunner:
    """Test cases for main application runner functionality."""

    @patch('basilisk.main_app.create_app')
    def test_run_app_success(self, mock_create_app, sample_config):
        """Test successful application startup."""
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app

        with patch('basilisk.main_app.load_config', return_value=sample_config):
            main_app.run_app()

        mock_create_app.assert_called_once()
        mock_app.run.assert_called_once_with(
            host=sample_config['host'],
            port=sample_config['port'],
            debug=sample_config['debug']
        )

    @patch('basilisk.main_app.create_app')
    def test_run_app_handles_startup_error(self, mock_create_app):
        """Test handling of application startup errors."""
        mock_create_app.side_effect = RuntimeError("Startup failed")

        with pytest.raises(RuntimeError, match="Startup failed"):
            main_app.run_app()

    @patch('sys.argv', ['main_app.py', '--port', '9000', '--debug'])
    def test_parse_command_line_args(self):
        """Test command line argument parsing."""
        args = main_app.parse_args()
        assert args.port == 9000
        assert args.debug is True

    @patch('sys.argv', ['main_app.py', '--config', 'custom.json'])
    def test_parse_command_line_config_path(self):
        """Test command line config path parsing."""
        args = main_app.parse_args()
        assert args.config == 'custom.json'

    def test_parse_args_invalid_port(self):
        """Test handling of invalid port in command line arguments."""
        with patch('sys.argv', ['main_app.py', '--port', 'invalid']):
            with pytest.raises(SystemExit):
                main_app.parse_args()

class TestIntegrationScenarios:
    """Integration test cases for main application workflows."""

    @patch('basilisk.main_app.create_app')
    @patch('basilisk.main_app.load_config')
    def test_full_app_lifecycle(self, mock_load_config, mock_create_app, sample_config):
        """Test complete application lifecycle from config to running."""
        mock_load_config.return_value = sample_config
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app

        # Test initialization
        app = main_app.create_app()
        assert app is not None

        # Test running
        main_app.run_app()
        mock_app.run.assert_called_once()

    def test_environment_variable_override(self):
        """Test that environment variables override config values."""
        with patch.dict(os.environ, {'BASILISK_PORT': '9999', 'BASILISK_DEBUG': 'true'}):
            config = main_app.get_effective_config({})
            assert config['port'] == 9999
            assert config['debug'] is True

    def test_graceful_shutdown_handling(self):
        """Test graceful handling of shutdown signals."""
        with patch('signal.signal') as mock_signal:
            main_app.setup_signal_handlers()
            mock_signal.assert_called()

    @patch('sys.stdout', new_callable=StringIO)
    def test_logging_configuration(self, mock_stdout):
        """Test that logging is properly configured."""
        main_app.setup_logging(level='INFO')
        logger = main_app.get_logger()
        logger.info("Test message")
        assert "Test message" in mock_stdout.getvalue()

class TestErrorHandlingAndEdgeCases:
    """Test cases for error handling and edge cases."""

    def test_handle_database_connection_error(self):
        """Test handling of database connection failures."""
        with patch('basilisk.main_app.connect_database') as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")
            with pytest.raises(Exception, match="Connection failed"):
                main_app.initialize_database()

    def test_handle_port_already_in_use(self):
        """Test handling when specified port is already in use."""
        with patch('basilisk.main_app.create_app') as mock_create:
            mock_app = MagicMock()
            mock_app.run.side_effect = OSError("Port already in use")
            mock_create.return_value = mock_app

            with pytest.raises(OSError, match="Port already in use"):
                main_app.run_app()

    def test_memory_usage_under_load(self):
        """Test memory usage remains reasonable under simulated load."""
        initial_memory = main_app.get_memory_usage()

        # Simulate load
        for i in range(100):
            app = main_app.create_app()
            del app

        final_memory = main_app.get_memory_usage()
        # Allow for some memory increase but not excessive
        assert final_memory - initial_memory < 50  # MB

    def test_concurrent_app_creation(self):
        """Test thread safety of application creation."""
        import threading

        results = []

        def create_app_thread():
            try:
                app = main_app.create_app()
                results.append(app is not None)
            except Exception:
                results.append(False)

        threads = [threading.Thread(target=create_app_thread) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert all(results), "All concurrent app creations should succeed"

    @pytest.mark.parametrize("invalid_config", [
        {},  # Empty config
        {"host": ""},  # Empty host
        {"port": 0},  # Invalid port
        {"debug": "not_boolean"},  # Invalid debug value
    ])
    def test_various_invalid_configurations(self, invalid_config):
        """Test handling of various invalid configuration scenarios."""
        assert main_app.validate_config(invalid_config) is False

# Test utilities and cleanup
def teardown_module():
    """Clean up after all tests in this module."""
    import tempfile
    import shutil
    temp_dirs = [d for d in os.listdir(tempfile.gettempdir()) if d.startswith('pytest')]
    for temp_dir in temp_dirs:
        try:
            shutil.rmtree(os.path.join(tempfile.gettempdir(), temp_dir))
        except:
            pass  # Ignore cleanup errors

if __name__ == '__main__':
    # Allow running tests directly
    pytest.main([__file__, '-v'])