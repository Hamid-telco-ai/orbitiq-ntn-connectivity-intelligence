# OrbitIQ NTN Connectivity Intelligence

A physics-based **multi-satellite Non-Terrestrial Network (NTN)** framework for modeling **LEO mobility, Earth-Moving Cells (EMCs), beam-level connectivity, predictive handovers, and future connectivity intelligence**.

Traditional satellite platforms primarily provide **visibility** and **coverage maps**. OrbitIQ moves beyond static coverage estimation and predicts **where and when connectivity actually works**.

---

## Overview

OrbitIQ integrates:

- Multi-satellite LEO constellation modeling
- Earth-Moving Cell (EMC) beam mobility
- RF propagation and link budgets
- Beam-level serviceability analysis
- Future SINR prediction
- Release-18 inspired Conditional Handover (CHO)
- Predictive mobility intelligence

The objective is to transition from:

```text
Visibility → Coverage → Connectivity Intelligence
```

---

## Architecture

```text
Multi-satellite LEO constellation
        ↓
EMC moving beam footprints
        ↓
UE evaluates satellite-beam candidates
        ↓
Reference-location prediction
        ↓
Release-18 D2 preparation region
        ↓
Future SINR estimation
        ↓
Conditional handover execution
        ↓
Connectivity Intelligence
```

---

## Key Features

### Multi-Satellite LEO Simulation

Unlike static single-satellite models, OrbitIQ supports:

- Multiple satellites
- Dynamic orbital movement
- Satellite spacing
- Cross-satellite mobility evolution

Example:

```text
S1 → S2 → S3
```

representing realistic satellite progression over time.

---

### Earth-Moving Cell (EMC) Modeling

Beam footprints continuously move over Earth due to LEO satellite motion.

Beam positions evolve through:

- satellite local coordinate frames
- beam offset geometry
- Earth-surface projections
- moving reference locations

This follows NTN moving-cell assumptions discussed in Release-17 and Release-18 studies.

---

### Advanced Beam-Level Mobility

The framework performs:

- beam candidate selection
- future link prediction
- handover preparation
- conditional execution

instead of simply selecting strongest received power.

---

### Predictive Conditional Handover (CHO)

Inspired by Release-18 NTN mobility concepts:

Geometry preparation:

```math
D_1 > T_1 + H
```

```math
D_2 < T_2 - H
```

Combined with:

```math
NeighborSINR > Threshold
```

Extended with:

- future SINR prediction
- quality scoring
- beam persistence
- RF protection logic

---

## RF Propagation Models

### Free Space Path Loss

```math
FSPL(dB)=32.45+20log_{10}(d)+20log_{10}(f)
```

---

### Atmospheric Loss

```math
L_{atm}=
0.08/\sin(elevation)
```

---

### Doppler Shift

```math
f_d=
v_r/\lambda
```

Where:

| Parameter | Description |
|---|---|
| \(v_r\) | radial relative velocity |
| \(\lambda\) | carrier wavelength |

---

### Propagation Delay

```math
Delay=
distance/c
```

---

## Advanced UE Beamforming

### Sub-6 GHz UE

| Parameter | Value |
|---|---:|
| Panels | 1 |
| Array | 1×2 |
| Element gain | Omni |
| Noise figure | 7 dB |

---

### Ku/Ka UE

| Parameter | Value |
|---|---:|
| Panels | 2 |
| Array | 2×4 |
| Element gain | 5 dBi |
| Orientation | 0° /180° |
| Noise figure | 10 dB |

---

### UE Gain

```math
G_{UE}
=
G_{element}
+
G_{array}
```

---

## Simulation Outputs

OrbitIQ automatically generates:

```text
advanced_ntn_results.csv
```

and:

```text
final_ue_sinr_by_beam.png
final_sinr_histogram.png
sinr_vs_off_axis.png
sinr_vs_elevation.png
sinr_vs_doppler.png
avg_sinr_over_time.png
handover_events_over_time.png
d2_sinr_cho_triggers_over_time.png
```

---

## Example Run

Run baseline:

```bash
python ntn_beam_calibration_multisat.py
```

Run predictive mobility:

```bash
python ntn_beam_calibration_multisat.py \
--d2-cho \
--use-moving-refs \
--future-sinr-margin-db 2 \
--num-sats 3 \
--sat-spacing-s 150
```

---

## Example Results

Typical output:

```text
Serving Satellite Evolution:

S1 → S2 → S3

Average SINR: 36 dB
Average Off-axis: 2°
Outages: 0
CHO events: 30
```

---

## Project Structure

```bash
orbitiq-ntn-connectivity-intelligence/

├── ntn_beam_calibration_multisat.py
├── README.md
├── requirements.txt
├── .gitignore
├── advanced_ntn_results.csv
├── assets/
├── plots/
```

---


## References

**3GPP TR 38.811**  
Study on New Radio (NR) to support Non-Terrestrial Networks

**3GPP Release-18 NTN Mobility Studies**

**R1-1802551**  
UE Antenna Assumption and Beam Modeling for NTN

**R1-1802613**  
NTN NR Impacts on HARQ Operation

**R1-1806750**  
Considerations on Random Access for NTN

**Kodheli et al.**  
Satellite Communications in the New Space Era: A Survey and Future Challenges

**O-RAN Alliance**
Use Cases and AI/ML Architecture Specifications

---
