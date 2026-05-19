# OrbitIQ NTN Connectivity Intelligence

<p align="center">
<img src="assets/orbitiq_banner.png" width="100%">
</p>

A physics-based **multi-satellite NTN digital twin and connectivity intelligence framework** for modeling **LEO mobility, Earth-Moving Cells (EMC), beam-level RF serviceability, OrbitIQ-LHT mobility intelligence, and AI-assisted NTN decision systems.**

---

## Overview

Traditional satellite systems answer:

```text
Where is the satellite?
Where is coverage available?
```

OrbitIQ answers:

```text
Where and when will connectivity actually work?
```

OrbitIQ combines:

- Multi-satellite LEO constellation evolution
- Earth-Moving Cell (EMC) beam mobility
- RF link-budget modeling
- Beam-level serviceability
- OrbitIQ-LHT mobility intelligence
- Inter-satellite handovers
- SINR-aware mobility
- NTN digital twin visualization
- AI recommendation engine

---

# System Architecture

```text
LEO constellation
      ↓
EMC beam evolution
      ↓
Beam candidate generation
      ↓
RF link calculation
      ↓
SINR + serviceability estimation
      ↓
OrbitIQ-LHT mobility engine
      ↓
Inter-satellite handover
      ↓
Digital Twin + Decision Engine
```

---

# Earth-Moving Cell (EMC)

OrbitIQ models moving cells attached to satellites.

UE–beam distance:

D(t)=||x_UE - x_beam(t)||

Moving beam centers evolve as:

x_beam(t)=f(x_satellite(t), beam_offset)

Satellite progression:

θ(t)=ωt+φ

where:

- ω = angular velocity
- φ = phase offset

Satellite evolution:

```text
S1 → S2 → S3
```

---

# RF Propagation

## Free Space Path Loss

FSPL:

FSPL(dB)=32.45+20log10(d)+20log10(f)

where:

- d : distance (km)
- f : frequency (MHz)

---

## Received Power

P_rx:

P_rx=EIRP−FSPL+G_sat+G_UE−L_atm−L_fading

Implemented terms:

- satellite beam gain
- UE gain
- atmospheric attenuation
- fading
- off-axis loss

---

## Atmospheric Loss

Used implementation:

L_atm=0.08/sin(elevation)

with:

elevation>2° clipping

---

## Doppler Shift

f_d=v_r/λ

where:

- vr = radial velocity
- λ = wavelength

---

## Propagation Delay

Delay=d/c

where:

- c = speed of light

---

# Beam Gain Model

Total gain:

G_total=G_element+G_array

Sub‑6 implementation:

|Parameter|Value|
|---|---:|
|Panels|1|
|Array|1×2|
|NF|7 dB|

Ku/Ka implementation:

|Parameter|Value|
|---|---:|
|Panels|2|
|Array|2×4|
|Element gain|5 dBi|

---

# Interference and SINR

Noise:

N=kTB

SINR:

SINR=P_rx/(I+N)

dB domain:

SINR_dB=P_rx−10log10(I+N)

Implemented:

- reuse-one interference
- fading
- beam overlap effects
- off-axis degradation

---

# OrbitIQ-LHT Mobility Intelligence

OrbitIQ-LHT is the mobility engine developed for EMC NTN systems.

Implemented:

- A3 mobility
- Γ mobility intelligence
- TTT
- inter-satellite handovers
- mobility-wave prediction
- serviceability-aware decisions

Decision rule:

P_T(t)>P_S(t)+HOM+Γ_ST

where:

- PT = target beam quality
- PS = serving beam quality
- HOM = handover margin
- Γ = OrbitIQ intelligence term

---

## Distance Evolution

Serving:

ΔD_S=D_S(t)-D_S(t-1)

Target:

ΔD_T=D_T(t)-D_T(t-1)

Mobility trend:

ξ_ST=ΔD_T/ΔD_S

OrbitIQ extension:

Γ_unclipped=α ξ_ST

Γ=max(min(Γ_unclipped,Γ_max),Γ_min)

This stabilizes mobility decisions.

---

# Serviceability Logic

OrbitIQ moves beyond visibility.

Decision dimensions:

- SINR
- outage
- beam quality
- mobility stability
- satellite transitions

MCS selection:

256QAM
64QAM
16QAM
QPSK
Outage

---

# Digital Twin

Features:

- Live connectivity map
- UE heat maps
- beam footprints
- mobility arcs
- handover trajectories
- AI decision engine
- risk estimation

---

# Simulation Configuration

|Parameter|Value|
|---|---:|
|Frequency|2 GHz|
|Bandwidth|10 MHz|
|Altitude|600 km|
|Users|100|
|Satellites|3|
|Spacing|60 sec|
|EMC|Enabled|
|OrbitIQ-LHT|Enabled|

---

# KPI Results

|Metric|Result|
|---|---:|
|Average SINR|33 dB|
|Outages|0|
|Handovers|18|
|Predictive events|3|
|Dominant satellite|S3|

---

# Vision

> Google Maps for Satellite Connectivity

Predict:

- where connectivity exists
- where outages emerge
- where service degrades
- where mobility actions should occur

---

# References

3GPP TR 38.811

3GPP Release‑18 NTN mobility

EMC NTN mobility studies

O‑RAN AI/ML specifications
