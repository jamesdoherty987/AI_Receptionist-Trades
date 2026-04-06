"""
Tests for OpenAI connection warmup and keepalive functionality.

These tests verify:
1. Warmup function works correctly
2. Keepalive loop handles errors gracefully
3. Graceful shutdown works
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestOpenAIWarmup:
    """Tests for the warmup_openai function"""
    
    @pytest.mark.asyncio
    async def test_warmup_success(self):
        """Test that warmup completes successfully with valid API"""
        from src.server import warmup_openai
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = Mock()
        
        with patch('src.server.get_openai_client', return_value=mock_client):
            with patch('src.server.config') as mock_config:
                mock_config.CHAT_MODEL = 'gpt-4o-mini'
                mock_config.max_tokens_param = lambda model=None, value=None: {"max_tokens": value if value is not None else 150}
                
                # Should not raise
                await warmup_openai()
                
                # Verify API was called with correct params
                mock_client.chat.completions.create.assert_called_once()
                call_kwargs = mock_client.chat.completions.create.call_args
                assert call_kwargs.kwargs['max_tokens'] == 1
                assert call_kwargs.kwargs['stream'] == True
    
    @pytest.mark.asyncio
    async def test_warmup_handles_api_error(self):
        """Test that warmup handles API errors gracefully"""
        from src.server import warmup_openai
        
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        with patch('src.server.get_openai_client', return_value=mock_client):
            with patch('src.server.config') as mock_config:
                mock_config.CHAT_MODEL = 'gpt-4o-mini'
                mock_config.max_tokens_param = lambda model=None, value=None: {"max_tokens": value if value is not None else 150}
                
                # Should not raise - just logs warning
                await warmup_openai()


class TestOpenAIKeepalive:
    """Tests for the keepalive loop"""
    
    @pytest.mark.asyncio
    async def test_keepalive_cancellation(self):
        """Test that keepalive loop handles cancellation gracefully"""
        from src.server import openai_keepalive_loop, OPENAI_KEEPALIVE_INTERVAL
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = Mock()
        
        with patch('src.server.get_openai_client', return_value=mock_client):
            with patch('src.server.config') as mock_config:
                mock_config.CHAT_MODEL = 'gpt-4o-mini'
                mock_config.max_tokens_param = lambda model=None, value=None: {"max_tokens": value if value is not None else 150}
                
                # Start the keepalive loop
                task = asyncio.create_task(openai_keepalive_loop())
                
                # Let it start
                await asyncio.sleep(0.1)
                
                # Cancel it
                task.cancel()
                
                # Should complete without error
                try:
                    await task
                except asyncio.CancelledError:
                    pass  # Expected
    
    @pytest.mark.asyncio
    async def test_keepalive_handles_repeated_failures(self):
        """Test that keepalive only logs after multiple failures"""
        from src.server import openai_keepalive_loop
        
        mock_client = Mock()
        call_count = 0
        
        def failing_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise Exception("API Error")
        
        mock_client.chat.completions.create.side_effect = failing_create
        
        with patch('src.server.get_openai_client', return_value=mock_client):
            with patch('src.server.config') as mock_config:
                mock_config.CHAT_MODEL = 'gpt-4o-mini'
                mock_config.max_tokens_param = lambda model=None, value=None: {"max_tokens": value if value is not None else 150}
                # Use short interval for testing
                with patch('src.server.OPENAI_KEEPALIVE_INTERVAL', 0.05):
                    
                    task = asyncio.create_task(openai_keepalive_loop())
                    
                    # Let it run a few iterations
                    await asyncio.sleep(0.3)
                    
                    # Cancel
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    
                    # Should have made multiple attempts
                    assert call_count >= 3


class TestShutdown:
    """Tests for graceful shutdown"""
    
    @pytest.mark.asyncio
    async def test_shutdown_cancels_keepalive(self):
        """Test that shutdown properly cancels the keepalive task"""
        from src.server import shutdown_event, openai_keepalive_loop
        import src.server as server_module
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = Mock()
        
        with patch('src.server.get_openai_client', return_value=mock_client):
            with patch('src.server.config') as mock_config:
                mock_config.CHAT_MODEL = 'gpt-4o-mini'
                mock_config.max_tokens_param = lambda model=None, value=None: {"max_tokens": value if value is not None else 150}
                
                # Start a keepalive task
                server_module._keepalive_task = asyncio.create_task(openai_keepalive_loop())
                
                await asyncio.sleep(0.1)
                
                # Shutdown should cancel it
                await shutdown_event()
                
                # Task should be done
                assert server_module._keepalive_task.done()
    
    @pytest.mark.asyncio
    async def test_shutdown_handles_no_task(self):
        """Test that shutdown works even if no keepalive task exists"""
        from src.server import shutdown_event
        import src.server as server_module
        
        server_module._keepalive_task = None
        
        # Should not raise
        await shutdown_event()


class TestIntegration:
    """Integration tests - these actually call OpenAI (use sparingly)"""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(True, reason="Requires real OpenAI API key - run manually")
    async def test_real_warmup(self):
        """Test warmup with real OpenAI API"""
        from src.server import warmup_openai
        
        # This will actually call OpenAI
        await warmup_openai()
