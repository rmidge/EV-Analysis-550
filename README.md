# Philadelphia EV Charging Infrastructure Gap Analysis

## Project Overview
This repository contains a comprehensive analysis of electric vehicle (EV) charging infrastructure in Philadelphia, with a focus on spatial equity and accessibility. The analysis identifies service gaps and priority areas for future infrastructure development using network analysis and socioeconomic data.

## Key Features
- **Spatial Equity Analysis**: Assessment of current EV charging station distribution across Philadelphia
- **Network-Based Accessibility**: Service area calculations using OpenStreetMap network data
- **Gap Score System**: Multi-factor prioritization framework incorporating coverage, income, poverty, density, and education
- **Interactive Visualizations**: Maps and dashboard for exploring priority areas
- **Policy Recommendations**: Evidence-based suggestions for equitable infrastructure development


## Data Sources
- **EV Charging Stations**: National Renewable Energy Laboratory API
- **Census Data**: American Community Survey (ACS) 5-year estimates
- **Street Network**: OpenStreetMap via OSMnx
- **Boundaries**: City of Philadelphia Open Data

## Methodology Highlights
- Network analysis using multi-buffer approach (0.25-0.75 mile walking, 1-3 mile driving)
- Gap scoring with dynamic weighting system: Coverage (24%), Income (16%), Poverty (24%), Density (20%), Education (16%)
- Prioritization using thresholds [0.45, 0.55, 0.65] for Low, Medium, High, and Critical priority areas

## Author
[Rachel Midgett - rachelmidge@gmail.com]

https://rmidge.github.io/EV-Analysis-550/