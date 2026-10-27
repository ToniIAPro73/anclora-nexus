from typing import List

from fastapi import HTTPException, status

from backend.models.deal_margin import (
    CompareRequest,
    CompareResponse,
    MarginAssumptions,
    MarginDriver,
    ScopeMetadata,
    SimulationRequest,
    SimulationResponse,
    SimulationResult,
)
from backend.models.membership import UserRole
from backend.services.neon_service import neon_service


class DealMarginService:
    def __init__(self) -> None:
        self.client = neon_service.client

    async def _get_role(self, org_id: str, user_id: str) -> str:
        try:
            result = (
                self.client.table("organization_members")
                .select("role,status")
                .eq("org_id", org_id)
                .eq("user_id", user_id)
                .eq("status", "active")
                .limit(1)
                .execute()
            )
            if result.data:
                return str(result.data[0].get("role") or UserRole.AGENT.value)
        except Exception:
            pass
        return UserRole.OWNER.value

    def _band(self, expected_margin_eur: float, expected_margin_pct: float) -> str:
        if expected_margin_eur >= 150000 and expected_margin_pct >= 18:
            return "A"
        if expected_margin_eur >= 70000 and expected_margin_pct >= 12:
            return "B"
        if expected_margin_eur >= 25000 and expected_margin_pct >= 7:
            return "C"
        return "D"

    def _simulate(self, assumptions: MarginAssumptions, scenario_name: str) -> SimulationResult:
        total_cost = (
            assumptions.acquisition_cost_eur
            + assumptions.closing_cost_eur
            + assumptions.renovation_cost_eur
            + assumptions.holding_cost_eur
            + assumptions.tax_cost_eur
        )
        gross_margin_eur = assumptions.deal_value_eur - total_cost
        gross_margin_pct = (gross_margin_eur / assumptions.deal_value_eur * 100) if assumptions.deal_value_eur > 0 else 0
        expected_commission_eur = assumptions.deal_value_eur * (assumptions.commission_rate_pct / 100)
        expected_margin_eur = gross_margin_eur * (assumptions.confidence_pct / 100)
        expected_margin_pct = gross_margin_pct * (assumptions.confidence_pct / 100)
        band = self._band(expected_margin_eur=expected_margin_eur, expected_margin_pct=expected_margin_pct)

        drivers: List[MarginDriver] = [
            MarginDriver(label="deal_value_eur", value_eur=round(assumptions.deal_value_eur, 2)),
            MarginDriver(label="acquisition_cost_eur", value_eur=round(assumptions.acquisition_cost_eur, 2)),
            MarginDriver(label="operational_costs_eur", value_eur=round(
                assumptions.closing_cost_eur + assumptions.renovation_cost_eur + assumptions.holding_cost_eur + assumptions.tax_cost_eur,
                2,
            )),
            MarginDriver(label="confidence_impact_eur", value_eur=round(gross_margin_eur - expected_margin_eur, 2)),
        ]

        return SimulationResult(
            scenario_name=scenario_name,
            gross_margin_eur=round(gross_margin_eur, 2),
            gross_margin_pct=round(gross_margin_pct, 2),
            expected_commission_eur=round(expected_commission_eur, 2),
            expected_margin_eur=round(expected_margin_eur, 2),
            recommendation_band=band,
            drivers=drivers,
        )

    async def simulate(self, org_id: str, user_id: str, payload: SimulationRequest) -> SimulationResponse:
        role = await self._get_role(org_id, user_id)
        scenario_name = payload.scenario_name or "scenario_base"
        result = self._simulate(payload.assumptions, scenario_name)

        try:
            await neon_service.insert_audit_log(
                {
                    "org_id": org_id,
                    "entity_type": "deal_margin_simulation",
                    "entity_id": scenario_name,
                    "action": "simulate",
                    "actor_user_id": user_id,
                    "details": {
                        "band": result.recommendation_band,
                        "expected_margin_eur": result.expected_margin_eur,
                    },
                }
            )
        except Exception:
            pass

        return SimulationResponse(scope=ScopeMetadata(org_id=org_id, role=role), result=result)

    async def compare(self, org_id: str, user_id: str, payload: CompareRequest) -> CompareResponse:
        role = await self._get_role(org_id, user_id)
        results: List[SimulationResult] = []
        for idx, scenario in enumerate(payload.scenarios, start=1):
            name = scenario.scenario_name or f"scenario_{idx}"
            results.append(self._simulate(scenario.assumptions, name))

        best = max(results, key=lambda r: r.expected_margin_eur)

        try:
            await neon_service.insert_audit_log(
                {
                    "org_id": org_id,
                    "entity_type": "deal_margin_simulation",
                    "entity_id": "compare",
                    "action": "compare",
                    "actor_user_id": user_id,
                    "details": {
                        "best_scenario": best.scenario_name,
                        "best_expected_margin_eur": best.expected_margin_eur,
                    },
                }
            )
        except Exception:
            pass

        return CompareResponse(
            scope=ScopeMetadata(org_id=org_id, role=role),
            results=results,
            best_scenario=best.scenario_name,
        )


deal_margin_service = DealMarginService()
