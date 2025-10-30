"""
Test suite for OHLCV historic collector resume functionality.

Tests that the historic collector resumes from the last collected timestamp
instead of restarting from the backtest period.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import arrow
import pytest
from fullon_ohlcv.models import Candle
from fullon_ohlcv.repositories.ohlcv import CandleRepository
from fullon_orm.models import Symbol

# Import the module we're testing
import sys
import importlib.util
spec = importlib.util.spec_from_file_location(
    "historic_collector",
    "/home/ingmar/.cache/pypoetry/virtualenvs/fullon-master-api-Nd4OHEoI-py3.13/lib/python3.13/site-packages/fullon_ohlcv_service/ohlcv/historic_collector.py"
)
historic_collector_module = importlib.util.module_from_spec(spec)
sys.modules["historic_collector"] = historic_collector_module
spec.loader.exec_module(historic_collector_module)

from historic_collector import HistoricOHLCVCollector


class TestHistoricCollectorResume:
    """Test cases for historic collector resume functionality."""

    @pytest.mark.asyncio
    async def test_collector_starts_from_backtest_when_no_data_exists(self):
        """Test that collector starts from backtest period when no existing data."""
        # Create a mock symbol with 30 days backtest
        mock_symbol = MagicMock(spec=Symbol)
        mock_symbol.backtest = 30
        mock_symbol.symbol = "BTC/USDT"
        mock_symbol.cat_exchange.name = "binance"

        # Create mock handler
        mock_handler = AsyncMock()
        mock_handler.needs_trades_for_ohlcv.return_value = False
        mock_handler.get_ohlcv = AsyncMock(return_value=[])

        # Create collector
        collector = HistoricOHLCVCollector()

        # Mock CandleRepository to return None (no data exists)
        with patch.object(CandleRepository, '__aenter__', return_value=AsyncMock()) as mock_repo_context:
            mock_repo = mock_repo_context.return_value
            mock_repo.get_latest_timestamp = AsyncMock(return_value=None)
            mock_repo.save_candles = AsyncMock(return_value=True)

            # Mock ProcessCache
            with patch('historic_collector.ProcessCache'):
                # Call the method
                result = await collector._collect_symbol_historical(mock_handler, mock_symbol)

        # Verify it called get_ohlcv with timestamp from 30 days ago
        assert mock_handler.get_ohlcv.called
        call_args = mock_handler.get_ohlcv.call_args[1]
        since_timestamp = call_args['since']

        # Check that the timestamp is approximately 30 days ago (within 1 minute tolerance)
        expected_timestamp = int((datetime.now(UTC) - timedelta(days=30)).timestamp() * 1000)
        assert abs(since_timestamp - expected_timestamp) < 60000  # 1 minute tolerance

    @pytest.mark.asyncio
    async def test_collector_resumes_from_last_timestamp_when_data_exists(self):
        """Test that collector resumes from last collected timestamp when data exists."""
        # Create a mock symbol with 30 days backtest
        mock_symbol = MagicMock(spec=Symbol)
        mock_symbol.backtest = 30
        mock_symbol.symbol = "BTC/USDT"
        mock_symbol.cat_exchange.name = "binance"

        # Create mock handler
        mock_handler = AsyncMock()
        mock_handler.needs_trades_for_ohlcv.return_value = False
        mock_handler.get_ohlcv = AsyncMock(return_value=[])

        # Create collector
        collector = HistoricOHLCVCollector()

        # Set up a timestamp from 10 days ago as the latest existing data
        ten_days_ago = datetime.now(UTC) - timedelta(days=10)
        latest_timestamp = arrow.get(ten_days_ago)

        # Mock CandleRepository to return the latest timestamp
        with patch.object(CandleRepository, '__aenter__', return_value=AsyncMock()) as mock_repo_context:
            mock_repo = mock_repo_context.return_value
            mock_repo.get_latest_timestamp = AsyncMock(return_value=latest_timestamp)
            mock_repo.save_candles = AsyncMock(return_value=True)

            # Mock ProcessCache
            with patch('historic_collector.ProcessCache'):
                # Call the method
                result = await collector._collect_symbol_historical(mock_handler, mock_symbol)

        # Verify it called get_ohlcv with timestamp from 10 days ago + 1 second
        assert mock_handler.get_ohlcv.called
        call_args = mock_handler.get_ohlcv.call_args[1]
        since_timestamp = call_args['since']

        # Check that the timestamp is the last timestamp + 1 second
        expected_timestamp = int((ten_days_ago.timestamp() + 1) * 1000)
        assert abs(since_timestamp - expected_timestamp) < 1000  # 1 second tolerance

    @pytest.mark.asyncio
    async def test_collector_handles_none_from_get_latest_timestamp(self):
        """Test that collector handles None return from get_latest_timestamp correctly."""
        # Create a mock symbol with 7 days backtest
        mock_symbol = MagicMock(spec=Symbol)
        mock_symbol.backtest = 7
        mock_symbol.symbol = "ETH/USDT"
        mock_symbol.cat_exchange.name = "kraken"

        # Create mock handler
        mock_handler = AsyncMock()
        mock_handler.needs_trades_for_ohlcv.return_value = False
        mock_handler.get_ohlcv = AsyncMock(return_value=[])

        # Create collector
        collector = HistoricOHLCVCollector()

        # Mock CandleRepository to return None
        with patch.object(CandleRepository, '__aenter__', return_value=AsyncMock()) as mock_repo_context:
            mock_repo = mock_repo_context.return_value
            mock_repo.get_latest_timestamp = AsyncMock(return_value=None)
            mock_repo.save_candles = AsyncMock(return_value=True)

            # Mock ProcessCache
            with patch('historic_collector.ProcessCache'):
                # Call the method
                result = await collector._collect_symbol_historical(mock_handler, mock_symbol)

        # Verify it called get_ohlcv with timestamp from 7 days ago
        assert mock_handler.get_ohlcv.called
        call_args = mock_handler.get_ohlcv.call_args[1]
        since_timestamp = call_args['since']

        # Check that the timestamp is approximately 7 days ago
        expected_timestamp = int((datetime.now(UTC) - timedelta(days=7)).timestamp() * 1000)
        assert abs(since_timestamp - expected_timestamp) < 60000  # 1 minute tolerance

    @pytest.mark.asyncio
    async def test_collector_does_not_duplicate_data_on_restart(self):
        """Test that collector doesn't duplicate data when service is restarted."""
        # Create a mock symbol
        mock_symbol = MagicMock(spec=Symbol)
        mock_symbol.backtest = 30
        mock_symbol.symbol = "BTC/USDT"
        mock_symbol.cat_exchange.name = "binance"

        # Create mock handler that returns some candle data
        sample_candles = [
            [int(datetime.now(UTC).timestamp() * 1000) - 86400000, 50000, 51000, 49000, 50500, 100],  # Yesterday
            [int(datetime.now(UTC).timestamp() * 1000) - 82800000, 50500, 51500, 50000, 51000, 120],  # Yesterday + 1h
        ]
        mock_handler = AsyncMock()
        mock_handler.needs_trades_for_ohlcv.return_value = False
        mock_handler.get_ohlcv = AsyncMock(return_value=sample_candles)

        # Create collector
        collector = HistoricOHLCVCollector()

        # Set up latest timestamp to be yesterday (should resume from here)
        yesterday = datetime.now(UTC) - timedelta(days=1)
        latest_timestamp = arrow.get(yesterday)

        # Mock CandleRepository
        with patch.object(CandleRepository, '__aenter__', return_value=AsyncMock()) as mock_repo_context:
            mock_repo = mock_repo_context.return_value
            mock_repo.get_latest_timestamp = AsyncMock(return_value=latest_timestamp)
            mock_repo.save_candles = AsyncMock(return_value=True)

            # Mock ProcessCache
            with patch('historic_collector.ProcessCache'):
                # Call the method
                result = await collector._collect_symbol_historical(mock_handler, mock_symbol)

        # Verify it started collection from yesterday + 1 second
        assert mock_handler.get_ohlcv.called
        call_args = mock_handler.get_ohlcv.call_args[1]
        since_timestamp = call_args['since']

        # Should be yesterday + 1 second (to avoid duplicates)
        expected_timestamp = int((yesterday.timestamp() + 1) * 1000)
        assert abs(since_timestamp - expected_timestamp) < 1000  # 1 second tolerance

    @pytest.mark.asyncio
    async def test_collector_logs_resume_information(self, caplog):
        """Test that collector logs when resuming from existing data."""
        # Create a mock symbol
        mock_symbol = MagicMock(spec=Symbol)
        mock_symbol.backtest = 30
        mock_symbol.symbol = "BTC/USDT"
        mock_symbol.cat_exchange.name = "binance"

        # Create mock handler
        mock_handler = AsyncMock()
        mock_handler.needs_trades_for_ohlcv.return_value = False
        mock_handler.get_ohlcv = AsyncMock(return_value=[])

        # Create collector
        collector = HistoricOHLCVCollector()

        # Set up a timestamp from 5 days ago
        five_days_ago = datetime.now(UTC) - timedelta(days=5)
        latest_timestamp = arrow.get(five_days_ago)

        # Mock CandleRepository
        with patch.object(CandleRepository, '__aenter__', return_value=AsyncMock()) as mock_repo_context:
            mock_repo = mock_repo_context.return_value
            mock_repo.get_latest_timestamp = AsyncMock(return_value=latest_timestamp)
            mock_repo.save_candles = AsyncMock(return_value=True)

            # Mock ProcessCache
            with patch('historic_collector.ProcessCache'):
                # Enable debug logging to capture log messages
                import logging
                caplog.set_level(logging.DEBUG)

                # Call the method
                result = await collector._collect_symbol_historical(mock_handler, mock_symbol)

        # Check that appropriate log message was created
        # The actual implementation should log that it's resuming from existing data
        # This will be verified once the fix is implemented