"""
OrbitIQ Digital Twin Engine

Pipeline:
    Controlled EMC multi-satellite geometry
        -> moving satellite-fixed beam footprints
        -> RF/serviceability calculation
        -> OrbitIQ LHT handover logic
        -> dashboard-ready UE and beam DataFrames

"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import importlib.util
import sys

import numpy as np
import pandas as pd


def _load_core(core_path: str | None = None):
    """
    Load the EMC simulator module.

    By default, this expects `ntn_beam_calibration_multisat.py` to be in the
    same folder as this engine file. You can also pass an explicit `core_path`.
    """
    if core_path is None:
        core_path = Path(__file__).with_name("ntn_beam_calibration_multisat.py")
    else:
        core_path = Path(core_path)

    if not core_path.exists():
        raise FileNotFoundError(
            f"Cannot find EMC simulator core at: {core_path}. "
            "Put ntn_beam_calibration_multisat.py in the same folder as "
            "orbitiq_digital_twin_engine.py, or pass core_path explicitly."
        )

    module_name = "ntn_beam_calibration_multisat_runtime"

    spec = importlib.util.spec_from_file_location(module_name, core_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec from {core_path}")

    core = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = core
    spec.loader.exec_module(core)
    return core


def _ecef_to_lat_lon(v):
    """
    Convert an ECEF-like Earth-centered vector to latitude/longitude degrees.

    The core simulator uses spherical Earth coordinates, so this conversion is
    sufficient for dashboard visualization.
    """
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    if n <= 0:
        return np.nan, np.nan

    x, y, z = v / n
    lat = np.degrees(np.arcsin(np.clip(z, -1.0, 1.0)))
    lon = np.degrees(np.arctan2(y, x))
    return float(lat), float(lon)


def make_args(
    # RF / orbit
    freq_mhz=2000.0,
    bandwidth_mhz=10.0,
    altitude_km=600.0,
    inclination_deg=20.0,
    duration_s=120.0,
    step_s=1.0,

    # RF options
    reuse_one=False,
    no_fading=True,

    # EMC / handover options
    use_moving_refs=True,
    d2_cho=True,
    d2_t1_km=160.0,
    d2_t2_km=140.0,
    d2_hysteresis_km=10.0,
    d2_neighbor_sinr_db=0.0,

    prediction_horizon_s=60.0,
    prediction_step_s=10.0,
    future_sinr_margin_db=3.0,
    ho_penalty_db=1.0,
    outage_penalty_db=10.0,
    min_predicted_sinr_db=0.0,

    # OrbitIQ LHT parameters
    lht_cell_radius_km=25.0,
    lht_inner_epsilon_km=2.0,
    lht_outer_epsilon_km=2.0,
    lht_ho_margin_db=0.0,
    lht_ttt_s=0.0,
    lht_openalty_db=1e6,
    lht_gamma_scale_db=1.0,
    lht_gamma_min_db=-3.0,
    lht_gamma_max_db=3.0,
    lht_min_delta_km=1e-6,

    # Constellation
    num_sats=3,
    sat_spacing_s=60.0,

    tle_file=None,
    start_utc="now",
    demo_center_lat=52.0,
    demo_center_lon=-72.0,
    ue_count=100,
    ue_radius_km=25.0,
    min_elevation_deg=15.0,
):
    """
    Create an argparse-like namespace for `ntn_beam_calibration_multisat.run()`.

    This function intentionally accepts some legacy Starlink/TLE arguments for
    compatibility with the previous dashboard. They are not used by the EMC core.
    """
    return SimpleNamespace(
        freq_mhz=float(freq_mhz),
        bandwidth_mhz=float(bandwidth_mhz),
        altitude_km=float(altitude_km),
        inclination_deg=float(inclination_deg),
        duration_s=float(duration_s),
        step_s=float(step_s),

        reuse_one=bool(reuse_one),
        no_fading=bool(no_fading),
        use_moving_refs=bool(use_moving_refs),
        d2_cho=bool(d2_cho),

        d2_t1_km=float(d2_t1_km),
        d2_t2_km=float(d2_t2_km),
        d2_hysteresis_km=float(d2_hysteresis_km),
        d2_neighbor_sinr_db=float(d2_neighbor_sinr_db),

        prediction_horizon_s=float(prediction_horizon_s),
        prediction_step_s=float(prediction_step_s),
        future_sinr_margin_db=float(future_sinr_margin_db),
        ho_penalty_db=float(ho_penalty_db),
        outage_penalty_db=float(outage_penalty_db),
        min_predicted_sinr_db=float(min_predicted_sinr_db),

        lht_cell_radius_km=float(lht_cell_radius_km),
        lht_inner_epsilon_km=float(lht_inner_epsilon_km),
        lht_outer_epsilon_km=float(lht_outer_epsilon_km),
        lht_ho_margin_db=float(lht_ho_margin_db),
        lht_ttt_s=float(lht_ttt_s),
        lht_openalty_db=float(lht_openalty_db),
        lht_gamma_scale_db=float(lht_gamma_scale_db),
        lht_gamma_min_db=float(lht_gamma_min_db),
        lht_gamma_max_db=float(lht_gamma_max_db),
        lht_min_delta_km=float(lht_min_delta_km),

        num_sats=int(num_sats),
        sat_spacing_s=float(sat_spacing_s),

        # Legacy fields; harmless if app.py expects them to exist.
        tle_file=tle_file,
        start_utc=start_utc,
        demo_center_lat=float(demo_center_lat),
        demo_center_lon=float(demo_center_lon),
        ue_count=int(ue_count),
        ue_radius_km=float(ue_radius_km),
        min_elevation_deg=float(min_elevation_deg),
    )


def _build_beam_df(core, args):
    """
    Recompute satellite/beam footprint states for dashboard map layers.
    """
    beam_local_dirs = core.init_emc_beam_local_directions()
    times = np.arange(0, args.duration_s + 1e-9, args.step_s)

    rows = []
    for t in times:
        candidates = core.constellation_candidates(t, args, beam_local_dirs)

        for cid, item in candidates.items():
            beam_lat, beam_lon = _ecef_to_lat_lon(item["ref"])
            sat_lat, sat_lon = _ecef_to_lat_lon(item["sat"])

            rows.append({
                "time_s": float(t),
                "satellite_id": item["sat_id"],
                "beam_id": item["beam_id"],
                "candidate_id": cid,
                "serving_beam": cid,

                # Generic names commonly used by dashboard code
                "beam_lat": beam_lat,
                "beam_lon": beam_lon,
                "sat_lat": sat_lat,
                "sat_lon": sat_lon,

                # Explicit serving-style names for easy merge/plotting
                "serving_beam_lat": beam_lat,
                "serving_beam_lon": beam_lon,
                "serving_sat_lat": sat_lat,
                "serving_sat_lon": sat_lon,
            })

    return pd.DataFrame(rows)


def _prepare_ue_df(df: pd.DataFrame, beam_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add dashboard-friendly lat/lon columns and merge serving satellite/beam
    footprint coordinates into the UE time-series.

    Important integration note:
    Some versions of ntn_beam_calibration_multisat.py return raw UE
    coordinates as ue_x/ue_y/ue_z. The current cleaned EMC/Aalborg version
    returns UE-level KPIs but not the raw UE coordinates. In that case, this
    wrapper reconstructs stable dashboard UE positions from each UE's
    initial home_beam footprint at t=0 and adds a deterministic small jitter
    so users do not overlap visually. This fixes the missing-coordinate crash
    without changing the simulator core.
    """
    ue_df = df.copy()

    # ------------------------------------------------------------
    # UE coordinates
    # ------------------------------------------------------------
    if {"ue_x", "ue_y", "ue_z"}.issubset(ue_df.columns):
        ue_lat_lon = ue_df[["ue_x", "ue_y", "ue_z"]].apply(
            lambda r: _ecef_to_lat_lon([r["ue_x"], r["ue_y"], r["ue_z"]]),
            axis=1,
            result_type="expand",
        )
        ue_df["ue_lat"] = ue_lat_lon[0]
        ue_df["ue_lon"] = ue_lat_lon[1]

    elif {"ue_lat", "ue_lon"}.issubset(ue_df.columns):
        # Already dashboard-ready.
        pass

    elif "home_beam" in ue_df.columns:
        # Reconstruct static UE map positions from the initial home beam
        # footprint. This is used when the core does not export ue_x/y/z.
        initial_time = beam_df["time_s"].min()
        home_lookup = (
            beam_df[beam_df["time_s"] == initial_time][
                ["candidate_id", "beam_lat", "beam_lon"]
            ]
            .drop_duplicates("candidate_id")
            .rename(
                columns={
                    "candidate_id": "home_beam",
                    "beam_lat": "home_beam_lat",
                    "beam_lon": "home_beam_lon",
                }
            )
        )

        ue_df = ue_df.merge(
            home_lookup,
            on="home_beam",
            how="left",
        )

        if ue_df["home_beam_lat"].isna().any() or ue_df["home_beam_lon"].isna().any():
            missing = sorted(
                ue_df.loc[
                    ue_df["home_beam_lat"].isna() | ue_df["home_beam_lon"].isna(),
                    "home_beam",
                ].dropna().unique().tolist()
            )
            raise KeyError(
                "Could not reconstruct UE map coordinates from home_beam. "
                f"Missing home_beam entries in beam_df: {missing}. "
                f"Available beam_df candidates: {sorted(beam_df['candidate_id'].dropna().unique().tolist())[:20]}"
            )

        # Deterministic small visual jitter per UE. The jitter is constant
        # across time, so UE tracks do not jump around on the map.
        uid = ue_df["ue_id"].astype(float)
        jitter_radius_deg = 0.035
        angle = (uid * 137.508) * np.pi / 180.0
        radius = jitter_radius_deg * (0.35 + 0.65 * ((uid % 11) / 10.0))

        ue_df["ue_lat"] = ue_df["home_beam_lat"] + radius * np.sin(angle)
        ue_df["ue_lon"] = ue_df["home_beam_lon"] + radius * np.cos(angle)

        ue_df = ue_df.drop(columns=["home_beam_lat", "home_beam_lon"])

    else:
        raise KeyError(
            "UE dataframe missing coordinates and home_beam. "
            f"Found columns: {list(ue_df.columns)}"
        )

    # Merge current serving beam footprint / satellite subpoint coordinates
    merge_cols = [
        "time_s",
        "candidate_id",
        "serving_beam_lat",
        "serving_beam_lon",
        "serving_sat_lat",
        "serving_sat_lon",
    ]

    beam_lookup = beam_df[merge_cols].rename(
        columns={"candidate_id": "serving_beam"}
    )

    ue_df = ue_df.merge(
        beam_lookup,
        on=["time_s", "serving_beam"],
        how="left",
    )

    # Compatibility aliases used by some dashboard versions.
    ue_df["serving_satellite_lat"] = ue_df["serving_sat_lat"]
    ue_df["serving_satellite_lon"] = ue_df["serving_sat_lon"]

    # Make sure booleans are clean for dashboard filters.
    for col in ["handover", "satellite_handover", "cell_handover", "cho_triggered"]:
        if col in ue_df.columns:
            ue_df[col] = ue_df[col].astype(bool)

    return ue_df


def run_digital_twin(args, core_path: str | None = None):
    """
    Run the EMC/Aalborg digital twin and return dashboard-ready DataFrames:

        ue_df:
            UE-level state over time, including lat/lon, serving beam,
            serving satellite, SINR, MCS, handover flags, and LHT diagnostics.

        beam_df:
            Beam/satellite footprint state over time for map visualization.
    """
    core = _load_core(core_path)

    ue_core_df = core.run(args)
    if ue_core_df.empty:
        raise RuntimeError("No UE rows were generated by ntn_beam_calibration_multisat.run().")

    beam_df = _build_beam_df(core, args)
    if beam_df.empty:
        raise RuntimeError("No beam rows were generated from the EMC constellation.")

    ue_df = _prepare_ue_df(ue_core_df, beam_df)

    return ue_df, beam_df


def save_digital_twin_outputs(
    args,
    core_path: str | None = None,
    output_dir: str = "outputs",
):
    """
    Save dashboard-ready digital twin outputs.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    ue_df, beam_df = run_digital_twin(args, core_path=core_path)

    ue_csv = output_path / "orbitiq_emc_aalborg_users.csv"
    beam_csv = output_path / "orbitiq_emc_aalborg_beams.csv"

    ue_df.to_csv(ue_csv, index=False)
    beam_df.to_csv(beam_csv, index=False)

    return ue_csv, beam_csv
