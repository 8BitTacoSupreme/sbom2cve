#!/usr/bin/env python3
"""
Risk Scoring Calculator

Calculates weighted risk scores (0-100) from multiple signals:
- CVSS Score (25%)
- Exploit Likelihood - KEV/EPSS (25%)
- Dependency Depth (15%)
- Environment (15%)
- Reachability - VEX (20%)

This enables auto-prioritization in FloxHub UI, moving beyond CVSS-only sorting.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class AlertSignals:
    """Input signals for risk scoring"""
    cvss_score: float  # 0.0-10.0
    kev_listed: bool  # CISA Known Exploited Vulnerability
    epss_score: float  # 0.0-1.0 Exploit Prediction Scoring System
    exploit_available: bool  # Public exploit code exists
    dependency_depth: int  # 0 = direct, 1+ = transitive
    environment_tag: str  # 'prod', 'staging', 'dev'
    vex_reachable: Optional[bool] = None  # None = unknown, True = reachable, False = not reachable
    vex_status: Optional[str] = None  # 'not_affected', 'affected', 'fixed', 'under_investigation'


@dataclass
class RiskScoreResult:
    """Output of risk scoring"""
    risk_score: int  # 0-100
    breakdown: Dict[str, int]  # Component scores
    priority: str  # P0, P1, P2, P3, P4
    reasoning: str  # Human-readable explanation


class RiskScoreCalculator:
    """
    Calculate weighted risk score from multiple signals.

    Weight Distribution:
      - CVSS: 25% (base severity)
      - Exploit Likelihood: 25% (KEV > EPSS > exploit available)
      - Dependency Depth: 15% (direct > transitive)
      - Environment: 15% (prod > staging > dev)
      - Reachability: 20% (VEX reachable > unknown > not reachable)

    Example Scenarios:
      1. CVSS 9.8, KEV listed, Direct dep, Prod → Risk Score: 100, P0
      2. CVSS 9.8, No exploit, Depth 4, Dev → Risk Score: 45, P2
      3. CVSS 7.5, EPSS 0.8, Direct, Staging → Risk Score: 72, P1
    """

    def calculate(self, signals: AlertSignals) -> RiskScoreResult:
        """
        Calculate risk score and priority.

        Args:
            signals: Input signals from CVE, SBOM, KEV, VEX

        Returns:
            RiskScoreResult with score, breakdown, priority, reasoning
        """

        # VEX override: not_affected = 0 score
        if signals.vex_status == 'not_affected':
            return RiskScoreResult(
                risk_score=0,
                breakdown={'vex_override': 0},
                priority='P4',
                reasoning='VEX statement: not_affected (vulnerability does not apply to this package)'
            )

        # Signal 1: CVSS (25%)
        cvss_component = (signals.cvss_score / 10.0) * 25

        # Signal 2: Exploit Likelihood (25%)
        if signals.kev_listed:
            exploit_component = 25  # Known active exploitation in the wild
            exploit_reason = 'CISA KEV listed (active exploitation)'
        elif signals.epss_score >= 0.7:
            exploit_component = 20  # High EPSS (70%+ probability)
            exploit_reason = f'High EPSS score ({signals.epss_score:.2f})'
        elif signals.epss_score >= 0.3:
            exploit_component = 10  # Medium EPSS (30-70%)
            exploit_reason = f'Medium EPSS score ({signals.epss_score:.2f})'
        elif signals.exploit_available:
            exploit_component = 5   # Public exploit code exists
            exploit_reason = 'Public exploit code available'
        else:
            exploit_component = 0
            exploit_reason = 'No known exploitation'

        # Signal 3: Dependency Depth (15%)
        depth_map = {
            0: 15,  # Direct dependency
            1: 10,  # 1 level deep
            2: 5    # 2 levels deep
        }
        depth_component = depth_map.get(signals.dependency_depth, 2)  # 3+ levels = 2 points

        if signals.dependency_depth == 0:
            depth_reason = 'Direct dependency'
        elif signals.dependency_depth == 1:
            depth_reason = '1 level deep (transitive)'
        else:
            depth_reason = f'{signals.dependency_depth} levels deep (transitive)'

        # Signal 4: Environment (15%)
        env_map = {
            'prod': 15,
            'production': 15,
            'staging': 8,
            'dev': 3,
            'development': 3,
            'test': 3
        }
        env_component = env_map.get(signals.environment_tag.lower(), 3)
        env_reason = f"Environment: {signals.environment_tag}"

        # Signal 5: Reachability/VEX (20%)
        if signals.vex_reachable is True:
            reachability_component = 20
            reach_reason = 'VEX: Code path is reachable'
        elif signals.vex_reachable is False:
            reachability_component = 5
            reach_reason = 'VEX: Vulnerable code not reachable'
        else:
            reachability_component = 15  # Assume reachable when unknown
            reach_reason = 'Reachability unknown (assumed reachable)'

        # Calculate total score
        total = int(
            cvss_component +
            exploit_component +
            depth_component +
            env_component +
            reachability_component
        )

        # Clamp to 0-100
        risk_score = min(max(total, 0), 100)

        # Determine priority
        priority = self._calculate_priority(risk_score)

        # Build reasoning
        reasoning_parts = [
            f"CVSS {signals.cvss_score}/10.0",
            exploit_reason,
            depth_reason,
            env_reason,
            reach_reason
        ]
        reasoning = ' | '.join(reasoning_parts)

        return RiskScoreResult(
            risk_score=risk_score,
            breakdown={
                'cvss': int(cvss_component),
                'exploit': exploit_component,
                'depth': depth_component,
                'environment': env_component,
                'reachability': reachability_component
            },
            priority=priority,
            reasoning=reasoning
        )

    def _calculate_priority(self, score: int) -> str:
        """
        Map risk score to priority level.

        P0 (Critical): 90-100 - Immediate action required
        P1 (High): 70-89 - Urgent, fix within days
        P2 (Medium): 40-69 - Important, fix within weeks
        P3 (Low): 20-39 - Nice to fix, lower urgency
        P4 (Informational): 0-19 - Informational only
        """
        if score >= 90:
            return 'P0'  # Critical
        if score >= 70:
            return 'P1'  # High
        if score >= 40:
            return 'P2'  # Medium
        if score >= 20:
            return 'P3'  # Low
        return 'P4'  # Informational

    def calculate_batch(self, signals_list: list) -> list:
        """Calculate risk scores for multiple alerts"""
        return [self.calculate(signals) for signals in signals_list]


def compare_scenarios():
    """
    Compare risk scores across different scenarios.
    Demonstrates that context matters more than CVSS alone.
    """
    calculator = RiskScoreCalculator()

    scenarios = [
        {
            'name': 'Worst Case: Prod + KEV + Direct',
            'signals': AlertSignals(
                cvss_score=9.8,
                kev_listed=True,
                epss_score=0.95,
                exploit_available=True,
                dependency_depth=0,
                environment_tag='prod',
                vex_reachable=True
            )
        },
        {
            'name': 'High CVSS but Deep Transitive in Dev',
            'signals': AlertSignals(
                cvss_score=9.8,
                kev_listed=False,
                epss_score=0.05,
                exploit_available=False,
                dependency_depth=4,
                environment_tag='dev',
                vex_reachable=None
            )
        },
        {
            'name': 'Medium CVSS but Active Exploitation in Prod',
            'signals': AlertSignals(
                cvss_score=7.5,
                kev_listed=True,
                epss_score=0.85,
                exploit_available=True,
                dependency_depth=0,
                environment_tag='prod',
                vex_reachable=True
            )
        },
        {
            'name': 'High CVSS but VEX Not Affected',
            'signals': AlertSignals(
                cvss_score=9.8,
                kev_listed=True,
                epss_score=0.95,
                exploit_available=True,
                dependency_depth=0,
                environment_tag='prod',
                vex_status='not_affected'
            )
        },
        {
            'name': 'Moderate Everything',
            'signals': AlertSignals(
                cvss_score=6.5,
                kev_listed=False,
                epss_score=0.4,
                exploit_available=True,
                dependency_depth=1,
                environment_tag='staging',
                vex_reachable=None
            )
        }
    ]

    print("=" * 80)
    print("Risk Score Comparison Scenarios")
    print("=" * 80)

    for scenario in scenarios:
        result = calculator.calculate(scenario['signals'])
        print(f"\n📊 {scenario['name']}")
        print(f"   Risk Score: {result.risk_score}/100 ({result.priority})")
        print(f"   Breakdown: {result.breakdown}")
        print(f"   Reasoning: {result.reasoning}")

    print("\n" + "=" * 80)
    print("Key Insight: Risk score considers exploit likelihood + environment + depth,")
    print("             not just CVSS. This prevents alert fatigue.")
    print("=" * 80)


if __name__ == '__main__':
    compare_scenarios()
