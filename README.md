# OrbitIQ NTN Connectivity Intelligence

<img width="1536" height="1024" alt="e656c1bb-b7c0-4110-bfec-a008529ef44b" src="https://github.com/user-attachments/assets/5fa5b098-dcf6-4231-b0a8-1f6daa3072a3" />


<p align="center">
<b>From Coverage Visibility → Connectivity Intelligence</b>
</p>

A physics-based **multi-satellite Non-Terrestrial Network (NTN)** framework for modeling **LEO mobility, Earth-Moving Cells (EMC), beam-level RF serviceability, OrbitIQ-LHT mobility intelligence, and AI-assisted connectivity intelligence systems.**

Traditional satellite systems answer:

```text
Where is the satellite?
Where is coverage available?
```

OrbitIQ answers:

```text
Where and when will connectivity actually work?
```

---

# Overview

OrbitIQ combines:

- Multi-satellite LEO constellation evolution
- Earth-Moving Cell (EMC) mobility
- RF link-budget modeling
- Beam-level serviceability
- OrbitIQ-LHT mobility intelligence
- Inter-satellite handovers
- SINR-aware mobility
- NTN digital twin visualization
- AI recommendation engine
- Connectivity intelligence dashboard

The objective is to transition from:

```text
Visibility
      ↓
Coverage
      ↓
Connectivity Intelligence
```

---

# System Architecture

```text
Multi-satellite LEO constellation
                ↓
Earth-Moving Cell beam evolution
                ↓
Beam candidate generation
                ↓
RF link calculation
                ↓
SINR + serviceability estimation
                ↓
OrbitIQ-LHT mobility engine
                ↓
Inter-satellite handover execution
                ↓
Digital Twin + AI Decision Engine
```

---

# Multi-Satellite Mobility

Unlike static single-satellite approaches, OrbitIQ supports:

- Multiple satellites
- Dynamic orbital movement
- Satellite spacing
- Cross-satellite mobility evolution
- Beam migration behavior

Example:

```text
S1 → S2 → S3
```

representing realistic satellite progression.

---

# Earth-Moving Cell (EMC)

OrbitIQ models moving beam footprints attached to satellites.

UE-to-beam distance:

```math
D(t)=||x_{UE}-x_{beam}(t)||
```

Beam evolution:

```math
x_{beam}(t)=f(x_{satellite}(t),beam_{offset})
```

Satellite angular evolution:

```math
\theta(t)=\omega t+\phi
```

Where:

| Parameter | Description |
|---|---|
| ω | angular velocity |
| φ | phase offset |

---

# RF Propagation

## Free Space Path Loss

```math
FSPL(dB)=32.45+20log_{10}(d)+20log_{10}(f)
```

Where:

| Parameter | Description |
|---|---|
| d | distance (km) |
| f | frequency (MHz) |

---

## Received Power

Implemented link-budget:

```math
P_{rx}=EIRP-FSPL+G_{sat}+G_{UE}-L_{atm}-L_{fading}
```

Implemented terms:

- satellite beam gain
- UE gain
- atmospheric attenuation
- fading
- off-axis loss

---

## Atmospheric Loss

Implemented:

```math
L_{atm}=0.08/\sin(elevation)
```

with:

```text
elevation > 2°
```

clipping.

---

## Doppler Shift

```math
f_d=v_r/\lambda
```

Where:

| Parameter | Description |
|---|---|
| vr | radial velocity |
| λ | carrier wavelength |

---

## Propagation Delay

```math
Delay=d/c
```

---

# Beam Gain Model

Overall UE gain:

```math
G_{UE}=G_{element}+G_{array}
```

Sub-6 implementation:

| Parameter | Value |
|---|---:|
| Panels | 1 |
| Array | 1×2 |
| Noise Figure | 7 dB |

Ku/Ka implementation:

| Parameter | Value |
|---|---:|
| Panels | 2 |
| Array | 2×4 |
| Element Gain | 5 dBi |

---

# Interference and SINR

Thermal noise:

```math
N=kTB
```

SINR:

```math
SINR=P_{rx}/(I+N)
```

dB domain:

```math
SINR_{dB}=P_{rx}-10log_{10}(I+N)
```

Implemented:

- reuse-one interference
- beam overlap effects
- fading
- off-axis degradation

---

# OrbitIQ-LHT Mobility Intelligence

OrbitIQ-LHT is the mobility framework designed for **EMC NTN systems**.

Implemented:

- A3 mobility logic  
- Γ mobility intelligence  
- Time-to-Trigger (TTT)  
- Inter-satellite handovers  
- Mobility-wave prediction  
- Serviceability-aware decisions  

---

## OrbitIQ-LHT Decision Rule

```math
P_T(t)>P_S(t)+HOM+\Gamma_{S,T}
```

Where:

| Parameter | Description |
|---|---|
| PT | target beam quality |
| PS | serving beam quality |
| HOM | handover margin |
| Γ | OrbitIQ intelligence term |

---

## Distance Evolution

Serving trend:

```math
\Delta D_S=D_S(t)-D_S(t-1)
```

Target trend:

```math
\Delta D_T=D_T(t)-D_T(t-1)
```

Mobility evolution:

```math
\xi_{ST}=\Delta D_T/\Delta D_S
```

OrbitIQ enhancement:

```math
\Gamma_{unclipped}=\alpha \xi_{ST}
```

```math
\Gamma=
max(
min(\Gamma_{unclipped},\Gamma_{max}),
\Gamma_{min}
)
```

This stabilizes mobility decisions and avoids excessive handovers.

---

# Serviceability Logic

OrbitIQ extends beyond visibility.

Decision dimensions:

- SINR
- outage
- beam quality
- mobility stability
- satellite transitions

Supported MCS:

- 256QAM
- 64QAM
- 16QAM
- QPSK
- Outage

---

# OrbitIQ Digital Twin

OrbitIQ includes a command-center style dashboard.

### Live Connectivity Intelligence Map

Features:

- Satellite visualization
- Beam footprints
- SINR heat layers
- UE clusters
- Mobility arcs
- Handover trajectories

---

### OrbitIQ Decision Engine

Provides:

- Connectivity risk estimation
- Live network event feed
- AI recommendations
- Serving layer analysis
- Satellite load visualization
- Mobility intelligence

---

# Simulation Configuration

| Parameter | Value |
|---|---:|
| Frequency | 2 GHz |
| Bandwidth | 10 MHz |
| Altitude | 600 km |
| Users | 100 |
| Satellites | 3 |
| Satellite spacing | 60 sec |
| EMC | Enabled |
| OrbitIQ-LHT | Enabled |
| TTT | Enabled |

---

# KPI Results

| Metric | Result |
|---|---:|
| Average SINR | 33 dB |
| Average Off-axis | 14° |
| Outages | 0 |
| Handovers | 18 |
| Predictive events | 3 |
| Dominant satellite | S3 |

---

# Satellite Mobility Evolution

| Time(s) | S1 | S2 | S3 |
|---|---:|---:|---:|
|0|100|0|0|
|50|72|28|0|
|80|22|78|0|
|100|0|58|42|
|120|0|0|100|

Observed:

```text
Initial
 S1
 ↓
Transition
 S2
 ↓
Final
 S3
```

---

# Project Structure

```bash
orbitiq-ntn-connectivity-intelligence/

├── app.py
├── orbitiq_digital_twin_engine.py
├── ntn_beam_calibration_multisat.py
├── requirements.txt
├── README.md
├── LICENSE
├── assets/
```

---

# Vision

> Google Maps for Satellite Connectivity

Predict:

- where connectivity exists
- where service degrades
- where handovers occur
- where outages emerge
- where connectivity intelligence should act

---

# References

- **3GPP TR 38.811**  
  Study on NR to support Non-Terrestrial Networks

- **3GPP Release-18 NTN Mobility Studies**

- **EMC NTN mobility studies and location-aware mobility concepts**

- **O-RAN Alliance AI/ML specifications**

- **ITU-R P.525**  
  Free Space Path Loss model
