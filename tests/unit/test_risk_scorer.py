#!/usr/bin/env python3
"""
Unit Tests for Risk Score Calculator

Tests weighted risk scoring from multiple signals.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/matchers'))

import pytest
from risk_scorer import RiskScoreCalculator, AlertSignals, RiskScoreResult


@pytest.fixture
def calculator():
    """Create RiskScoreCalculator instance"""
    return RiskScoreCalculator()


class TestVEXOverride:
    """Test VEX override functionality"""

    def test_vex_not_affected_zeros_score(self, calculator):
        """VEX status 'not_affected' should override to risk score 0"""
        signals = AlertSignals(
            cvss_score=9.8,
            kev_listed=True,
            epss_score=0.95,
            exploit_available=True,
            dependency_depth=0,
            environment_tag='prod',
            vex_reachable=True,
            vex_status='not_affected'  # Override!
        )

        result = calculator.calculate(signals)

        assert result.risk_score == 0
        assert result.priority == 'P4'
        assert 'not_affected' in result.reasoning.lower()


class TestCriticalScenarios:
    """Test P0 (Critical) scenarios"""

    def test_worst_case_scenario(self, calculator):
        """CVSS 9.8 + KEV + Prod + Direct = P0"""
        signals = AlertSignals(
            cvss_score=9.8,
            kev_listed=True,
            epss_score=0.95,
            exploit_available=True,
            dependency_depth=0,
            environment_tag='prod',
            vex_reachable=True
        )

        result = calculator.calculate(signals)

        assert result.risk_score >= 90  # P0 threshold
        assert result.priority == 'P0'
        assert result.breakdown['exploit'] == 25  # KEV listed
        assert result.breakdown['environment'] == 15  # Prod

    def test_medium_cvss_with_kev_still_p0(self, calculator):
        """Lower CVSS (7.5) but KEV + Prod should still be P0"""
        signals = AlertSignals(
            cvss_score=7.5,
            kev_listed=True,
            epss_score=0.85,
            exploit_available=True,
            dependency_depth=0,
            environment_tag='prod',
            vex_reachable=True
        )

        result = calculator.calculate(signals)

        assert result.risk_score >= 90  # Should still be P0
        assert result.priority == 'P0'


class TestContextMatters:
    """Test that context (env, depth) matters more than CVSS alone"""

    def test_high_cvss_dev_deep_transitive(self, calculator):
        """CVSS 9.8 but dev + deep transitive = P2 (not P0)"""
        signals = AlertSignals(
            cvss_score=9.8,
            kev_listed=False,
            epss_score=0.05,
            exploit_available=False,
            dependency_depth=4,
            environment_tag='dev',
            vex_reachable=None
        )

        result = calculator.calculate(signals)

        assert result.risk_score < 70  # Should be P2, not P0/P1
        assert result.priority in ['P2', 'P3']
        assert result.breakdown['environment'] == 3  # Dev = 3 points
        assert result.breakdown['depth'] == 2  # 4+ levels = 2 points

    def test_high_cvss_prod_beats_low_cvss_dev(self, calculator):
        """CVSS 7.5 + Prod should score higher than CVSS 9.8 + Dev"""
        prod_signals = AlertSignals(
            cvss_score=7.5,
            kev_listed=False,
            epss_score=0.3,
            exploit_available=True,
            dependency_depth=1,
            environment_tag='prod',
            vex_reachable=None
        )

        dev_signals = AlertSignals(
            cvss_score=9.8,
            kev_listed=False,
            epss_score=0.05,
            exploit_available=False,
            dependency_depth=3,
            environment_tag='dev',
            vex_reachable=None
        )

        prod_result = calculator.calculate(prod_signals)
        dev_result = calculator.calculate(dev_signals)

        # Prod should score higher despite lower CVSS
        assert prod_result.risk_score > dev_result.risk_score


class TestExploitLikelihood:
    """Test exploit likelihood scoring"""

    def test_kev_listed_max_exploit_score(self, calculator):
        """KEV listed should give maximum exploit component (25)"""
        signals = AlertSignals(
            cvss_score=5.0,
            kev_listed=True,
            epss_score=0.5,
            exploit_available=False,
            dependency_depth=0,
            environment_tag='dev',
            vex_reachable=None
        )

        result = calculator.calculate(signals)

        assert result.breakdown['exploit'] == 25
        assert 'KEV' in result.reasoning

    def test_high_epss_scores_high(self, calculator):
        """EPSS >= 0.7 should score 20 points"""
        signals = AlertSignals(
            cvss_score=5.0,
            kev_listed=False,
            epss_score=0.75,
            exploit_available=False,
            dependency_depth=0,
            environment_tag='dev',
            vex_reachable=None
        )

        result = calculator.calculate(signals)

        assert result.breakdown['exploit'] == 20
        assert 'EPSS' in result.reasoning

    def test_medium_epss_scores_medium(self, calculator):
        """EPSS 0.3-0.7 should score 10 points"""
        signals = AlertSignals(
            cvss_score=5.0,
            kev_listed=False,
            epss_score=0.4,
            exploit_available=False,
            dependency_depth=0,
            environment_tag='dev',
            vex_reachable=None
        )

        result = calculator.calculate(signals)

        assert result.breakdown['exploit'] == 10

    def test_exploit_available_scores_low(self, calculator):
        """Exploit available (but low EPSS) should score 5 points"""
        signals = AlertSignals(
            cvss_score=5.0,
            kev_listed=False,
            epss_score=0.1,
            exploit_available=True,
            dependency_depth=0,
            environment_tag='dev',
            vex_reachable=None
        )

        result = calculator.calculate(signals)

        assert result.breakdown['exploit'] == 5


class TestDependencyDepth:
    """Test dependency depth scoring"""

    def test_direct_dependency_max_score(self, calculator):
        """Direct dependency (depth 0) should score 15 points"""
        signals = AlertSignals(
            cvss_score=5.0,
            kev_listed=False,
            epss_score=0.1,
            exploit_available=False,
            dependency_depth=0,
            environment_tag='dev',
            vex_reachable=None
        )

        result = calculator.calculate(signals)

        assert result.breakdown['depth'] == 15

    def test_one_level_deep(self, calculator):
        """1 level deep should score 10 points"""
        signals = AlertSignals(
            cvss_score=5.0,
            kev_listed=False,
            epss_score=0.1,
            exploit_available=False,
            dependency_depth=1,
            environment_tag='dev',
            vex_reachable=None
        )

        result = calculator.calculate(signals)

        assert result.breakdown['depth'] == 10

    def test_two_levels_deep(self, calculator):
        """2 levels deep should score 5 points"""
        signals = AlertSignals(
            cvss_score=5.0,
            kev_listed=False,
            epss_score=0.1,
            exploit_available=False,
            dependency_depth=2,
            environment_tag='dev',
            vex_reachable=None
        )

        result = calculator.calculate(signals)

        assert result.breakdown['depth'] == 5

    def test_very_deep_transitive(self, calculator):
        """3+ levels deep should score 2 points"""
        signals = AlertSignals(
            cvss_score=5.0,
            kev_listed=False,
            epss_score=0.1,
            exploit_available=False,
            dependency_depth=5,
            environment_tag='dev',
            vex_reachable=None
        )

        result = calculator.calculate(signals)

        assert result.breakdown['depth'] == 2


class TestEnvironment:
    """Test environment scoring"""

    def test_prod_max_score(self, calculator):
        """Production environment should score 15 points"""
        signals = AlertSignals(
            cvss_score=5.0,
            kev_listed=False,
            epss_score=0.1,
            exploit_available=False,
            dependency_depth=0,
            environment_tag='prod',
            vex_reachable=None
        )

        result = calculator.calculate(signals)

        assert result.breakdown['environment'] == 15

    def test_staging_medium_score(self, calculator):
        """Staging environment should score 8 points"""
        signals = AlertSignals(
            cvss_score=5.0,
            kev_listed=False,
            epss_score=0.1,
            exploit_available=False,
            dependency_depth=0,
            environment_tag='staging',
            vex_reachable=None
        )

        result = calculator.calculate(signals)

        assert result.breakdown['environment'] == 8

    def test_dev_low_score(self, calculator):
        """Dev environment should score 3 points"""
        signals = AlertSignals(
            cvss_score=5.0,
            kev_listed=False,
            epss_score=0.1,
            exploit_available=False,
            dependency_depth=0,
            environment_tag='dev',
            vex_reachable=None
        )

        result = calculator.calculate(signals)

        assert result.breakdown['environment'] == 3


class TestReachability:
    """Test VEX reachability scoring"""

    def test_vex_reachable_true_max_score(self, calculator):
        """VEX reachable=true should score 20 points"""
        signals = AlertSignals(
            cvss_score=5.0,
            kev_listed=False,
            epss_score=0.1,
            exploit_available=False,
            dependency_depth=0,
            environment_tag='dev',
            vex_reachable=True
        )

        result = calculator.calculate(signals)

        assert result.breakdown['reachability'] == 20

    def test_vex_reachable_false_low_score(self, calculator):
        """VEX reachable=false should score 5 points"""
        signals = AlertSignals(
            cvss_score=5.0,
            kev_listed=False,
            epss_score=0.1,
            exploit_available=False,
            dependency_depth=0,
            environment_tag='dev',
            vex_reachable=False
        )

        result = calculator.calculate(signals)

        assert result.breakdown['reachability'] == 5

    def test_vex_unknown_assumes_reachable(self, calculator):
        """VEX reachable=None should assume reachable (15 points)"""
        signals = AlertSignals(
            cvss_score=5.0,
            kev_listed=False,
            epss_score=0.1,
            exploit_available=False,
            dependency_depth=0,
            environment_tag='dev',
            vex_reachable=None
        )

        result = calculator.calculate(signals)

        assert result.breakdown['reachability'] == 15


class TestPriorityBands:
    """Test priority band classification"""

    def test_p0_threshold(self, calculator):
        """Score >= 90 should be P0"""
        signals = AlertSignals(
            cvss_score=10.0,  # 25 points
            kev_listed=True,  # 25 points
            epss_score=0.95,
            exploit_available=True,
            dependency_depth=0,  # 15 points
            environment_tag='prod',  # 15 points
            vex_reachable=True  # 20 points
        )

        result = calculator.calculate(signals)

        assert result.risk_score >= 90
        assert result.priority == 'P0'

    def test_p1_threshold(self, calculator):
        """Score 70-89 should be P1"""
        signals = AlertSignals(
            cvss_score=8.0,  # 20 points
            kev_listed=False,
            epss_score=0.75,  # 20 points (high EPSS)
            exploit_available=False,
            dependency_depth=0,  # 15 points
            environment_tag='prod',  # 15 points
            vex_reachable=None  # 15 points
        )

        result = calculator.calculate(signals)

        assert 70 <= result.risk_score < 90
        assert result.priority == 'P1'

    def test_p2_threshold(self, calculator):
        """Score 40-69 should be P2"""
        signals = AlertSignals(
            cvss_score=6.0,  # 15 points
            kev_listed=False,
            epss_score=0.4,  # 10 points (medium EPSS)
            exploit_available=False,
            dependency_depth=1,  # 10 points
            environment_tag='staging',  # 8 points
            vex_reachable=None  # 15 points
        )

        result = calculator.calculate(signals)

        assert 40 <= result.risk_score < 70
        assert result.priority == 'P2'

    def test_p3_threshold(self, calculator):
        """Score 20-39 should be P3"""
        signals = AlertSignals(
            cvss_score=4.0,  # 10 points
            kev_listed=False,
            epss_score=0.1,  # 0 points
            exploit_available=False,
            dependency_depth=2,  # 5 points
            environment_tag='dev',  # 3 points
            vex_reachable=None  # 15 points
        )

        result = calculator.calculate(signals)

        assert 20 <= result.risk_score < 40
        assert result.priority == 'P3'

    def test_p4_threshold(self, calculator):
        """Score < 20 should be P4"""
        signals = AlertSignals(
            cvss_score=2.0,  # 5 points
            kev_listed=False,
            epss_score=0.01,  # 0 points
            exploit_available=False,
            dependency_depth=4,  # 2 points
            environment_tag='dev',  # 3 points
            vex_reachable=False  # 5 points
        )

        result = calculator.calculate(signals)

        assert result.risk_score < 20
        assert result.priority == 'P4'


class TestReasoning:
    """Test that reasoning is generated"""

    def test_reasoning_includes_all_signals(self, calculator):
        """Reasoning should include all signal types"""
        signals = AlertSignals(
            cvss_score=7.5,
            kev_listed=True,
            epss_score=0.85,
            exploit_available=True,
            dependency_depth=0,
            environment_tag='prod',
            vex_reachable=True
        )

        result = calculator.calculate(signals)

        reasoning = result.reasoning.lower()
        assert 'cvss' in reasoning
        assert 'kev' in reasoning or 'exploit' in reasoning
        assert 'direct' in reasoning or 'dependency' in reasoning
        assert 'prod' in reasoning or 'environment' in reasoning
        assert 'reachable' in reasoning or 'vex' in reasoning


class TestBatchProcessing:
    """Test batch calculation"""

    def test_calculate_batch(self, calculator):
        """Should calculate risk scores for multiple signals"""
        signals_list = [
            AlertSignals(
                cvss_score=9.8,
                kev_listed=True,
                epss_score=0.95,
                exploit_available=True,
                dependency_depth=0,
                environment_tag='prod',
                vex_reachable=True
            ),
            AlertSignals(
                cvss_score=5.0,
                kev_listed=False,
                epss_score=0.1,
                exploit_available=False,
                dependency_depth=3,
                environment_tag='dev',
                vex_reachable=None
            )
        ]

        results = calculator.calculate_batch(signals_list)

        assert len(results) == 2
        assert results[0].risk_score > results[1].risk_score  # First is higher risk
        assert results[0].priority == 'P0'
        assert results[1].priority in ['P3', 'P4']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
