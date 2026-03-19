# NYC Food Insecurity Vulnerability Dashboard

## Overview

Full-stack civic tech dashboard for the NYC Mayor's Office of Food Policy. Visualizes food insecurity vulnerability scores across all 59 NYC Community Districts with an interactive Leaflet.js map, AI assistant panel, active alerts, and key indicators.

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5
- **Frontend**: React + Vite (Tailwind CSS v4, Leaflet.js, Recharts, Framer Motion)
- **Validation**: Zod (`zod/v4`), `drizzle-zod`
- **API codegen**: Orval (from OpenAPI spec)
- **Python tools**: process_data.py (scorer), data_pipeline.py (scheduled refresh)

## Structure

```text
workspace/
├── artifacts/
│   ├── api-server/         # Express API server serving district data
│   └── nyc-food-dashboard/ # React dashboard (dark civic tech UI)
├── lib/
│   ├── api-spec/           # OpenAPI spec + Orval codegen config
│   ├── api-client-react/   # Generated React Query hooks
│   ├── api-zod/            # Generated Zod schemas from OpenAPI
│   └── db/                 # Drizzle ORM schema + DB connection
├── vulnerability_scores.json  # Scored data for all 59 community districts
├── process_data.py            # Vulnerability scorer (run manually)
├── data_pipeline.py           # Scheduled API refresh pipeline
├── requirements.txt           # Python deps: requests, schedule, anthropic
├── data/                      # Upload CSV files here to re-score
│   ├── SNAP (Food Stamps).csv
│   ├── Citizenship.csv
│   ├── NYC_EH_Rent-burdened_households.csv
│   ├── NYC_EH_Child_poverty_under_age_5.csv
│   └── NYC_EH_Unemployment.csv
```

## Dashboard Features

- **NYC Choropleth Map**: Leaflet.js map with community districts colored by risk tier (Critical/High/Moderate/Lower)
- **Neighborhood Risk Ranking**: Sorted list with search + borough filter tabs
- **District Detail Panel**: Indicator bars + SNAP trend sparkline for selected district
- **Active Alerts**: Real-time alerts for high-risk districts
- **Food Policy AI Assistant**: Chat interface for policy queries
- **Stats Bar**: 1.8M SNAP Recipients, 8 Critical Districts, 700+ Pantries, $186B Cuts
- **Quick Actions**: Generate Report, SNAP Impact, Pantry Gaps

## Vulnerability Score Formula

| Indicator | Weight |
|---|---|
| SNAP household enrollment | 35% |
| Child poverty rate (under 5) | 20% |
| Rent-burdened households | 20% |
| Unemployment rate | 15% |
| Non-citizen population | 10% |

Risk Tiers: Critical (70-100) | High (50-69) | Moderate (30-49) | Lower (0-29)

## API Routes

- `GET /api/healthz` — health check
- `GET /api/districts` — all 59 community districts with vulnerability scores
- `GET /api/districts/:fips` — single district by FIPS code

## Python Tools

Run the scorer after uploading CSV files to `/data`:
```bash
python process_data.py
```

Run the data pipeline (fetches fresh NYC Open Data + re-scores):
```bash
python data_pipeline.py --once
# or scheduled:
python data_pipeline.py --interval 24
```

## Data Sources

- SNAP data: NYC HRA via CCC, 2024
- Citizenship: ACS via CCC, 2023
- Rent burden, Child poverty, Unemployment: NYC EH Portal, 2017-21
