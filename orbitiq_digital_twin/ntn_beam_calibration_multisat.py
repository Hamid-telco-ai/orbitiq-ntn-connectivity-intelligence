import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

np.random.seed(7)

RE_KM = 6371.0  # Earth radius
MU_EARTH_KM3_S2 = 398600.4418 # Earth gravitational parameter
C = 299792458.0 # Speed of ligh

# Beam Centers
BEAM_CENTERS_T0 = {
    "B1": np.array([6371.0, 0.0, 0.0]),
    "B2": np.array([6347.0, 481.0, 278.0]),
    "B3": np.array([6347.0, 481.0, -278.0]),
    "B4": np.array([5422.0, 3622.0, 0.0]),
}


# 4 beams × 25 users = 100 UEs (UE Population)
N_USERS_PER_BEAM = 20
DROP_RADIUS_KM = 25.0

#RF Constants
SAT_EIRP_DBW = 44.0 # Fixed total satellite EIRP
SAT_GMAX_DB = 30.0 # Maximum beam gain
SAT_THETA_3DB_DEG = 4.4127 # Beamwidth-like parameter
SAT_SIDELOBE_ATTEN_DB = 35.0 # Max. off-axis attenuation
THERMAL_NOISE_DBW_PER_HZ = -204.0 # Thermal noise density

# ============================================================
# Vector Helpers
# ============================================================

def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def angle_deg(a, b):
    d = np.clip(np.dot(unit(a), unit(b)), -1.0, 1.0)
    return np.degrees(np.arccos(d))

## Distance between UE and reference location on Earth surface (D2 distance metric)
def surface_distance_km(a, b):
    central_angle_rad = np.arccos(
        np.clip(np.dot(unit(a), unit(b)), -1.0, 1.0)
    )
    return RE_KM * central_angle_rad

## Free space path loss: FSPL increases with distance and frequency
def fspl_db(d_km, f_mhz):
    return 32.45 + 20 * np.log10(d_km) + 20 * np.log10(f_mhz)

## Thermal noise: noise increases with bandwidth
def noise_dbw(bw_hz, nf_db):
    return THERMAL_NOISE_DBW_PER_HZ + 10 * np.log10(bw_hz) + nf_db


def db_to_lin(x):
    return 10 ** (x / 10)


def lin_to_db(x):
    return 10 * np.log10(np.maximum(x, 1e-30))


def elevation_deg(ue, sat):
    local_up = unit(ue)
    ue_to_sat = unit(sat - ue)
    return 90.0 - angle_deg(local_up, ue_to_sat)


# ============================================================
# Satellite Orbit
# ============================================================

## Create a simplified circular LEO orbit
def sat_state(t_s, altitude_km=1500.0, inclination_deg=20.0):
    r = RE_KM + altitude_km
    n = np.sqrt(MU_EARTH_KM3_S2 / r**3)  # Angular speed: n=√(μ/r³)
    inc = np.radians(inclination_deg) # Satellite path tilts relative to equator: 0: no equator, 90: polar
    u = n * t_s # Current orbital angle

    ## Satellite coordinates
    pos = np.array([
        r * np.cos(u),
        r * np.sin(u) * np.cos(inc),
        r * np.sin(u) * np.sin(inc),
    ])
    
    ## Velocity: Derivative of position
    vel = np.array([
        -r * n * np.sin(u),
        r * n * np.cos(u) * np.cos(inc),
        r * n * np.cos(u) * np.sin(inc),
    ])

    return pos, vel


def orbital_rate_rad_s(altitude_km=1500.0):
    """
    Circular-orbit angular rate.

    This is used to create phase-shifted LEO satellites in the same orbital plane.
    """
    r = RE_KM + altitude_km
    return np.sqrt(MU_EARTH_KM3_S2 / r**3)


def sat_state_phased(t_s, altitude_km=1500.0, inclination_deg=20.0, phase_rad=0.0):
    """
    Circular LEO orbit with an orbital phase offset.

    phase_rad < 0 means the satellite is behind the reference satellite.
    This lets the next satellite enter the UE service region after the serving
    satellite has moved away.
    """
    r = RE_KM + altitude_km
    n = orbital_rate_rad_s(altitude_km)
    inc = np.radians(inclination_deg)
    u = n * t_s + phase_rad

    pos = np.array([
        r * np.cos(u),
        r * np.sin(u) * np.cos(inc),
        r * np.sin(u) * np.sin(inc),
    ])

    vel = np.array([
        -r * n * np.sin(u),
        r * n * np.cos(u) * np.cos(inc),
        r * n * np.cos(u) * np.sin(inc),
    ])

    return pos, vel

## Model Earth-Moving (EMC) Cell behavior
def sat_local_frame(sat, sat_vel):
    z_nadir = unit(-sat)  # Points toward Earth center
    x_along = unit(sat_vel) # Where satellite moves
    y_cross = unit(np.cross(z_nadir, x_along)) # Perpendicular direction
    x_along = unit(np.cross(y_cross, z_nadir))
    return x_along, y_cross, z_nadir

## To answer this question: Where does beam hit Earth?
def ray_earth_intersection(sat, direction):
    
    ## Quadratic: as²+bs+c=0
    d = unit(direction)
    b = 2 * np.dot(sat, d)
    c = np.dot(sat, sat) - RE_KM**2
    disc = b * b - 4 * c ## Tells whether line hits Earth

    if disc < 0:
        return None
    
    ## Two intersections: enter sphere and exit sphere
    s1 = (-b - np.sqrt(disc)) / 2
    s2 = (-b + np.sqrt(disc)) / 2

    candidates = [s for s in [s1, s2] if s > 0]
    if not candidates:
        return None

    s = min(candidates)  ## Nearest point
    return RE_KM * unit(sat + s * d)  ## Gives beam footprint center


def init_beam_local_directions(altitude_km, inclination_deg):
    sat0, vel0 = sat_state(0.0, altitude_km, inclination_deg)
    x0, y0, z0 = sat_local_frame(sat0, vel0)  ## Build local frame

    local_dirs = {}

    for bname, center in BEAM_CENTERS_T0.items():
        d_ecef = unit(center - sat0)  ## Beam direction toward beam center
        
        ## Convert to satellite coordinates
        local_dirs[bname] = np.array([
            np.dot(d_ecef, x0),
            np.dot(d_ecef, y0),
            np.dot(d_ecef, z0),
        ])

    return local_dirs

## Release-18 D2 CHO: Serving cell:movingReferenceLocation-r18
##                    Neighbor: referenceLocation-r17
##                    UE: propagates satellite trajectory using ephemerisInfo-r17 to estimate future beam movement     

def init_emc_beam_local_directions():

    beam_offsets_deg = {
        "B1": (0.0, 0.0),
        "B2": (1.5, 0.0),
        "B3": (-1.5, 0.0),
        "B4": (0.0, 1.5),
        "B5": (0.0,-1.5),
    }

    local_dirs = {}

    for bname, (along_deg, cross_deg) in beam_offsets_deg.items():

        ax = np.radians(along_deg)
        ay = np.radians(cross_deg)

        d_local = np.array([
            np.tan(ax),
            np.tan(ay),
            1.0
        ])

        local_dirs[bname] = unit(d_local)

    return local_dirs


def moving_beam_references(
        t_s,
        altitude_km,
        inclination_deg,
        beam_local_dirs
):

    sat,sat_vel=sat_state(
        t_s,
        altitude_km,
        inclination_deg
    )

    x,y,z=sat_local_frame(
        sat,
        sat_vel
    )

    refs={}

    for bname,d_local in beam_local_dirs.items():

        d_ecef=unit(
            d_local[0]*x
            +
            d_local[1]*y
            +
            d_local[2]*z
        )

        hit=ray_earth_intersection(
            sat,
            d_ecef
        )

        if hit is None:
            hit=RE_KM*unit(sat)

        refs[bname]=hit


    return refs


# ============================================================
# Multi-Satellite LEO Constellation Candidate Model
# ============================================================

def satellite_phase_offsets(args):
    """
    Build a same-plane LEO constellation using time-separated satellites.

    S1 is the current satellite.
    S2, S3, ... are behind S1 by sat_spacing_s, 2*sat_spacing_s, ...
    so they enter the service region later as S1 moves away.

    This creates realistic inter-satellite handover pressure for EMC beams.
    """
    n = orbital_rate_rad_s(args.altitude_km)

    return {
        f"S{i + 1}": -i * n * args.sat_spacing_s
        for i in range(args.num_sats)
    }


def moving_beam_references_for_state(sat, sat_vel, beam_local_dirs):
    """
    Compute EMC beam footprint centers for one satellite state.
    Beam directions are fixed in the satellite local frame.
    """
    x, y, z = sat_local_frame(sat, sat_vel)
    refs = {}

    for bname, d_local in beam_local_dirs.items():
        d_ecef = unit(
            d_local[0] * x
            + d_local[1] * y
            + d_local[2] * z
        )

        hit = ray_earth_intersection(sat, d_ecef)

        if hit is None:
            hit = RE_KM * unit(sat)

        refs[bname] = hit

    return refs


def constellation_candidates(t_s, args, beam_local_dirs):
    """
    Return all satellite-beam candidates at time t.

    Candidate IDs are formatted as:
        S1_B1, S1_B2, ..., S2_B1, S2_B2, ...

    Each candidate carries:
        satellite ID, beam ID, satellite position, velocity, and beam footprint.
    """
    candidates = {}

    for sat_id, phase_rad in satellite_phase_offsets(args).items():
        sat, sat_vel = sat_state_phased(
            t_s,
            args.altitude_km,
            args.inclination_deg,
            phase_rad=phase_rad
        )

        refs = moving_beam_references_for_state(
            sat,
            sat_vel,
            beam_local_dirs
        )

        for beam_id, ref in refs.items():
            candidate_id = f"{sat_id}_{beam_id}"

            candidates[candidate_id] = {
                "sat_id": sat_id,
                "beam_id": beam_id,
                "sat": sat,
                "sat_vel": sat_vel,
                "ref": ref,
            }

    return candidates


def references_from_candidates(candidates):
    """
    Convert candidate metadata into the reference-location dictionary used by
    the D2/location-based CHO logic.
    """
    return {
        cid: item["ref"]
        for cid, item in candidates.items()
    }


def build_beam_links_for_ue(
    ue,
    candidate_info,
    args,
    ue_bearing,
    shadow_db,
    enable_fading=True,
):
    """
    Compute link budget for every satellite-beam candidate.
    """
    links = {}

    for cid, item in candidate_info.items():
        links[cid] = link_power_dbw(
            ue=ue,
            sat=item["sat"],
            sat_vel=item["sat_vel"],
            beam_reference=item["ref"],
            freq_mhz=args.freq_mhz,
            bw_mhz=args.bandwidth_mhz,
            ue_bearing=ue_bearing,
            shadow_db=shadow_db,
            enable_fading=enable_fading,
        )

        links[cid]["satellite_id"] = item["sat_id"]
        links[cid]["beam_id"] = item["beam_id"]

    return links


# ============================================================
# UE Dropping
# ============================================================
## This function creates one user inside beam footprint

def random_surface_point(center, radius_km):  ## One random UE location inside beam footprint
    c = unit(center)
    ref = np.array([0.0, 0.0, 1.0])  ## Temporary reference vector

    if abs(np.dot(c, ref)) > 0.95:  ## If beam center (c) is close to pole and ref become almost parallel
        ref = np.array([0.0, 1.0, 0.0])
    
    ## Two perpendicular directions on Earth's surface: Scatter usres
    t1 = unit(np.cross(c, ref))
    t2 = unit(np.cross(c, t1))

    r = radius_km * np.sqrt(np.random.rand())  ## Uniform density inside circle
    th = 2 * np.pi * np.random.rand() ## Random angle: 0-360
    

    ## Create random point
 #     UE
 #   /      
 #  /
 # B1------ UE

    p = center + r * np.cos(th) * t1 + r * np.sin(th) * t2

    ## UE lies exactly on Earth sphere
    return RE_KM * unit(p)


def create_ues(beam_centers):
    rows = []
    uid = 0

    for beam, center in beam_centers.items():
        for _ in range(N_USERS_PER_BEAM):
            uid += 1
            pos = random_surface_point(center, DROP_RADIUS_KM)

            rows.append({
                "ue_id": uid,
                "home_beam": beam,
                "ue_x": pos[0],
                "ue_y": pos[1],
                "ue_z": pos[2],
                "ue_bearing_deg": np.random.uniform(0, 360),
                "shadow_db": np.random.normal(0, 2.0),
            })

    return pd.DataFrame(rows)

# ============================================================
# UE Antenna / Panel Geometry
# ============================================================

## Creates a local coordinate frame at the UE location
## ENU: East - North - Up
## Up    = away from Earth center
## East  = sideways
## North = perpendicular to east and up
def local_enu(ue):
    up = unit(ue)
    z = np.array([0.0, 0.0, 1.0])

    if abs(np.dot(up, z)) > 0.99:
        z = np.array([0.0, 1.0, 0.0])

    east = unit(np.cross(z, up))
    north = unit(np.cross(up, east))

    return east, north, up

## Rodrigues’ rotation formula: To model downtilt / uptilt
def rodrigues(v, axis, deg):
    a = np.radians(deg)
    axis = unit(axis)

    return (
        v * np.cos(a)
        + np.cross(axis, v) * np.sin(a)
        + axis * np.dot(axis, v) * (1 - np.cos(a))
    )

## Creates the UE antenna panel coordinate system
## x = panel boresight direction
## y = panel horizontal side direction
## z = panel vertical direction

def panel_frame(ue, bearing_deg, downtilt_deg=0.0):
    east, north, up = local_enu(ue)

    x = unit(
        np.cos(np.radians(bearing_deg)) * east
        + np.sin(np.radians(bearing_deg)) * north
    )

    y = unit(np.cross(up, x))
    x = unit(rodrigues(x, y, -downtilt_deg))  # This rotates panel boresight around the side-axis
    z = unit(np.cross(x, y))

    return x, y, z

## This is crucial for antenna gain
    ## [1, 0, 0]: Satellite is directly in front of the panel
    ## [0, 1, 0]: Satellite is sideways
    ## [-1, 0, 0]: Satellite is behind the panel
def to_panel_dir(direction_ecef, x, y, z):
    d = unit(direction_ecef)
    return np.array([np.dot(d, x), np.dot(d, y), np.dot(d, z)])

## if satellite is near boresight → higher gain
## if satellite is off-angle → lower gain
def panel_angles(d):
    x, y, z = unit(d)
    phi = np.degrees(np.arctan2(y, x))  ## phi   = horizontal azimuth angle
    v_angle = np.degrees(np.arctan2(z, np.sqrt(x * x + y * y)))
    theta = 90.0 + v_angle  ## theta = vertical-style antenna pattern angle
    return theta, phi

# ============================================================
# UE Antenna Model
# ============================================================
## How much antenna gain does the UE get toward the satellite?

def element_gain_high_db(theta, phi):  ## For Ku / Ka / higher-band NTN
    theta_3db = 90.0  ## Vertical beamwidth-like parameter
    phi_3db = 90.0 ## Horizontal beamwidth-like parameter
    sla_v = 25.0 ## Vertical side-lobe attenuation limit
    a_m = 25.0 ## Maximum total attenuation
    ge_max = 5.0 ## Max element gain, 5 dBi
    
    # Vertical attenuation: farther theta from 90°, more vertical loss you get
    a_v = -min(12 * ((theta - 90.0) / theta_3db) ** 2, sla_v)
    
    # Horizontal attenuation:farther phi from 0°, more horizontal loss you get
    a_h = -min(12 * (phi / phi_3db) ** 2, a_m)
    
    # Combine vertical + horizontal
    #   satellite near boresight: close to 5 dBi
    #   satellite off-abgle: maybe 0 dBi
    #   satellite far off-angle: negative gain    

    a_3d = -min(-(a_v + a_h), a_m)

    return ge_max + a_3d


def element_gain_low_db(theta, phi): ## S-band: Omni-directional: 0 dBi element gain
    return 0.0


## UPA: Uniform Plannar Array: Creates the physical positions of antanna elements
def upa_positions(m, n, dv=0.5, dh=0.5):  ## For low-band: m, n = 1, 2 (1 x 2 antenna)
                                          ## For high-band: m, n = 2, 4 (2 x 4 antenna)
                                          ## dv and dh: 0.5 wavelength: Gives good beamforming behavior
    pos = []

    for i in range(m):
        for j in range(n):
            y = (j - (n - 1) / 2) * dh
            z = (i - (m - 1) / 2) * dv
            pos.append([0.0, y, z])

    return np.array(pos)

## Phased-array beamforming: Calculates the phase each antenna element should see for a signal coming from a given direction
def steering_vector(direction_panel, positions_lambda):
    d = unit(direction_panel)
    phase = 2 * np.pi * (positions_lambda @ d)
    return np.exp(1j * phase)

## Real phased arrays cannot choose perfectly continuous phase:
## They use phase shifters with finite resolution

def quantize_phase(phases, bits):
    levels = 2 ** bits
    step = 2 * np.pi / levels
    return np.round(phases / step) * step

## Calculates how much gain the UE gets from beamforming

def array_gain_db(actual_dir, steer_dir, positions, phase_bits=5):
    a_actual = steering_vector(actual_dir, positions)  ## Where the satellite really is
    a_steer = steering_vector(steer_dir, positions) ## Where the UE thinks it should steer

    phases = np.angle(a_steer)
    q_phases = quantize_phase(phases, phase_bits)

    w = np.exp(1j * q_phases) / np.sqrt(len(q_phases)) ## Phased-array weights
    gain = np.abs(np.vdot(w, a_actual)) ** 2 ## How well the beamformong weights match the incoming wave

    return lin_to_db(gain) ## gain ≈ number of antenna elements

## Create a small beam tracking error: good for high freq.

def rotate_panel_azimuth(d, error_deg):
    x, y, z = unit(d)
    a = np.radians(error_deg)

    return unit(np.array([
        x * np.cos(a) - y * np.sin(a),
        x * np.sin(a) + y * np.cos(a),
        z
    ]))


## It decides:
    #Which UE antenna model to use
    #Which panel is best
    #How much gain UE gets
    #What noise figure to use

def ue_gain_db(freq_mhz, ue, sat, bearing_deg, tracking_sigma_deg=1.0):
    direction = sat - ue
    
    ## Expected gain for S-band ~3 dB

    if freq_mhz < 6000:  ## S-band
        panels = [bearing_deg]  ## Single array
        m, n = 1, 2  ## 1 x 2 array
        nf = 7.0  ## NF; Noise Figure
        element_func = element_gain_low_db ## 0 dBi element gain
    else:  ## Ku/Ka
        panels = [bearing_deg, bearing_deg + 180.0]  ## 2 back-to-back panels
        m, n = 2, 4  ## 2 x 4 array
        nf = 10.0  ## NF
        element_func = element_gain_high_db ## Directional element pattern

    positions = upa_positions(m, n)
    best = None

    for b in panels:
        px, py, pz = panel_frame(ue, b)  ## Build panel axes
        d_panel = to_panel_dir(direction, px, py, pz) ## Convert satellite direction into panel frame
        theta, phi = panel_angles(d_panel) ## Get theta and phi
        
        ## UE tries to steer toward satellite, but with small angular error

        steering_error = np.random.normal(0.0, tracking_sigma_deg)
        steer_panel = rotate_panel_azimuth(d_panel, steering_error)

        eg = element_func(theta, phi)
        ag = array_gain_db(d_panel, steer_panel, positions)

        total = eg + ag ## UE gain = element gain + array gain

        item = {
            "ue_gain_db": total,
            "ue_element_gain_db": eg,
            "ue_array_gain_db": ag,
            "ue_theta_deg": theta,
            "ue_phi_deg": phi,
            "ue_panel_bearing_deg": b,
            "ue_nf_db": nf,
            "ue_tracking_error_deg": steering_error,
        }
        
        ## Pick best panel
        if best is None or item["ue_gain_db"] > best["ue_gain_db"]:
            best = item

    return best

# ============================================================
# Satellite Beam Pattern
# ============================================================

def sat_beam_gain_db(sat, beam_reference, ue):
    boresight = beam_reference - sat  ## Satellite → beam center
    direction = ue - sat  ## Satellite → UE

    alpha = angle_deg(boresight, direction)     
    ##              UE
    #         /
    #        /
    #       /
#sat ●------> beam center

    ## Apply beam attenuation model
    atten = min(12 * (alpha / SAT_THETA_3DB_DEG) ** 2, SAT_SIDELOBE_ATTEN_DB)

    ## Final beam gain
    gain = SAT_GMAX_DB - atten

    return gain, alpha

# ============================================================
# Propagation Effects
# ============================================================

def rician_fading_db(k_db=10.0):  ## Rician K-factor = LOS power / scattered power
    k = db_to_lin(k_db) ## Convert from dB to linear

    los = np.sqrt(k / (k + 1))
    scat = np.sqrt(1 / (2 * (k + 1))) * (
        np.random.randn() + 1j * np.random.randn()
    )

    h = los + scat ## Random scattered component
    return 20 * np.log10(np.abs(h) + 1e-12)  ## Total complex channel


def atmospheric_loss_db(elev_deg):
    e = max(elev_deg, 2.0)
    return 0.08 / np.sin(np.radians(e))  ## L_atm = 0.08 / sin (e)
## For advanced model, use ITU-R P.618/P.676 atmospheric model


def doppler_hz(ue, sat, sat_vel_km_s, freq_mhz):
    los = unit(sat - ue) ## Direction from UE to satellite
    radial_km_s = np.dot(sat_vel_km_s, los)
    wavelength_m = C / (freq_mhz * 1e6)

    return (radial_km_s * 1000.0) / wavelength_m


def propagation_delay_ms(ue, sat):
    d_m = np.linalg.norm(sat - ue) * 1000.0  ## Slant range: Large slant range variations in LEO introduce delay and path-loss changes
    return 1000.0 * d_m / C  ## One-way delay in milliseconds

# ============================================================
# Link Calculation
# ============================================================

def link_power_dbw(
    ue,
    sat,
    sat_vel,
    beam_reference,
    freq_mhz,
    bw_mhz,
    ue_bearing,
    shadow_db,
    enable_fading=True,
):
    d_km = np.linalg.norm(sat - ue)  ## Slant range
    elev = elevation_deg(ue, sat)  ## Satellite elevation angle 

    eirp_total = SAT_EIRP_DBW
    fspl = fspl_db(d_km, freq_mhz)  ## fslp

    sg, off_axis = sat_beam_gain_db(sat, beam_reference, ue)  ## Satellite beam gain
    ug = ue_gain_db(freq_mhz, ue, sat, ue_bearing)  ## UE antenna gain: S-band ~3 dB, Ku/Ka: directional panel + array gain

    atm = atmospheric_loss_db(elev) ## Atmospheric loss
    fad = rician_fading_db(10.0) if enable_fading else 0.0

    ## Link budget calculation
    rx = eirp_total + sg + ug["ue_gain_db"] - fspl - atm + shadow_db + fad

    return {
        "rx_dbw": rx,
        "distance_km": d_km,
        "elevation_deg": elev,
        "fspl_db": fspl,
        "sat_gain_db": sg,
        "off_axis_deg": off_axis,
        "atmospheric_loss_db": atm,
        "fading_db": fad,
        "doppler_hz": doppler_hz(ue, sat, sat_vel, freq_mhz),
        "delay_ms": propagation_delay_ms(ue, sat),
        **ug
    }


## If I hand over to this candidate beam, what SINR would the UE get?

def candidate_sinr_db(candidate_beam, beam_links, bw_hz, reuse_one):
    candidate_link = beam_links[candidate_beam]
    noise = noise_dbw(bw_hz, candidate_link["ue_nf_db"])

    ## Candidate beam signal power

    signal_lin = db_to_lin(candidate_link["rx_dbw"])
    noise_lin = db_to_lin(noise)
    interf_lin = 0.0
    
    ## Model frequency reuse/co-channel interference: If "reuse-one" is enabled: all beams use same frequency

    if reuse_one:
        for bname, link in beam_links.items():
            if bname != candidate_beam:
                interf_lin += db_to_lin(link["rx_dbw"])

    return lin_to_db(signal_lin / (interf_lin + noise_lin))

## Not a full 3GPP MCS table
def mcs_from_sinr(sinr):
    table = [
        (-5, "Outage"),
        (0, "QPSK-low"),
        (5, "QPSK"),
        (10, "16QAM"),
        (18, "64QAM"),
        (25, "256QAM"),
    ]

    label = "Outage"

    for th, name in table:
        if sinr >= th:
            label = name

    return label

# ============================================================
# Predictive Link-Quality CHO
# Release-18-inspired D2 Candidate Preparation + RF Execution
# ============================================================
# ============================================================
# Future SINR Prediction for Predictive CHO
# ============================================================

def predict_future_beam_quality(
    ue,
    candidate_beam,
    t_now,
    args,
    bw_hz,
    ue_bearing,
    shadow_db,
    beam_local_dirs,
):
    """
    Predict future SINR for a satellite-beam candidate over a look-ahead window.

    In the multi-satellite model, candidate_beam is a key like:
        S1_B2 or S2_B4

    The prediction recomputes the entire constellation at future times and
    evaluates the same candidate if it remains available.
    """
    future_sinrs = []

    prediction_times = np.arange(
        t_now,
        t_now + args.prediction_horizon_s + 1e-9,
        args.prediction_step_s
    )

    for tf in prediction_times:

        if args.use_moving_refs:
            future_candidates = constellation_candidates(
                tf,
                args,
                beam_local_dirs
            )
        else:
            # Static single-satellite fallback for baseline validation.
            sat_f, sat_vel_f = sat_state(
                tf,
                args.altitude_km,
                args.inclination_deg
            )

            future_candidates = {
                bname: {
                    "sat_id": "S1",
                    "beam_id": bname,
                    "sat": sat_f,
                    "sat_vel": sat_vel_f,
                    "ref": bref,
                }
                for bname, bref in BEAM_CENTERS_T0.items()
            }

        future_links = build_beam_links_for_ue(
            ue=ue,
            candidate_info=future_candidates,
            args=args,
            ue_bearing=ue_bearing,
            shadow_db=shadow_db,
            enable_fading=False,
        )

        if candidate_beam not in future_links:
            future_sinrs.append(-100.0)
            continue

        sinr_f = candidate_sinr_db(
            candidate_beam=candidate_beam,
            beam_links=future_links,
            bw_hz=bw_hz,
            reuse_one=args.reuse_one,
        )

        future_sinrs.append(sinr_f)

    future_sinrs = np.array(future_sinrs)

    outage_fraction = np.mean(future_sinrs < args.min_predicted_sinr_db)

    score = (
        np.mean(future_sinrs)
        - args.outage_penalty_db * outage_fraction
    )

    return {
        "mean_sinr": float(np.mean(future_sinrs)),
        "min_sinr": float(np.min(future_sinrs)),
        "outage_fraction": float(outage_fraction),
        "score": float(score),
    }

def aalborg_lht_gamma(
    serving_cell,
    target_cell,
    distances_now,
    distances_prev,
    args,
):
    """
    LHT location offset Γ_{S,T}(t-τ,t).
        ΔdS = dS(t) - dS(t-τ)
        ΔdT = dT(t) - dT(t-τ)
        ξS,T = ΔdT / ΔdS

    ξS,T is dimensionless, so this implementation maps it into a
    bounded dB offset before using it in the A3 threshold.

    Location gate:
        ΔdS > 0       serving cell center is moving away
        dS > Rc-      UE is near/outside inner serving-cell edge
        dT < Rc+      target cell is close enough to the UE

    If the gate fails, ΓS,T = openalty, which blocks the candidate.
    """
    d_s_now = distances_now.get(serving_cell, np.nan)
    d_t_now = distances_now.get(target_cell, np.nan)
    d_s_prev = distances_prev.get(serving_cell, np.nan)
    d_t_prev = distances_prev.get(target_cell, np.nan)

    if not np.isfinite(d_s_now) or not np.isfinite(d_t_now):
        return {
            "gamma_db": args.lht_openalty_db,
            "xi_st": np.nan,
            "delta_d_s_km": np.nan,
            "delta_d_t_km": np.nan,
            "lht_allowed": False,
            "d_s_now": d_s_now,
            "d_t_now": d_t_now,
        }

    if not np.isfinite(d_s_prev) or not np.isfinite(d_t_prev):
        return {
            "gamma_db": args.lht_openalty_db,
            "xi_st": np.nan,
            "delta_d_s_km": np.nan,
            "delta_d_t_km": np.nan,
            "lht_allowed": False,
            "d_s_now": d_s_now,
            "d_t_now": d_t_now,
        }

    delta_d_s = d_s_now - d_s_prev
    delta_d_t = d_t_now - d_t_prev

    if abs(delta_d_s) < args.lht_min_delta_km:
        xi_st = np.nan
    else:
        xi_st = delta_d_t / delta_d_s

    r_minus = args.lht_cell_radius_km - args.lht_inner_epsilon_km
    r_plus = args.lht_cell_radius_km + args.lht_outer_epsilon_km

    allowed = (
        delta_d_s > args.lht_min_delta_km
        and d_s_now > r_minus
        and d_t_now < r_plus
        and np.isfinite(xi_st)
    )

    # Interpretation:
    #   xi_st < 0  -> target is approaching while serving is moving away,
    #                 so Gamma becomes negative and helps the A3 condition.
    #   xi_st > 0  -> target is also moving away, so Gamma becomes positive
    #                 and makes HO harder.
    #   failed gate -> openalty blocks the candidate.
    if allowed:
        gamma_unclipped_db = args.lht_gamma_scale_db * xi_st
        gamma = float(
            np.clip(
                gamma_unclipped_db,
                args.lht_gamma_min_db,
                args.lht_gamma_max_db,
            )
        )
    else:
        gamma = args.lht_openalty_db

    return {
        "gamma_db": float(gamma),
        "xi_st": float(xi_st) if np.isfinite(xi_st) else np.nan,
        "delta_d_s_km": float(delta_d_s),
        "delta_d_t_km": float(delta_d_t),
        "lht_allowed": bool(allowed),
        "d_s_now": float(d_s_now),
        "d_t_now": float(d_t_now),
    }


def choose_serving_beam_d2_cho(
    ue,
    beam_links,
    moving_refs,
    old_serving,
    args,
    bw_hz,
    t_now,
    ue_bearing,
    shadow_db,
    beam_local_dirs,
    lht_state=None,
    ue_id=None,
):
    """
    Location-Based Handover Triggering (LHT).

    This replaces the previous D2 + future-SINR + RF-fallback logic.
    The execution condition is the A3 event with the location-based offset:

        P_T(t) > P_S(t) + HOM + Γ_{S,T}(t-τ,t)

    A candidate target is only accepted after the condition remains true for
    the configured Time-To-Trigger (TTT). There is no RF-best-beam fallback in
    this function, because that fallback was causing artificial ping-pong.
    """
    if lht_state is None:
        lht_state = {}
    if ue_id is None:
        ue_id = 0

    ue_key = int(ue_id)
    lht_state.setdefault("prev_distances", {})
    lht_state.setdefault("ttt_elapsed", {})

    # --------------------------------------------------------
    # Current radio and distance measurements
    # --------------------------------------------------------
    beam_sinr = {
        bname: candidate_sinr_db(
            candidate_beam=bname,
            beam_links=beam_links,
            bw_hz=bw_hz,
            reuse_one=args.reuse_one,
        )
        for bname in beam_links
    }

    best_radio_beam = max(beam_sinr, key=beam_sinr.get)
    best_distance_beam = min(
        moving_refs,
        key=lambda bname: surface_distance_km(ue, moving_refs[bname]),
    )

    distances = {
        bname: surface_distance_km(ue, ref)
        for bname, ref in moving_refs.items()
    }

    best_distance_km = distances[best_distance_beam]
    prev_distances = lht_state["prev_distances"].get(ue_key, {})

    # --------------------------------------------------------
    # Initial attachment
    # --------------------------------------------------------
    if old_serving is None or old_serving not in beam_links:
        lht_state["prev_distances"][ue_key] = distances
        lht_state["ttt_elapsed"][ue_key] = {}
        return {
            "serving": best_radio_beam,
            "cho_triggered": False,
            "cho_reason": "initial_attachment" if old_serving is None else "serving_cell_not_available",
            "d1_serving_km": distances[best_radio_beam],
            "d2_target_km": np.nan,
            "d2_target_beam": None,
            "target_sinr_db": np.nan,
            "best_radio_beam": best_radio_beam,
            "best_distance_beam": best_distance_beam,
            "best_distance_km": best_distance_km,
            "lht_gamma_db": np.nan,
            "lht_xi_st": np.nan,
            "lht_delta_d_s_km": np.nan,
            "lht_delta_d_t_km": np.nan,
            "lht_allowed": False,
            "lht_ttt_elapsed_s": 0.0,
        }

    serving_sinr = beam_sinr[old_serving]
    d1 = distances[old_serving]

    # --------------------------------------------------------
    # Baseline mode: keep original RF-best behavior only when
    # D2/LHT is explicitly disabled from CLI/dashboard.
    # --------------------------------------------------------
    if not args.d2_cho:
        lht_state["prev_distances"][ue_key] = distances
        lht_state["ttt_elapsed"][ue_key] = {}
        return {
            "serving": best_radio_beam,
            "cho_triggered": False,
            "cho_reason": "radio_best_selection_baseline",
            "d1_serving_km": distances.get(best_radio_beam, np.nan),
            "d2_target_km": np.nan,
            "d2_target_beam": None,
            "target_sinr_db": np.nan,
            "best_radio_beam": best_radio_beam,
            "best_distance_beam": best_distance_beam,
            "best_distance_km": best_distance_km,
            "lht_gamma_db": np.nan,
            "lht_xi_st": np.nan,
            "lht_delta_d_s_km": np.nan,
            "lht_delta_d_t_km": np.nan,
            "lht_allowed": False,
            "lht_ttt_elapsed_s": 0.0,
        }

    # If there is no previous distance snapshot yet, collect it and stay.
    if not prev_distances:
        lht_state["prev_distances"][ue_key] = distances
        lht_state["ttt_elapsed"][ue_key] = {}
        return {
            "serving": old_serving,
            "cho_triggered": False,
            "cho_reason": "lht_waiting_for_previous_distance_sample",
            "d1_serving_km": d1,
            "d2_target_km": np.nan,
            "d2_target_beam": None,
            "target_sinr_db": np.nan,
            "best_radio_beam": best_radio_beam,
            "best_distance_beam": best_distance_beam,
            "best_distance_km": best_distance_km,
            "lht_gamma_db": np.nan,
            "lht_xi_st": np.nan,
            "lht_delta_d_s_km": np.nan,
            "lht_delta_d_t_km": np.nan,
            "lht_allowed": False,
            "lht_ttt_elapsed_s": 0.0,
        }

    # --------------------------------------------------------
    # A3 + Γ target evaluation
    # --------------------------------------------------------
    target_rows = []
    old_sat = beam_links[old_serving]["satellite_id"]

    for target in beam_links:
        if target == old_serving:
            continue
        if beam_links[target]["satellite_id"] == old_sat:
            continue

        gamma_info = aalborg_lht_gamma(
            serving_cell=old_serving,
            target_cell=target,
            distances_now=distances,
            distances_prev=prev_distances,
            args=args,
        )

        target_sinr = beam_sinr[target]
        threshold = serving_sinr + args.lht_ho_margin_db + gamma_info["gamma_db"]
        a3_lht_condition = target_sinr > threshold

        target_rows.append({
            "beam": target,
            "sinr": target_sinr,
            "threshold": threshold,
            "a3_lht_condition": a3_lht_condition,
            **gamma_info,
        })

    valid = [r for r in target_rows if r["a3_lht_condition"]]

    if valid:
        valid.sort(
            key=lambda r: (
                -r["sinr"],
                -(r["sinr"] - r["threshold"]),
                r["d_t_now"],
            )
        )
        target = valid[0]
        target_beam = target["beam"]

        ue_ttt = lht_state["ttt_elapsed"].setdefault(ue_key, {})
        for b in list(ue_ttt.keys()):
            if b != target_beam:
                ue_ttt[b] = 0.0

        ue_ttt[target_beam] = ue_ttt.get(target_beam, 0.0) + args.step_s
        ttt_elapsed = ue_ttt[target_beam]

        if ttt_elapsed >= args.lht_ttt_s:
            lht_state["prev_distances"][ue_key] = distances
            lht_state["ttt_elapsed"][ue_key] = {}
            return {
                "serving": target_beam,
                "cho_triggered": True,
                "cho_reason": "aalborg_lht_a3_gamma_ttt",
                "d1_serving_km": d1,
                "d2_target_km": target["d_t_now"],
                "d2_target_beam": target_beam,
                "target_sinr_db": target["sinr"],
                "best_radio_beam": best_radio_beam,
                "best_distance_beam": best_distance_beam,
                "best_distance_km": best_distance_km,
                "lht_gamma_db": target["gamma_db"],
                "lht_xi_st": target["xi_st"],
                "lht_delta_d_s_km": target["delta_d_s_km"],
                "lht_delta_d_t_km": target["delta_d_t_km"],
                "lht_allowed": target["lht_allowed"],
                "lht_ttt_elapsed_s": ttt_elapsed,
            }

        lht_state["prev_distances"][ue_key] = distances
        return {
            "serving": old_serving,
            "cho_triggered": False,
            "cho_reason": "aalborg_lht_condition_met_waiting_ttt",
            "d1_serving_km": d1,
            "d2_target_km": target["d_t_now"],
            "d2_target_beam": target_beam,
            "target_sinr_db": target["sinr"],
            "best_radio_beam": best_radio_beam,
            "best_distance_beam": best_distance_beam,
            "best_distance_km": best_distance_km,
            "lht_gamma_db": target["gamma_db"],
            "lht_xi_st": target["xi_st"],
            "lht_delta_d_s_km": target["delta_d_s_km"],
            "lht_delta_d_t_km": target["delta_d_t_km"],
            "lht_allowed": target["lht_allowed"],
            "lht_ttt_elapsed_s": ttt_elapsed,
        }

    # No target satisfies A3 + Γ. Reset TTT counters and stay serving.
    lht_state["prev_distances"][ue_key] = distances
    lht_state["ttt_elapsed"][ue_key] = {}

    # Diagnostics: closest target to triggering, useful for debugging plots.
    if target_rows:
        candidate = max(target_rows, key=lambda r: r["sinr"] - r["threshold"])
        d2_target = candidate["d_t_now"]
        d2_target_beam = candidate["beam"]
        target_sinr = candidate["sinr"]
        gamma_db = candidate["gamma_db"]
        xi_st = candidate["xi_st"]
        delta_d_s = candidate["delta_d_s_km"]
        delta_d_t = candidate["delta_d_t_km"]
        allowed = candidate["lht_allowed"]
    else:
        d2_target = np.nan
        d2_target_beam = None
        target_sinr = np.nan
        gamma_db = np.nan
        xi_st = np.nan
        delta_d_s = np.nan
        delta_d_t = np.nan
        allowed = False

    return {
        "serving": old_serving,
        "cho_triggered": False,
        "cho_reason": "stay_serving_aalborg_lht_not_triggered",
        "d1_serving_km": d1,
        "d2_target_km": d2_target,
        "d2_target_beam": d2_target_beam,
        "target_sinr_db": target_sinr,
        "best_radio_beam": best_radio_beam,
        "best_distance_beam": best_distance_beam,
        "best_distance_km": best_distance_km,
        "lht_gamma_db": gamma_db,
        "lht_xi_st": xi_st,
        "lht_delta_d_s_km": delta_d_s,
        "lht_delta_d_t_km": delta_d_t,
        "lht_allowed": allowed,
        "lht_ttt_elapsed_s": 0.0,
    }

# ============================================================
# Main Simulation
# ============================================================

def run(args):
    beam_local_dirs = init_emc_beam_local_directions()

    # UE population is dropped under S1 beam footprints at t=0.
    # During the simulation, S2/S3/... move into the region and become
    # valid CHO targets.
    if args.use_moving_refs:
        initial_candidates = constellation_candidates(
            0.0,
            args,
            beam_local_dirs
        )

        initial_beam_centers = {
            cid: item["ref"]
            for cid, item in initial_candidates.items()
            if item["sat_id"] == "S1"
        }

    else:
        initial_beam_centers = BEAM_CENTERS_T0

    ues = create_ues(initial_beam_centers)

    rows = []

    times = np.arange(0, args.duration_s + 1e-9, args.step_s)
    bw_hz = args.bandwidth_mhz * 1e6

    previous_serving = {}
    lht_state = {}

    for t in times:

        if args.use_moving_refs:
            candidate_info = constellation_candidates(
                t,
                args,
                beam_local_dirs
            )
        else:
            sat, sat_vel = sat_state(
                t,
                args.altitude_km,
                args.inclination_deg
            )

            candidate_info = {
                bname: {
                    "sat_id": "S1",
                    "beam_id": bname,
                    "sat": sat,
                    "sat_vel": sat_vel,
                    "ref": bref,
                }
                for bname, bref in BEAM_CENTERS_T0.items()
            }

        moving_refs = references_from_candidates(candidate_info)

        for _, r in ues.iterrows():
            ue = np.array([r.ue_x, r.ue_y, r.ue_z])
            ue_bearing = r.ue_bearing_deg
            shadow = r.shadow_db

            beam_links = build_beam_links_for_ue(
                ue=ue,
                candidate_info=candidate_info,
                args=args,
                ue_bearing=ue_bearing,
                shadow_db=shadow,
                enable_fading=not args.no_fading,
            )

            old_serving = previous_serving.get(r.ue_id)

            cho = choose_serving_beam_d2_cho(
                ue=ue,
                beam_links=beam_links,
                moving_refs=moving_refs,
                old_serving=old_serving,
                args=args,
                bw_hz=bw_hz,
                t_now=t,
                ue_bearing=ue_bearing,
                shadow_db=shadow,
                beam_local_dirs=beam_local_dirs,
                lht_state=lht_state,
                ue_id=r.ue_id,
            )

            serving = cho["serving"]
            serving_link = beam_links[serving]

            noise = noise_dbw(bw_hz, serving_link["ue_nf_db"])

            signal_lin = db_to_lin(serving_link["rx_dbw"])
            interf_lin = 0.0

            if args.reuse_one:
                for bname, link in beam_links.items():
                    if bname != serving:
                        interf_lin += db_to_lin(link["rx_dbw"])

            noise_lin = db_to_lin(noise)

            sinr = lin_to_db(signal_lin / (interf_lin + noise_lin))
            snr = serving_link["rx_dbw"] - noise

            # --------------------------------------------------------
            # Handover counting fix
            # --------------------------------------------------------
            # cell_handover counts any serving cell/beam change, e.g.:
            #   S2_B3 -> S2_B4
            # satellite_handover counts only inter-satellite changes, e.g.:
            #   S1_B3 -> S2_B3
            #
            # For the high-level dashboard HO counter, use satellite_handover.
            # This avoids inflating the HO count with same-satellite beam changes.
            old_satellite = (
                beam_links[old_serving]["satellite_id"]
                if old_serving is not None and old_serving in beam_links
                else None
            )
            new_satellite = serving_link["satellite_id"]

            cell_handover = (
                old_serving is not None
                and old_serving != serving
            )

            satellite_handover = (
                old_satellite is not None
                and old_satellite != new_satellite
            )

            # Keep the legacy column name as the dashboard-level HO metric.
            handover = satellite_handover

            previous_serving[r.ue_id] = serving

            rows.append({
                "time_s": t,
                "ue_id": int(r.ue_id),
                "home_beam": r.home_beam,

                "serving_beam": serving,
                "serving_satellite": serving_link["satellite_id"],
                "serving_sat_beam": serving_link["beam_id"],
                "handover": handover,
                "satellite_handover": satellite_handover,
                "cell_handover": cell_handover,
                "old_satellite": old_satellite,
                "new_satellite": new_satellite,

                "d2_cho_enabled": args.d2_cho,
                "cho_triggered": cho["cho_triggered"],
                "cho_reason": cho["cho_reason"],

                "lht_gamma_db": cho.get("lht_gamma_db", np.nan),
                "lht_xi_st": cho.get("lht_xi_st", np.nan),
                "lht_delta_d_s_km": cho.get("lht_delta_d_s_km", np.nan),
                "lht_delta_d_t_km": cho.get("lht_delta_d_t_km", np.nan),
                "lht_allowed": cho.get("lht_allowed", False),
                "lht_ttt_elapsed_s": cho.get("lht_ttt_elapsed_s", 0.0),

                "movingReferenceLocation_r18_beam": old_serving,
                "referenceLocation_r17_target_beam": cho["d2_target_beam"],

                "D1_serving_distance_km": cho["d1_serving_km"],
                "D2_target_distance_km": cho["d2_target_km"],
                "D2_target_sinr_db": cho["target_sinr_db"],

                "distanceThreshFromReference1_km": args.d2_t1_km,
                "distanceThreshFromReference2_km": args.d2_t2_km,
                "hysteresis_km": args.d2_hysteresis_km,
                "neighbor_sinr_threshold_db": args.d2_neighbor_sinr_db,

                "best_radio_beam": cho["best_radio_beam"],
                "best_distance_beam": cho["best_distance_beam"],
                "best_distance_km": cho["best_distance_km"],

                "snr_db": snr,
                "sinr_db": sinr,
                "mcs": mcs_from_sinr(sinr),
                "noise_dbw": noise,
                "interference_dbw": lin_to_db(interf_lin) if interf_lin > 0 else -300,

                **serving_link
            })

    return pd.DataFrame(rows)


# ============================================================
# Plots
# ============================================================

def plot(df):
    last = df[df.time_s == df.time_s.max()]

    plt.figure(figsize=(9, 6))
    for b in sorted(last.serving_beam.unique()):
        s = last[last.serving_beam == b]
        plt.scatter(s["ue_id"], s["sinr_db"], label=b)
    plt.title("Final Snapshot: UE SINR by Serving Beam")
    plt.xlabel("UE ID")
    plt.ylabel("SINR (dB)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig("final_ue_sinr_by_beam.png", dpi=200)
    plt.show()

    plt.figure(figsize=(9, 5))
    plt.hist(last["sinr_db"], bins=18)
    plt.title("Final Snapshot: SINR Distribution")
    plt.xlabel("SINR (dB)")
    plt.ylabel("Number of UEs")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("final_sinr_histogram.png", dpi=200)
    plt.show()

    plt.figure(figsize=(9, 5))
    plt.scatter(last["off_axis_deg"], last["sinr_db"])
    plt.title("SINR vs Satellite Beam Off-Axis Angle")
    plt.xlabel("Off-axis angle (deg)")
    plt.ylabel("SINR (dB)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("sinr_vs_off_axis.png", dpi=200)
    plt.show()

    plt.figure(figsize=(9, 5))
    plt.scatter(last["elevation_deg"], last["sinr_db"])
    plt.title("SINR vs Elevation Angle")
    plt.xlabel("Elevation angle (deg)")
    plt.ylabel("SINR (dB)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("sinr_vs_elevation.png", dpi=200)
    plt.show()

    plt.figure(figsize=(9, 5))
    plt.scatter(last["doppler_hz"], last["sinr_db"])
    plt.title("SINR vs Doppler Shift")
    plt.xlabel("Doppler shift (Hz)")
    plt.ylabel("SINR (dB)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("sinr_vs_doppler.png", dpi=200)
    plt.show()

    avg = df.groupby("time_s")["sinr_db"].mean().reset_index()

    plt.figure(figsize=(9, 5))
    plt.plot(avg["time_s"], avg["sinr_db"])
    plt.title("Average SINR Over Time")
    plt.xlabel("Time (s)")
    plt.ylabel("Average SINR (dB)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("avg_sinr_over_time.png", dpi=200)
    plt.show()

    ho = df.groupby("time_s")["handover"].sum().reset_index()

    plt.figure(figsize=(9, 5))
    plt.plot(ho["time_s"], ho["handover"])
    plt.title("Handover Events Over Time")
    plt.xlabel("Time (s)")
    plt.ylabel("Number of handovers")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("handover_events_over_time.png", dpi=200)
    plt.show()

    d2 = df.groupby("time_s")["cho_triggered"].sum().reset_index()

    plt.figure(figsize=(9, 5))
    plt.plot(d2["time_s"], d2["cho_triggered"])
    plt.title("D2 + Neighbor SINR CHO Triggers Over Time")
    plt.xlabel("Time (s)")
    plt.ylabel("Hybrid CHO triggers")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("d2_sinr_cho_triggers_over_time.png", dpi=200)
    plt.show()

# ============================================================
# CLI
# ============================================================

def main():

    p = argparse.ArgumentParser()

    p.add_argument("--freq-mhz", type=float, default=2000.0)
    p.add_argument("--bandwidth-mhz", type=float, default=5.0)
    p.add_argument("--altitude-km", type=float, default=1500.0)
    p.add_argument("--inclination-deg", type=float, default=20.0)
    p.add_argument("--duration-s", type=float, default=300.0)
    p.add_argument("--step-s", type=float, default=10.0)

    p.add_argument("--reuse-one", action="store_true")
    p.add_argument("--no-fading", action="store_true")
    p.add_argument("--use-moving-refs", action="store_true")

    p.add_argument(
        "--d2-cho",
        action="store_true",
        help="Enable Aalborg location-based A3 + Gamma + TTT handover"
    )
    p.set_defaults(d2_cho=True)

    p.add_argument(
        "--d2-t1-km",
        type=float,
        default=160.0,
        help="distanceThreshFromReference1-r18 for serving moving reference"
    )

    p.add_argument(
        "--d2-t2-km",
        type=float,
        default=140.0,
        help="distanceThreshFromReference2-r18 for neighbor reference"
    )

    p.add_argument(
        "--d2-hysteresis-km",
        type=float,
        default=10.0,
        help="D2 CHO hysteresis distance"
    )

    p.add_argument(
        "--d2-neighbor-sinr-db",
        type=float,
        default=0.0,
        help="Neighbor SINR threshold required after D2 geometry condition is met"
    )

    p.add_argument(
        "--prediction-horizon-s",
        type=float,
        default=60.0,
        help="Future prediction horizon for CHO scoring"
    )

    p.add_argument(
        "--prediction-step-s",
        type=float,
        default=10.0,
        help="Future prediction time step for CHO scoring"
    )

    p.add_argument(
        "--future-sinr-margin-db",
        type=float,
        default=3.0,
        help="Required future SINR score margin before executing CHO"
    )

    p.add_argument(
        "--ho-penalty-db",
        type=float,
        default=1.0,
        help="Penalty applied to candidate beams to avoid unnecessary handovers"
    )

    p.add_argument(
        "--outage-penalty-db",
        type=float,
        default=10.0,
        help="Penalty applied when predicted future SINR falls below threshold"
    )

    p.add_argument(
        "--min-predicted-sinr-db",
        type=float,
        default=0.0,
        help="Minimum acceptable predicted SINR for CHO execution"
    )

    p.add_argument(
        "--lht-cell-radius-km",
        type=float,
        default=100.0,
        help="Aalborg LHT Rc. Use 25 km for the paper's 50 km diameter cells; 100 km matches this baseline UE drop radius."
    )

    p.add_argument(
        "--lht-inner-epsilon-km",
        type=float,
        default=10.0,
        help="Aalborg LHT inner edge epsilon: R_minus = Rc - epsilon."
    )

    p.add_argument(
        "--lht-outer-epsilon-km",
        type=float,
        default=10.0,
        help="Aalborg LHT outer edge epsilon: R_plus = Rc + epsilon."
    )

    p.add_argument(
        "--lht-ho-margin-db",
        type=float,
        default=0.0,
        help="A3 handover margin HOM in dB. The paper uses 0 dB."
    )

    p.add_argument(
        "--lht-ttt-s",
        type=float,
        default=0.0,
        help="A3 Time-To-Trigger in seconds. The paper uses 0 ms."
    )

    p.add_argument(
        "--lht-openalty-db",
        type=float,
        default=1e6,
        help="Aalborg openalty. Large value blocks candidates that fail the distance gate."
    )

    p.add_argument(
        "--lht-gamma-scale-db",
        type=float,
        default=1.0,
        help="Scale that maps dimensionless xi_ST into a dB-domain Gamma offset."
    )

    p.add_argument(
        "--lht-gamma-min-db",
        type=float,
        default=-3.0,
        help="Lower clipping bound for the dB-domain LHT Gamma offset."
    )

    p.add_argument(
        "--lht-gamma-max-db",
        type=float,
        default=3.0,
        help="Upper clipping bound for the dB-domain LHT Gamma offset."
    )

    p.add_argument(
        "--lht-min-delta-km",
        type=float,
        default=1e-6,
        help="Small guard to avoid division by zero in xi = delta_dT / delta_dS."
    )


    p.add_argument(
        "--num-sats",
        type=int,
        default=3,
        help="Number of same-plane LEO satellites in the simplified constellation"
    )

    p.add_argument(
        "--sat-spacing-s",
        type=float,
        default=150.0,
        help="Time separation between consecutive satellites in the same orbital plane"
    )

    args = p.parse_args()

    df = run(args)

    df.to_csv(
        "advanced_ntn_results.csv",
        index=False
    )

    print("\n=== Advanced NTN Simulation Complete ===")

    print(f"Frequency: {args.freq_mhz} MHz")
    print(f"Bandwidth: {args.bandwidth_mhz} MHz")
    print(f"Altitude: {args.altitude_km} km")
    print(f"Duration: {args.duration_s} s")
    print(f"Number of satellites: {args.num_sats}")
    print(f"Satellite spacing: {args.sat_spacing_s} s")

    print(
        f"Inter-beam interference enabled: {args.reuse_one}"
    )

    print(
        f"Release-18 condEventD2 enabled: {args.d2_cho}"
    )

    print(
        f"Neighbor SINR guard threshold: {args.d2_neighbor_sinr_db} dB"
    )

    print("\nSaved: advanced_ntn_results.csv")

    last = df[df.time_s == df.time_s.max()]

    print("\n=== Final Snapshot Summary ===")

    print(
        last[
            [
                "sinr_db",
                "snr_db",
                "rx_dbw",
                "elevation_deg",
                "off_axis_deg",
                "doppler_hz",
                "delay_ms",
                "ue_gain_db",
                "ue_array_gain_db",
                "ue_element_gain_db",
                "D1_serving_distance_km",
                "D2_target_distance_km",
                "D2_target_sinr_db",
            ]
        ].describe().to_string()
    )

    print("\n=== Serving Beam Counts ===")
    print(
        last["serving_beam"]
        .value_counts()
        .to_string()
    )

    if "serving_satellite" in last.columns:
        print("\n=== Serving Satellite Counts ===")
        print(last["serving_satellite"].value_counts().to_string())

    print("\n=== MCS Distribution ===")
    print(
        last["mcs"]
        .value_counts()
        .to_string()
    )

    print("\n=== Total Satellite Handovers ===")
    print(int(df["satellite_handover"].sum()) if "satellite_handover" in df.columns else int(df["handover"].sum()))

    if "cell_handover" in df.columns:
        print("\n=== Total Cell/Beam Changes ===")
        print(int(df["cell_handover"].sum()))

    print("\n=== Hybrid D2 + Neighbor SINR CHO Events ===")
    print(int(df["cho_triggered"].sum()))

    print("\n=== CHO Reason Distribution ===")
    print(
        df["cho_reason"]
        .value_counts()
        .to_string()
    )

    # ============================================================
    # Diagnostics
    # ============================================================

    print(
        "\n=== Best Radio Beam vs Serving Beam Diagnostic ==="
    )

    final = df[df.time_s == df.time_s.max()]

    print(
        final[
            [
                "serving_beam",
                "best_radio_beam",
                "off_axis_deg",
                "sinr_db",
            ]
        ]
        .head(20)
        .to_string()
    )

    print(
        "\nServing equals best radio beam:"
    )

    print(
        (
            final["serving_beam"]
            ==
            final["best_radio_beam"]
        ).mean()
    )

    print("\nAverage off-axis:")
    print(
        final["off_axis_deg"].mean()
    )

    print("\nAverage SINR:")
    print(
        final["sinr_db"].mean()
    )

    print("\nAverage elevation:")
    print(
        final["elevation_deg"].mean()
    )

    print("\nUsers in outage:")
    print(
        (
            final["mcs"] == "Outage"
        ).sum()
    )

    # --------------------------------------------------------
    # Multi-satellite diagnostics
    # --------------------------------------------------------

    print(
        "\n=== Serving Satellite Counts Over All Timesteps ==="
    )

    print(
        df["serving_satellite"]
        .value_counts()
        .to_string()
    )

    print(
        "\n=== Serving Satellite Counts by Time ==="
    )

    print(
        df.groupby("time_s")["serving_satellite"]
        .value_counts()
        .unstack(fill_value=0)
        .to_string()
    )

    print(
        "\n=== Final Snapshot Serving Satellite Counts ==="
    )

    print(
        final["serving_satellite"]
        .value_counts()
        .to_string()
    )

    print(
        "\n=== Handover Reasons by Serving Satellite ==="
    )

    print(
        df.groupby(
            [
                "serving_satellite",
                "cho_reason"
            ]
        )
        .size()
        .unstack(fill_value=0)
        .to_string()
    )

    print(
        "\n=== Average SINR by Serving Satellite ==="
    )

    print(
        df.groupby("serving_satellite")[
            "sinr_db"
        ]
        .mean()
        .to_string()
    )

    # --------------------------------------------------------
    # Plots
    # --------------------------------------------------------

    plot(df)

    print("\nSaved plots:")

    print("- final_ue_sinr_by_beam.png")
    print("- final_sinr_histogram.png")
    print("- sinr_vs_off_axis.png")
    print("- sinr_vs_elevation.png")
    print("- sinr_vs_doppler.png")
    print("- avg_sinr_over_time.png")
    print("- handover_events_over_time.png")
    print("- d2_sinr_cho_triggers_over_time.png")


if __name__ == "__main__":
    main()
