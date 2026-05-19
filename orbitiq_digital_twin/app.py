import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

from orbitiq_digital_twin_engine import make_args, run_digital_twin


st.set_page_config(
    page_title="OrbitIQ NTN Digital Twin",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .main {background-color: #050816;}
        div[data-testid="stMetricValue"] {font-size: 1.85rem;}
        div[data-testid="stMetricLabel"] {font-size: 0.9rem;}
        .block-container {padding-top: 1.5rem;}
        .orbit-card {
            border: 1px solid rgba(120, 180, 255, 0.25);
            border-radius: 18px;
            padding: 1rem 1.2rem;
            background: linear-gradient(135deg, rgba(20,30,60,0.92), rgba(5,8,22,0.98));
            box-shadow: 0 0 30px rgba(0, 140, 255, 0.12);
            color: white;
        }
        .orbit-card h2 {
            color: #4FC3FF;
            font-size: 2.4rem;
            margin-bottom: 0.5rem;
        }
        .orbit-card h4 {
            color: white;
            margin-bottom: 1rem;
        }
        .orbit-card p {
            color: #dce6ff;
            font-size: 0.95rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("OrbitIQ NTN Connectivity Intelligence Digital Twin")
st.caption(
    "Predictive serviceability, handover-wave intelligence, and beam-level, "
    "mobility risk for satellite and NTN networks."
)

with st.sidebar:
    st.header("Simulation Controls")

    duration_s = st.slider("Duration (s)", 18, 300, 120, 1)
    step_s = st.select_slider("Step (s)", options=[1, 2, 5, 10], value=1)
    num_sats = st.slider("Number of satellites", 2, 6, 3)
    sat_spacing_s = st.slider("Satellite spacing (s)", 30, 120, 60, 5)
    altitude_km = st.slider("Altitude (km)", 600, 2000, 600, 50)
    inclination_deg = st.slider("Inclination (deg)", 0, 80, 20, 5)
    future_margin = st.slider("Future SINR margin (dB)", 0.0, 8.0, 2.0, 0.5)
    neighbor_guard = st.slider("Neighbor SINR guard (dB)", -5.0, 15.0, 3.0, 0.5)
    reuse_one = st.toggle("Enable reuse-one interference", value=False)
    no_fading = st.toggle("Disable fading", value=True)

    st.divider()
    run_button = st.button(
        "Run / Refresh Digital Twin",
        type="primary",
        use_container_width=True,
    )


@st.cache_data(show_spinner=True)
def cached_simulation(
    duration_s,
    step_s,
    num_sats,
    sat_spacing_s,
    altitude_km,
    inclination_deg,
    future_margin,
    neighbor_guard,
    reuse_one,
    no_fading,
):
    args = make_args(
        duration_s=float(duration_s),
        step_s=float(step_s),
        num_sats=int(num_sats),
        sat_spacing_s=float(sat_spacing_s),
        altitude_km=float(altitude_km),
        inclination_deg=float(inclination_deg),
        future_sinr_margin_db=float(future_margin),
        d2_neighbor_sinr_db=float(neighbor_guard),
        reuse_one=bool(reuse_one),
        no_fading=bool(no_fading),
        use_moving_refs=True,
        d2_cho=True,
    )

    ue_df, beam_df = run_digital_twin(args)
    return ue_df, beam_df


with st.spinner("Running OrbitIQ multi-satellite NTN digital twin..."):
    ue_df, beam_df = cached_simulation(
        duration_s,
        step_s,
        num_sats,
        sat_spacing_s,
        altitude_km,
        inclination_deg,
        future_margin,
        neighbor_guard,
        reuse_one,
        no_fading,
    )

times = sorted(ue_df["time_s"].unique())

selected_time = st.slider(
    "Digital twin time (s)",
    int(min(times)),
    int(max(times)),
    int(max(times)),
    int(step_s),
)

selected_time = float(selected_time)

frame = ue_df[ue_df["time_s"] == selected_time].copy()
beam_frame = beam_df[beam_df["time_s"] == selected_time].copy()

if frame.empty:
    st.error("No data available at this time step.")
    st.stop()

# ============================================================
# Demo over Quebec
# ============================================================

DEMO_CENTER_LAT = 52.0
DEMO_CENTER_LON = -72.0

current_center_lat = frame["ue_lat"].mean()
current_center_lon = frame["ue_lon"].mean()

lat_shift = DEMO_CENTER_LAT - current_center_lat
lon_shift = DEMO_CENTER_LON - current_center_lon


def shift_lon(lon):
    return ((lon + lon_shift + 180) % 360) - 180


def shift_lat(lat):
    return np.clip(lat + lat_shift, -85, 85)


for df_ in [frame, beam_frame]:
    for lat_col, lon_col in [
        ("ue_lat", "ue_lon"),
        ("serving_sat_lat", "serving_sat_lon"),
        ("serving_beam_lat", "serving_beam_lon"),
        ("best_radio_sat_lat", "best_radio_sat_lon"),
        ("best_radio_beam_lat", "best_radio_beam_lon"),
        ("sat_lat", "sat_lon"),
        ("beam_lat", "beam_lon"),
    ]:
        if lat_col in df_.columns and lon_col in df_.columns:
            df_[lat_col] = df_[lat_col].apply(shift_lat)
            df_[lon_col] = df_[lon_col].apply(shift_lon)

final_frame = ue_df[ue_df["time_s"] == ue_df["time_s"].max()].copy()

avg_sinr = frame["sinr_db"].mean()
outages = int((frame["mcs"] == "Outage").sum())
avg_off_axis = frame["off_axis_deg"].mean()
ho_count = int(frame["handover"].sum())
cho_count = int(frame["cho_triggered"].sum())
dominant_sat = frame["serving_satellite"].value_counts().idxmax()

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("Avg SINR", f"{avg_sinr:.2f} dB")
c2.metric("Outage UEs", outages)
c3.metric("Avg Off-axis", f"{avg_off_axis:.2f}°")
c4.metric("Handover Events", ho_count)
c5.metric("Dominant Satellite", dominant_sat)

st.markdown("---")

map_col, side_col = st.columns([2.4, 1.0])


def sinr_color(sinr):
    if sinr < -5:
        return [220, 40, 40, 210]
    if sinr < 0:
        return [255, 140, 40, 210]
    if sinr < 10:
        return [255, 220, 60, 210]
    if sinr < 25:
        return [90, 210, 120, 210]
    return [55, 220, 255, 220]


frame["color"] = frame["sinr_db"].apply(sinr_color)

frame["handover_color"] = frame["handover"].apply(
    lambda x: [255, 255, 255, 255] if x else [90, 210, 255, 80]
)

beam_frame["sat_color"] = (
    beam_frame["satellite_id"]
    .map(
        {
            "S1": [70, 160, 255, 230],
            "S2": [140, 255, 170, 230],
            "S3": [255, 190, 80, 230],
            "S4": [230, 120, 255, 230],
            "S5": [255, 90, 130, 230],
            "S6": [150, 220, 255, 230],
        }
    )
    .fillna("")
    .apply(lambda x: x if isinstance(x, list) else [180, 180, 255, 230])
)

# ============================================================
#  CHO events
# ============================================================

arc_df = frame[
    (frame["handover"] == 1)
    | (frame["cho_triggered"] == 1)
].rename(
    columns={
        "ue_lon": "source_lon",
        "ue_lat": "source_lat",
        "serving_beam_lon": "target_lon",
        "serving_beam_lat": "target_lat",
    }
).copy()

arc_df = arc_df.drop_duplicates(
    subset=[
        "source_lon",
        "source_lat",
        "target_lon",
        "target_lat",
    ]
)

with map_col:
    st.subheader("Live Connectivity Intelligence Map")

    view_state = pdk.ViewState(
        latitude=float(frame["ue_lat"].mean()),
        longitude=float(frame["ue_lon"].mean()),
        zoom=4.8,
        pitch=65,
        bearing=35,
    )

    beam_footprint_layer = pdk.Layer(
        "ScatterplotLayer",
        data=beam_frame,
        get_position="[beam_lon, beam_lat]",
        get_fill_color="sat_color",
        get_radius=35000,
        opacity=0.08,
        stroked=True,
        get_line_color="sat_color",
        line_width_min_pixels=1,
        pickable=True,
    )

    beam_center_layer = pdk.Layer(
        "ScatterplotLayer",
        data=beam_frame,
        get_position="[beam_lon, beam_lat]",
        get_fill_color="sat_color",
        get_radius=9000,
        opacity=0.55,
        pickable=True,
    )

    sat_layer = pdk.Layer(
        "ScatterplotLayer",
        data=beam_frame.drop_duplicates("satellite_id"),
        get_position="[sat_lon, sat_lat]",
        get_fill_color="[255, 255, 255, 245]",
        get_radius=90000,
        stroked=True,
        get_line_color="[0, 220, 255, 255]",
        line_width_min_pixels=3,
        pickable=True,
    )

    sat_beam_arc_df = beam_frame.rename(
        columns={
            "sat_lon": "source_lon",
            "sat_lat": "source_lat",
            "beam_lon": "target_lon",
            "beam_lat": "target_lat",
        }
    ).copy()

    sat_beam_arc_layer = pdk.Layer(
        "ArcLayer",
        data=sat_beam_arc_df,
        get_source_position="[source_lon, source_lat]",
        get_target_position="[target_lon, target_lat]",
        get_source_color="[255, 255, 255, 160]",
        get_target_color="[0, 220, 255, 120]",
        get_width=3,
        width_min_pixels=1,
        width_max_pixels=5,
        pickable=False,
    )

    ue_heat = pdk.Layer(
        "HeatmapLayer",
        data=frame,
        get_position="[ue_lon, ue_lat]",
        get_weight="sinr_db",
        radiusPixels=60,
    )
    
    ue_layer = pdk.Layer(
        "ScatterplotLayer",
        data=frame,
        get_position="[ue_lon, ue_lat]",
        get_fill_color="color",
        get_radius=25000,
        stroked=True,
        get_line_color="[255, 255, 255, 80]",
        line_width_min_pixels=2,
        pickable=True,
        auto_highlight=True,
    )

    arc_layer = pdk.Layer(
        "ArcLayer",
        data=arc_df,
        get_source_position="[source_lon, source_lat]",
        get_target_position="[target_lon, target_lat]",
        get_source_color="[0, 255, 255, 190]",
        get_target_color="[255, 255, 255, 230]",
        get_width=5,
        width_min_pixels=2,
        width_max_pixels=7,
        pickable=True,
    )

    deck = pdk.Deck(
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        initial_view_state=view_state,
        layers=[
            beam_footprint_layer,
            sat_beam_arc_layer,
            beam_center_layer,
            sat_layer,
            ue_heat,
            arc_layer,
            ue_layer,
        ],
        tooltip={
            "html": """
            <b>UE {ue_id}</b><br/>
            Serving: {serving_beam}<br/>
            Satellite: {serving_satellite}<br/>
            SINR: {sinr_db} dB<br/>
            CHO: {cho_reason}
            """,
            "style": {
                "backgroundColor": "#0B1026",
                "color": "white",
            },
        },
    )

    st.pydeck_chart(deck, use_container_width=True)

with side_col:
    st.subheader("OrbitIQ Decision Engine")

    st.markdown("### Live Network Events")

    events = []

    if ho_count > 0:
        events.append(
            f"t={selected_time:.0f}s | Handover wave detected | {ho_count} UEs affected"
        )

    if cho_count > 0:
        events.append(
            f"t={selected_time:.0f}s | Predictive mobility trigger active | {cho_count} UEs"
        )

    if outages > 0:
        events.append(
            f"t={selected_time:.0f}s | Service degradation detected | {outages} outage UEs"
        )

    events.append(
        f"t={selected_time:.0f}s | Dominant serving layer: {dominant_sat}"
    )

    events.append(
        f"t={selected_time:.0f}s | Average SINR: {avg_sinr:.1f} dB"
    )

    events.append(
        f"t={selected_time:.0f}s | Average off-axis angle: {avg_off_axis:.1f}°"
    )

    for event in events[-6:]:
        st.info(event)

    # ============================================================
    # OrbitIQ AI Recommendation Engine
    # ============================================================

    if outages > 0:
        recommended_action = "Investigate degraded coverage region"
        action_reason = f"{outages} UEs currently experiencing outage."
        confidence = 96

    elif ho_count > 10:
        recommended_action = "Monitor active handover wave"
        action_reason = (
            f"{ho_count} UEs transitioning between serving satellites."
        )
        confidence = 92

    elif avg_sinr < 10:
        recommended_action = "Prepare backup serving layer"
        action_reason = f"Average SINR reduced to {avg_sinr:.1f} dB."
        confidence = 88

    elif avg_off_axis > 12:
        recommended_action = "Track beam alignment drift"
        action_reason = f"Average off-axis angle is {avg_off_axis:.1f}°."
        confidence = 84

    else:
        recommended_action = "Maintain current serving strategy"
        action_reason = (
            "Connectivity stable. No outage or major mobility risk detected."
        )
        confidence = 94

    st.markdown(
        f"""
        <div class="orbit-card">
            <h4>AI Recommended Action</h4>
            <h2>{recommended_action}</h2>
            <p>{action_reason}</p>
            <p>Confidence: <b>{confidence}%</b></p>
            <p>Dominant serving layer: <b>{dominant_sat}</b></p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    sat_counts = frame["serving_satellite"].value_counts().reset_index()
    sat_counts.columns = ["Satellite", "Users"]

    st.dataframe(
        sat_counts,
        use_container_width=True,
        hide_index=True,
    )

    risk_score = max(
        0,
        min(
            100,
            int(
                100
                - (avg_sinr * 2.2)
                + outages * 4
                + avg_off_axis * 2
            ),
        ),
    )

    if risk_score < 25:
        risk_label = "LOW"
    elif risk_score < 60:
        risk_label = "MEDIUM"
    else:
        risk_label = "HIGH"

    st.markdown(
        f"""
        <div class="orbit-card">
            <h4>Connectivity Risk</h4>
            <h2>{risk_label}</h2>
            <p>Risk score: <b>{risk_score}/100</b></p>
            <p>Dominant serving satellite: <b>{dominant_sat}</b></p>
            <p>Predictive CHO events at this time: <b>{cho_count}</b></p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Mobility Decision Summary")

    decision_labels = {
        "stay_serving_aalborg_lht_not_triggered": "Stable serving layer",
        "aalborg_lht_a3_gamma_ttt": "Mobility handover executed",
        "initial_attachment": "Initial serving assignment",
        "aalborg_lht_condition_met_waiting_ttt": "Mobility condition pending",
        "serving_cell_not_available": "Serving layer refreshed",
        "radio_best_selection_baseline": "Best serving layer selected",
    }

    reason_counts = (
        frame["cho_reason"]
        .replace(decision_labels)
        .value_counts()
        .reset_index()
    )
    reason_counts.columns = ["Decision", "UEs"]

    st.dataframe(
        reason_counts,
        use_container_width=True,
        hide_index=True,
    )

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "Performance",
        "Satellite Mobility",
        "Handover Intelligence",
        "Export",
    ]
)

with tab1:
    a, b = st.columns(2)

    avg_ts = ue_df.groupby("time_s", as_index=False)["sinr_db"].mean()

    fig = px.line(
        avg_ts,
        x="time_s",
        y="sinr_db",
        title="Average SINR Over Time",
    )

    fig.update_layout(
        template="plotly_dark",
        height=380,
    )

    a.plotly_chart(fig, use_container_width=True)

    off_axis_ts = ue_df.groupby("time_s", as_index=False)["off_axis_deg"].mean()

    fig2 = px.line(
        off_axis_ts,
        x="time_s",
        y="off_axis_deg",
        title="Average Off-axis Angle Over Time",
    )

    fig2.update_layout(
        template="plotly_dark",
        height=380,
    )

    b.plotly_chart(fig2, use_container_width=True)

    c, d = st.columns(2)

    fig3 = px.histogram(
        final_frame,
        x="sinr_db",
        nbins=20,
        title="Final Snapshot SINR Distribution",
    )

    fig3.update_layout(
        template="plotly_dark",
        height=380,
    )

    c.plotly_chart(fig3, use_container_width=True)

    fig4 = px.scatter(
        final_frame,
        x="off_axis_deg",
        y="sinr_db",
        color="serving_satellite",
        title="SINR vs Off-axis Angle",
        hover_data=[
            "ue_id",
            "serving_beam",
            "mcs",
        ],
    )

    fig4.update_layout(
        template="plotly_dark",
        height=380,
    )

    d.plotly_chart(fig4, use_container_width=True)

with tab2:
    mobility = (
        ue_df.groupby(
            [
                "time_s",
                "serving_satellite",
            ]
        )
        .size()
        .reset_index(name="users")
    )

    fig = px.area(
        mobility,
        x="time_s",
        y="users",
        color="serving_satellite",
        title="Serving Satellite Evolution: S1 → S2 → S3",
    )

    fig.update_layout(
        template="plotly_dark",
        height=430,
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Serving satellite counts by time")

    pivot = (
        ue_df.groupby("time_s")["serving_satellite"]
        .value_counts()
        .unstack(fill_value=0)
    )

    st.dataframe(pivot, use_container_width=True)

with tab3:
    ho_ts = ue_df.groupby("time_s", as_index=False)["handover"].sum()
    cho_ts = ue_df.groupby("time_s", as_index=False)["cho_triggered"].sum()

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=ho_ts["time_s"],
            y=ho_ts["handover"],
            mode="lines+markers",
            name="All handovers",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=cho_ts["time_s"],
            y=cho_ts["cho_triggered"],
            mode="lines+markers",
            name="Predictive CHO",
        )
    )

    fig.update_layout(
        title="Handover and Predictive CHO Events Over Time",
        xaxis_title="Time (s)",
        yaxis_title="Events",
        template="plotly_dark",
        height=430,
    )

    st.plotly_chart(fig, use_container_width=True)

    decision_labels = {
        "stay_serving_aalborg_lht_not_triggered": "Stable serving layer",
        "aalborg_lht_a3_gamma_ttt": "Mobility handover executed",
        "initial_attachment": "Initial serving assignment",
        "aalborg_lht_condition_met_waiting_ttt": "Mobility condition pending",
        "serving_cell_not_available": "Serving layer refreshed",
        "radio_best_selection_baseline": "Best serving layer selected",
    }

    reasons_df = ue_df.copy()
    reasons_df["mobility_decision"] = reasons_df["cho_reason"].replace(decision_labels)

    reasons = (
        reasons_df.groupby(
            [
                "serving_satellite",
                "mobility_decision",
            ]
        )
        .size()
        .reset_index(name="events")
    )

    fig2 = px.bar(
        reasons,
        x="serving_satellite",
        y="events",
        color="mobility_decision",
        title="Mobility Decisions by Serving Satellite",
        barmode="stack",
    )

    fig2.update_layout(
        template="plotly_dark",
        height=430,
    )

    st.plotly_chart(fig2, use_container_width=True)

with tab4:
    st.markdown("### Download Digital Twin Data")

    st.download_button(
        "Download UE Digital Twin CSV",
        data=ue_df.to_csv(index=False).encode("utf-8"),
        file_name="orbitiq_digital_twin_users.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.download_button(
        "Download Beam Footprint CSV",
        data=beam_df.to_csv(index=False).encode("utf-8"),
        file_name="orbitiq_digital_twin_beams.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.markdown("#### Current frame data")
    st.dataframe(frame, use_container_width=True)