from pydantic import BaseModel, Field, model_validator
from typing import Optional, Dict, List, Any, Literal

from .constants import (
    KD_MIN, KD_MAX, KW_MIN, KW_MAX, KP_MIN, KP_MAX,
    Z_MIN, Z_MAX, K_MIN, K_MAX, F_FACTOR_MIN, F_FACTOR_MAX,
)


# =============================================================================
# Input Models
# =============================================================================

class LiquidReliefInput(BaseModel):
    q_gpm: float = Field(gt=0, description="Flow rate (US GPM)")
    p1_psia: float = Field(gt=0, description="Relieving pressure (psia)")
    p2_psia: float = Field(gt=0, description="Total back pressure (psia)")
    g: float = Field(gt=0, description="Specific gravity")
    mu_cp: float = Field(default=1.0, gt=0, description="Viscosity (cP)")
    kd: Optional[float] = Field(default=None, ge=KD_MIN, le=KD_MAX, description="Discharge coefficient (0.65 certified / 0.62 noncertified if None)")
    kw: Optional[float] = Field(default=None, ge=KW_MIN, le=KW_MAX, description="Back pressure capacity correction (auto if None)")
    kc: float = Field(default=1.0, ge=0.1, le=1.0, description="Combination correction factor (rupture disk)")
    num_valves: int = Field(default=1, ge=1, le=100, description="Number of parallel valves")
    valve_type: Literal["conventional", "balanced_bellows", "pilot"] = Field(default="conventional", description="Valve type")
    overpressure_pct: float = Field(default=10.0, ge=1.0, le=50.0, description="Percent overpressure")
    capacity_certified: bool = Field(default=True, description="Capacity certified for liquid service per API 520 Part I 5.8")
    set_pressure_psig: Optional[float] = Field(default=None, gt=0, description="Set pressure for Kw/Kp reference")

    @model_validator(mode="after")
    def _check_relations(self):
        if self.p2_psia >= self.p1_psia:
            raise ValueError("p2_psia must be less than p1_psia")
        return self


class GasReliefInput(BaseModel):
    w_lb_h: float = Field(gt=0, description="Mass flow rate (lb/h)")
    p1_psia: float = Field(gt=0, description="Relieving pressure (psia)")
    p2_psia: float = Field(ge=0, description="Back pressure (psia)")
    t_rankine: float = Field(gt=0, description="Relieving temperature (Rankine)")
    z: float = Field(default=1.0, ge=Z_MIN, le=Z_MAX, description="Compressibility factor")
    mw: float = Field(gt=0, description="Molecular weight")
    k: float = Field(ge=K_MIN, le=K_MAX, description="Specific heat ratio (Cp/Cv)")
    kd: float = Field(default=0.975, ge=KD_MIN, le=KD_MAX, description="Discharge coefficient")
    kb: Optional[float] = Field(None, description="Back pressure correction (auto if None)")
    kc: float = Field(default=1.0, ge=0.1, le=1.0, description="Combination correction factor")
    num_valves: int = Field(default=1, ge=1, le=100, description="Number of parallel valves")
    valve_type: Literal["conventional", "balanced_bellows", "pilot"] = Field(default="conventional")
    set_pressure_psig: Optional[float] = Field(None, gt=0, description="Set pressure for Kb calculation")
    overpressure_pct: float = Field(default=10.0, ge=1.0, le=50.0, description="Percent overpressure")
    is_steam: bool = Field(default=False, description="Use Napier steam formula")
    use_napier: bool = Field(default=False, description="Use Napier as primary sizing method")

    @model_validator(mode="after")
    def _check_relations(self):
        if self.p2_psia >= self.p1_psia:
            raise ValueError("p2_psia must be less than p1_psia")
        if self.use_napier and not self.is_steam:
            raise ValueError("use_napier requires is_steam=True")
        return self


class TwoPhaseInput(BaseModel):
    w_lb_h: float = Field(gt=0, description="Mass flow rate (lb/h)")
    p0_psia: float = Field(gt=0, description="Stagnation relieving pressure (psia)")
    p_back_psia: float = Field(ge=0, description="Back pressure (psia)")
    v0_ft3_lb: float = Field(gt=0, description="Specific volume at inlet (ft3/lb)")
    v9_ft3_lb: Optional[float] = Field(None, gt=0, description="Specific vol at 90% P0 (ft3/lb), from an isentropic flash")
    omega: Optional[float] = Field(None, ge=0.01, description="Omega parameter (calc from v0/v9 if None)")
    kd: float = Field(default=0.85, ge=KD_MIN, le=KD_MAX, description="Discharge coefficient")
    kb: Optional[float] = Field(None, ge=KW_MIN, le=KW_MAX, description="Back pressure correction (balanced bellows)")
    kc: float = Field(default=1.0, ge=0.1, le=1.0, description="Combination correction factor")
    num_valves: int = Field(default=1, ge=1, le=100)
    valve_type: Literal["conventional", "balanced_bellows", "pilot"] = Field(default="conventional")
    set_pressure_psig: Optional[float] = Field(None, gt=0)
    overpressure_pct: float = Field(default=10.0, ge=1.0, le=50.0)

    @model_validator(mode="after")
    def _check_relations(self):
        if self.p_back_psia >= self.p0_psia:
            raise ValueError("p_back_psia must be less than p0_psia")
        if self.omega is None and self.v9_ft3_lb is None:
            raise ValueError("Either omega or v9_ft3_lb must be provided")
        return self


class FireWettedInput(BaseModel):
    a_wetted_sqft: float = Field(gt=0, description="Wetted surface area (sqft)")
    f_factor: float = Field(default=1.0, ge=F_FACTOR_MIN, le=F_FACTOR_MAX, description="Environment factor")
    heat_of_vap_btu_lb: float = Field(gt=0, description="Latent heat of vaporization (Btu/lb)")
    p1_psia: float = Field(gt=0, description="Relieving pressure (psia)")
    p2_psia: float = Field(default=14.6959, ge=0, description="Back pressure (psia)")
    t_rankine: float = Field(gt=0, description="Gas temperature (Rankine)")
    z: float = Field(default=0.9, ge=Z_MIN, le=Z_MAX, description="Compressibility")
    mw: float = Field(gt=0, description="Molecular weight")
    k: float = Field(ge=K_MIN, le=K_MAX, description="Specific heat ratio")
    adequate_drainage: bool = Field(default=False, description="Prompt firefighting and adequate drainage per API 521 4.4.13.2.4.2")

    @model_validator(mode="after")
    def _check_relations(self):
        if self.p2_psia >= self.p1_psia:
            raise ValueError("p2_psia must be less than p1_psia")
        return self


class FireUnwettedInput(BaseModel):
    a_exposed_sqft: float = Field(gt=0, description="Exposed area (sqft)")
    p1_psia: float = Field(gt=0, description="Relieving pressure (psia)")
    t_gas_rankine: float = Field(gt=0, description="Gas temperature (Rankine)")
    t_wall_rankine: float = Field(gt=0, description="Wall temperature (Rankine)")
    k: float = Field(ge=K_MIN, le=K_MAX, description="Specific heat ratio")
    kd: float = Field(default=0.975, ge=KD_MIN, le=KD_MAX, description="Discharge coefficient")

    @model_validator(mode="after")
    def _check_relations(self):
        if self.t_wall_rankine <= self.t_gas_rankine:
            raise ValueError("t_wall_rankine must be greater than t_gas_rankine")
        return self


class ThermalExpansionInput(BaseModel):
    b_expansion_coeff: float = Field(gt=0, description="Cubical expansion coefficient (1/°F)")
    h_heat_transfer_btu_h: float = Field(gt=0, description="Heat transfer rate (BTU/h)")
    g_specific_gravity: float = Field(gt=0, description="Specific gravity")
    c_specific_heat: float = Field(gt=0, description="Specific heat (BTU/lb°F)")
    mu_cp: float = Field(default=1.0, gt=0, description="Viscosity (cP)")
    p1_psia: float = Field(gt=0, description="Relieving pressure (psia)")
    p2_psia: float = Field(gt=0, description="Back pressure (psia)")
    num_valves: int = Field(default=1, ge=1, le=100, description="Number of parallel valves")
    valve_type: Literal["conventional", "balanced_bellows", "pilot"] = Field(default="conventional", description="Valve type")
    capacity_certified: bool = Field(default=True, description="Capacity certified for liquid service per API 520 Part I 5.8")

    @model_validator(mode="after")
    def _check_relations(self):
        if self.p2_psia >= self.p1_psia:
            raise ValueError("p2_psia must be less than p1_psia")
        return self


class PipingInletInput(BaseModel):
    flow_gpm: Optional[float] = Field(None, ge=0, description="Volumetric flow (US GPM)")
    flow_rate_lb_h: Optional[float] = Field(None, gt=0, description="Mass flow (lb/h)")
    fluid_density_lb_ft3: float = Field(gt=0, description="Fluid density (lb/ft3)")
    viscosity_cp: float = Field(gt=0, description="Fluid viscosity (cP)")
    pipe_id_in: float = Field(gt=0, description="Pipe inner diameter (inches)")
    pipe_length_ft: float = Field(ge=0, description="Straight pipe length (ft)")
    set_pressure_psig: float = Field(gt=0, description="Valve set pressure (psig)")
    fittings_90deg: int = Field(default=0, ge=0, description="Number of 90° elbows")
    fittings_45deg: int = Field(default=0, ge=0, description="Number of 45° elbows")
    gate_valves: int = Field(default=0, ge=0, description="Number of gate valves")
    roughness_in: float = Field(default=0.00015, ge=0, description="Pipe roughness (inches)")
    valve_type: Literal["conventional", "pilot"] = Field(default="conventional")
    remote_sensing: bool = Field(default=False, description="Remote sensing line for pilot valve")

    @model_validator(mode="after")
    def _check_relations(self):
        if (self.flow_gpm is None or self.flow_gpm <= 0) and (self.flow_rate_lb_h is None or self.flow_rate_lb_h <= 0):
            raise ValueError("Either flow_gpm or flow_rate_lb_h must be provided")
        return self


class ConvertInput(BaseModel):
    value: float
    from_unit: str
    to_unit: str


class TwoPhaseSubcooledInput(BaseModel):
    q_gpm: float = Field(gt=0, description="Relieving volume flow rate (US gpm)")
    p1_psia: float = Field(gt=0, description="Upstream relieving pressure (psia)")
    p2_psia: float = Field(ge=0, description="Downstream backpressure (psia)")
    ps_psia: float = Field(gt=0, description="Saturation (bubble) pressure at relieving temperature (psia)")
    rho1_lb_ft3: float = Field(gt=0, description="Liquid density at relieving conditions (lb/ft3)")
    rho9_lb_ft3: float = Field(gt=0, description="Overall density at 90% of Ps (lb/ft3)")
    kd: float = Field(default=0.65, ge=KD_MIN, le=KD_MAX, description="Discharge coefficient (0.65 subcooled)")
    kb: Optional[float] = Field(None, ge=KW_MIN, le=KW_MAX, description="Back pressure correction (1.0 if None)")
    kc: float = Field(default=1.0, ge=0.1, le=1.0, description="Combination correction factor")
    num_valves: int = Field(default=1, ge=1, le=100)
    valve_type: Literal["conventional", "balanced_bellows", "pilot"] = Field(default="conventional")

    @model_validator(mode="after")
    def _check_relations(self):
        if self.p2_psia >= self.p1_psia:
            raise ValueError("p2_psia must be less than p1_psia")
        if self.ps_psia >= self.p1_psia:
            raise ValueError("ps_psia must be strictly less than p1_psia for subcooled service.")
        if self.rho9_lb_ft3 > self.rho1_lb_ft3:
            raise ValueError("rho9_lb_ft3 must be <= rho1_lb_ft3 (flashing cannot increase density).")
        return self


# =============================================================================
# Output Models
# =============================================================================

class ReliefOutput(BaseModel):
    Required_Area_sqin: float
    Selected_Orifice_Letter: str
    Selected_Orifice_Area_sqin: float
    Num_Valves: int = 1


class LiquidReliefOutput(ReliefOutput):
    Required_Area_No_Visc_sqin: float
    Reynolds_Number: float
    Kv: float
    Kp: float
    Overpressure_Pct: float
    Method: str = "certified"


class GasReliefOutput(ReliefOutput):
    Flow_Type: str
    Critical_Pressure_psia: float
    C_Coefficient: Optional[float] = None
    F2_Coefficient: Optional[float] = None
    Kb_Factor: float = 1.0


class TwoPhaseOutput(ReliefOutput):
    Omega: float
    Critical_Pressure_Ratio_hc: float
    Critical_Pressure_psia: float
    Flow_Type: str
    Mass_Flux_G_lb_s_ft2: float
    Kb: float = 1.0


class FireWettedOutput(BaseModel):
    Heat_Absorption_Btu_h: float
    Relief_Load_lb_h: float
    Required_Area_sqin: float
    Selected_Orifice_Letter: str
    Selected_Orifice_Area_sqin: float
    Flow_Type: str
    C_Coefficient: Optional[float] = None
    Kb_Factor: float = 1.0


class PipingOutput(BaseModel):
    delta_p_psi: float
    velocity_fps: float
    reynolds: float
    friction_factor: float
    equivalent_length_ft: float
    flow_gpm: Optional[float] = None
    flow_rate_lb_h: Optional[float] = None
    api_520_rule_pass: bool
    delta_p_pct_of_set: float
    limit_pct: float


class HealthOutput(BaseModel):
    status: str
    units_backend: str


__all__ = [
    "LiquidReliefInput", "GasReliefInput", "TwoPhaseInput",
    "FireWettedInput", "FireUnwettedInput", "ThermalExpansionInput",
    "PipingInletInput", "ConvertInput", "TwoPhaseSubcooledInput",
    "ReliefOutput", "LiquidReliefOutput", "GasReliefOutput",
    "TwoPhaseOutput", "FireWettedOutput", "PipingOutput", "HealthOutput",
]
