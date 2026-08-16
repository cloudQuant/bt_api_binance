"""

、、
"""

from __future__ import annotations

import time
from decimal import Decimal

import pytest

pytest.importorskip("sklearn")

from bt_api_py.risk_management.containers.risk_events import RiskEventType, RiskLevel
from bt_api_py.risk_management.containers.risk_metrics import RiskMetrics
from bt_api_py.risk_management.core.limits_manager import LimitsManager
from bt_api_py.risk_management.core.policy_engine import PolicyEngine
from bt_api_py.risk_management.core.risk_assessor import RiskAssessor
from bt_api_py.risk_management.core.risk_manager import RiskManager
from bt_api_py.risk_management.ml_models.anomaly_detector import AnomalyDetector
from bt_api_py.risk_management.ml_models.ensemble_model import RiskEnsembleModel


class TestRiskManagement:
    """"""

    @pytest.fixture
    def risk_manager(self):
        """"""
        config = {
            "monitoring_interval": 0.1,  # 100ms for testing
            "risk_thresholds": {
                "low": 0.3,
                "medium": 0.6,
                "high": 0.8,
                "critical": 0.9,
            },
        }
        return RiskManager(config=config)

    @pytest.fixture
    def sample_account_data(self):
        """"""
        return {
            "account_id": "test_account",
            "exchange_name": "BINANCE",
            "balance": 100000,
            "used_credit": 20000,
            "total_credit": 50000,
            "kyc_status": "VERIFIED",
            "aml_flags": [],
            "account_age_days": 365,
            "trading_volume": 5000000,
        }

    @pytest.fixture
    def sample_position_data(self):
        """"""
        return {
            "positions": [
                {"symbol": "BTCUSDT", "value": 50000, "sector": "technology"},
                {"symbol": "ETHUSDT", "value": 30000, "sector": "technology"},
                {"symbol": "AAPL", "value": 20000, "sector": "technology"},
            ],
            "portfolio_value": 100000,
            "total_exposure": 100000,
            "leverage": 2.0,
            "concentration_ratio": 0.5,
            "collateral_ratio": 0.5,
        }

    @pytest.fixture
    def sample_market_data(self):
        """"""
        return {
            "price_history": [100, 102, 98, 105, 103, 101, 99, 107, 104, 102]
            * 10,  # 100 data points
            "market_returns": [0.02, -0.04, 0.07, -0.02, -0.02, -0.02, 0.08, -0.03, -0.02] * 10,
            "asset_returns": {
                "BTC": [0.02, -0.04, 0.07, -0.02, -0.02, -0.02, 0.08, -0.03, -0.02] * 10,
                "ETH": [0.01, -0.02, 0.05, -0.01, -0.01, -0.01, 0.06, -0.02, -0.01] * 10,
            },
            "bid_price": 101.5,
            "ask_price": 102.5,
            "bid_depth": 1000000,
            "ask_depth": 1000000,
            "volume_24h": 50000000,
            "volatility": 0.3,
            "bid_ask_spread": 10,  # bps
            "market_depth": 2000000,
            "liquidity_score": 0.8,
            "correlation_breakdown": 0.1,
        }

    @pytest.fixture
    def sample_order_data(self):
        """"""
        return {
            "symbol": "BTCUSDT",
            "side": "buy",
            "size": 10.0,
            "price": 50000,
            "type": "limit",
            "order_id": "test_order_123",
        }

    def test_risk_assessor_initialization(self):
        """"""
        assessor = RiskAssessor()

        assert assessor is not None
        assert assessor.factor_weights is not None
        assert assessor.risk_thresholds is not None
        assert len(assessor.historical_assessments) == 0

    def test_risk_assessment(self, sample_account_data, sample_position_data, sample_market_data):
        """"""
        assessor = RiskAssessor()

        # 
        risk_metrics = RiskMetrics(
            {
                "exchange_name": "BINANCE",
                "account_id": "test_account",
                "market_risk": {
                    "value_at_risk_1d": 10000,
                    "value_at_risk_10d": 30000,
                    "expected_shortfall": 12000,
                    "volatility": 0.3,
                    "beta": 1.2,
                    "position_concentration": {"herfindahl_index": 0.4},
                },
                "credit_risk": {
                    "credit_score": 750,
                    "probability_of_default": 0.01,
                    "credit_utilization": 0.4,
                },
                "operational_risk": {
                    "system_health_score": 0.9,
                    "error_rate": 0.01,
                    "system_availability": 0.99,
                },
                "liquidity_risk": {
                    "liquidity_score": 0.8,
                    "bid_ask_spread": 5,
                    "market_depth": 1000000,
                },
                "compliance_risk": {
                    "compliance_score": 0.95,
                    "kyc_status": "VERIFIED",
                    "aml_flags": [],
                },
            }
        )

        # 
        result = assessor.assess_risk(risk_metrics)

        assert result is not None
        assert hasattr(result, "score")
        assert hasattr(result, "level")
        assert hasattr(result, "confidence")
        assert 0 <= float(result.score) <= 1
        assert result.level.value in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    def test_risk_manager_initialization(self, risk_manager):
        """"""
        assert risk_manager is not None
        assert risk_manager.risk_assessor is not None
        assert risk_manager.risk_calculator is not None
        assert risk_manager.limits_manager is not None
        assert risk_manager.policy_engine is not None
        assert not risk_manager.is_monitoring

    def test_risk_metrics_calculation(
        self, risk_manager, sample_account_data, sample_position_data, sample_market_data
    ):
        """"""
        risk_metrics = risk_manager.risk_calculator.calculate_risk_metrics(
            exchange_name="BINANCE",
            account_id="test_account",
            account_data=sample_account_data,
            position_data=sample_position_data,
            market_data=sample_market_data,
        )

        assert risk_metrics is not None
        assert risk_metrics.exchange_name == "BINANCE"
        assert risk_metrics.account_id == "test_account"
        assert hasattr(risk_metrics, "market_risk")
        assert hasattr(risk_metrics, "credit_risk")
        assert hasattr(risk_metrics, "operational_risk")
        assert hasattr(risk_metrics, "liquidity_risk")
        assert hasattr(risk_metrics, "compliance_risk")

    def test_order_risk_check(self, risk_manager, sample_order_data):
        """"""
        result = risk_manager.check_order_risk(
            exchange_name="BINANCE", account_id="test_account", order_data=sample_order_data
        )

        assert result is not None
        assert "approved" in result
        assert "risk_level" in result
        assert "risk_score" in result
        assert "warnings" in result
        assert "restrictions" in result

    def test_risk_event_creation(self, risk_manager):
        """"""
        event = risk_manager.create_risk_event(
            event_type=RiskEventType.MARKET_VOLATILITY_SPIKE,
            risk_level=RiskLevel.HIGH,
            title="Test High Volatility Event",
            description="Test event for high market volatility",
            exchange_name="BINANCE",
            account_id="test_account",
        )

        assert event is not None
        assert event.event_type == RiskEventType.MARKET_VOLATILITY_SPIKE.value
        assert event.risk_level == RiskLevel.HIGH.value
        assert event.title == "Test High Volatility Event"
        assert event.exchange_name == "BINANCE"
        assert event.account_id == "test_account"
        assert event.event_id is not None

    def test_limits_manager_initialization(self):
        """"""
        manager = LimitsManager()

        assert manager is not None
        assert manager.static_limits is not None
        assert manager.dynamic_limits is not None
        assert manager.user_limits is not None

    def test_static_limit_setting(self):
        """"""
        manager = LimitsManager()

        manager.set_static_limit(
            limit_type="max_order_size",
            exchange_name="BINANCE",
            account_id="test_account",
            value=1000000,
        )

        limits = manager.get_current_limits("BINANCE", "test_account")
        assert "max_order_size" in limits
        assert limits["max_order_size"]["value"] == 1000000

    def test_pre_trade_limits_check(self):
        """"""
        manager = LimitsManager()

        # 
        manager.set_static_limit(
            limit_type="max_order_size",
            exchange_name="BINANCE",
            account_id="test_account",
            value=1000000,
        )

        # 
        order_data = {
            "symbol": "BTCUSDT",
            "size": 10.0,
            "price": 50000,  # 500,000 value, within limit
        }

        result = manager.check_pre_trade_limits(
            exchange_name="BINANCE", account_id="test_account", order_data=order_data
        )

        assert result is not None
        assert "approved" in result
        assert "warnings" in result
        assert "restrictions" in result

    def test_policy_engine_initialization(self):
        """"""
        engine = PolicyEngine()

        assert engine is not None
        assert engine.rules is not None
        assert engine.action_handlers is not None
        assert len(engine.rules) > 0  # 

    def test_order_policy_evaluation(self):
        """"""
        engine = PolicyEngine()

        order_data = {
            "symbol": "BTCUSDT",
            "size": 10.0,
            "price": 50000,
        }

        risk_metrics = {
            "risk_level": "LOW",
            "overall_risk_score": 0.3,
        }

        result = engine.evaluate_order_policy(
            exchange_name="BINANCE",
            account_id="test_account",
            order_data=order_data,
            risk_metrics=risk_metrics,
        )

        assert result is not None
        assert "approved" in result
        assert "warnings" in result
        assert "restrictions" in result
        assert "triggered_rules" in result

    def test_anomaly_detector_initialization(self):
        """"""
        detector = AnomalyDetector()

        assert detector is not None
        assert detector.isolation_forest is not None
        assert detector.one_class_svm is not None
        assert not detector.is_trained

    def test_anomaly_detection_training(self):
        """"""
        detector = AnomalyDetector()

        # 
        import numpy as np

        np.random.seed(42)
        X_normal = np.random.normal(0, 1, (1000, 5))

        result = detector.train(X_normal)

        assert result is not None
        assert detector.is_trained
        assert "success" in result

    def test_anomaly_detection(self):
        """"""
        detector = AnomalyDetector()

        # 
        import numpy as np

        np.random.seed(42)
        X_normal = np.random.normal(0, 1, (1000, 5))
        detector.train(X_normal)

        # 
        X_test_normal = np.random.normal(0, 1, (1, 5))
        result_normal = detector.detect_anomaly(X_test_normal)

        assert result_normal is not None
        assert hasattr(result_normal, "is_anomaly")

        # 
        X_test_anomaly = np.random.normal(5, 1, (1, 5))  # 
        result_anomaly = detector.detect_anomaly(X_test_anomaly)

        assert result_anomaly is not None
        assert hasattr(result_anomaly, "is_anomaly")

    def test_ensemble_model_initialization(self):
        """"""
        model = RiskEnsembleModel()

        assert model is not None
        assert model.models is not None
        assert model.model_weights is not None
        assert len(model.models) > 0
        assert not model.is_trained

    def test_ensemble_model_training(self):
        """"""
        model = RiskEnsembleModel()

        # 
        import numpy as np

        np.random.seed(42)
        X = np.random.normal(0, 1, (1000, 5))
        y = np.random.choice([0, 1], 1000)  # 

        result = model.train(X, y)

        assert result is not None
        assert model.is_trained
        assert "success" in result

    def test_ensemble_model_prediction(self):
        """"""
        model = RiskEnsembleModel()

        # 
        import numpy as np

        np.random.seed(42)
        X = np.random.normal(0, 1, (1000, 5))
        y = np.random.choice([0, 1], 1000)
        model.train(X, y)

        # 
        X_test = np.random.normal(0, 1, (10, 5))
        predictions = model.predict(X_test)
        probabilities = model.predict_proba(X_test)

        assert predictions is not None
        assert probabilities is not None
        assert len(predictions) == 10
        assert len(probabilities) == 10
        assert all(pred in [0, 1] for pred in predictions)

    def test_risk_monitoring_start_stop(self, risk_manager):
        """"""
        # 
        import asyncio

        # 
        asyncio.run(risk_manager.start_monitoring())
        assert risk_manager.is_monitoring

        # 
        time.sleep(0.2)

        # 
        asyncio.run(risk_manager.stop_monitoring())
        assert not risk_manager.is_monitoring

    def test_performance_metrics(self, risk_manager):
        """"""
        metrics = risk_manager.get_performance_metrics()

        assert metrics is not None
        assert "events_processed" in metrics
        assert "risk_assessments" in metrics
        assert "violations_detected" in metrics
        assert "average_processing_time_ms" in metrics
        assert "active_events" in metrics
        assert "cached_metrics" in metrics

    def test_integration_workflow(
        self,
        risk_manager,
        sample_account_data,
        sample_position_data,
        sample_market_data,
        sample_order_data,
    ):
        """"""
        # 1. 
        risk_metrics = risk_manager.risk_calculator.calculate_risk_metrics(
            exchange_name="BINANCE",
            account_id="test_account",
            account_data=sample_account_data,
            position_data=sample_position_data,
            market_data=sample_market_data,
        )

        # 2. 
        assessment_result = risk_manager.risk_assessor.assess_risk(risk_metrics)
        assert assessment_result is not None

        # 3. 
        order_check_result = risk_manager.check_order_risk(
            exchange_name="BINANCE", account_id="test_account", order_data=sample_order_data
        )
        assert order_check_result is not None

        # 4. 
        if assessment_result.level == "HIGH":
            event = risk_manager.create_risk_event(
                event_type=RiskEventType.MARKET_VOLATILITY_SPIKE,
                risk_level=RiskLevel.HIGH,
                title="Integration Test Event",
                description="Event created during integration test",
                exchange_name="BINANCE",
                account_id="test_account",
            )
            assert event is not None

        # 5. 
        active_events = risk_manager.get_active_events("BINANCE", "test_account")
        assert isinstance(active_events, list)

    @pytest.mark.parametrize(
        "risk_level,expected_approval",
        [
            ("LOW", True),
            ("MEDIUM", True),
            ("HIGH", True),
            ("CRITICAL", False),
        ],
    )
    def test_risk_level_approval(
        self, risk_manager, sample_order_data, risk_level, expected_approval
    ):
        """"""
        # 
        risk_metrics = RiskMetrics(
            {
                "exchange_name": "BINANCE",
                "account_id": "test_account",
                "risk_level": risk_level,
                "overall_risk_score": Decimal("0.9")
                if risk_level == "CRITICAL"
                else Decimal("0.5"),
            }
        )

        # 
        risk_manager.risk_metrics_cache["BINANCE:test_account"] = risk_metrics

        # 
        result = risk_manager.check_order_risk(
            exchange_name="BINANCE", account_id="test_account", order_data=sample_order_data
        )

        assert result is not None
        assert result["approved"] == expected_approval or result["mitigation_required"] == (
            not expected_approval
        )

    def test_error_handling(self, risk_manager):
        """"""
        # 
        result = risk_manager.check_order_risk(
            exchange_name="INVALID_EXCHANGE",
            account_id="test_account",
            order_data={"invalid": "data"},
        )

        # 
        assert result is not None
        assert "approved" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
