# THE GRID NYC — Build Record & Case Study Reference
*Saved from build session — April 15, 2026*

---

## PRODUCT OVERVIEW

**The Grid NYC** is a real-time neighborhood intelligence platform that maps food vulnerability, housing stress, cost of living pressure, health burden, and economic conditions across all 59 of New York City's community districts — in one view. It turns fragmented, months-old data into a live decision-making tool that shows city planners, agencies, and foundations exactly where the gaps are and where the next dollar will produce the most impact. For any budget allocation decision, The Grid answers the question every agency has needed answered for a decade: *where will this money do the most good, right now?*

**Tagline:** Every district. Every indicator. One view.

---

## THE PRODUCT VISION

### Current Question vs. Expanded Question

**Current question (original build):**
"Which neighborhoods will be hit hardest by SNAP cuts?"

**Expanded question (The Grid NYC):**
"For any dollar the city is considering spending, where will it produce the most impact — and what does the evidence say right now?"

That is a fundamentally different and far more valuable product. It turns the tool from a food policy dashboard into the city's fund allocation intelligence layer — used by MOFP, but also by the Department of Housing Preservation, the Department of Health, the Office of Economic Opportunity, community boards, nonprofits, and foundations making grant decisions.

---

## WHY THE GRID — THE PITCH ANSWER

> "New York City was literally built on a grid.
>
> In 1811 the city commissioners looked at Manhattan — chaotic, unplanned, growing faster than anyone could manage — and they drew a grid over all of it. Every block accounted for. Every street numbered. No neighborhood invisible. The grid did not generate anything. It organized everything. It made the city governable.
>
> That is exactly what this tool does for data.
>
> Right now city planners are making decisions about where to send resources using spreadsheets and quarterly reports that are months old. Some neighborhoods show up in every dataset. Some barely show up at all. The ones that barely show up are usually the ones that need the most.
>
> The Grid puts every one of NYC's 59 community districts on equal footing. Every district scored. Every indicator visible. No neighborhood falls through the cracks. And just like the 1811 grid did not favor one block over another — it just made everything legible — The Grid does not advocate for any particular outcome. It just shows you what is true, right now, so that the people responsible for this city can make better decisions faster.
>
> Every district. Every indicator. One view.
>
> That is why The Grid."

### Why "THE GRID" — Five Layers of Meaning

**Layer 1 — The Commissioner's Plan of 1811**
New York City is literally built on a grid. The Manhattan street grid — laid out by the Commissioners' Plan of 1811 — divided the entire island into a rational, navigable system of blocks and lots. The grid did not generate anything. It organized everything. It made the city governable at scale. Your tool does the same thing for data that the 1811 grid did for land.

**Layer 2 — The Power Grid**
A power grid does not generate energy. It distributes it. Efficiently, to where it is needed, based on real-time demand signals. That is exactly what this tool does with funding and resources. It does not create money. It shows where the demand is highest and enables the system to route resources there.

**Layer 3 — The Grid as a Visual Object**
A grid is literally what your dashboard shows. 59 districts laid out in a spatial grid on a choropleth map. The visualization itself is a grid. The name describes what you see when you open the tool. It also implies completeness — a grid has no gaps. Every cell is accounted for.

**Layer 4 — The Grid as Infrastructure**
Infrastructure is the thing you do not notice until it fails. Policy intelligence should be infrastructure. It should be the thing that is always on, always current, always there when a planner needs to make a decision. The word grid signals that this is not a report or a dashboard — it is the underlying layer that everything else runs on top of. Infrastructure gets funded and maintained. Projects get deprecated.

**Layer 5 — NYC-Specific Resonance**
- "Did you check EquityLens?" — sounds like an academic tool
- "Did you check CityPulse?" — sounds like a news app
- "Did you check The Grid?" — sounds like the system itself

**THE / GRID / NYC**
- THE — not a grid, the grid. Definitive. The only one. The official one.
- GRID — infrastructure, not a product. Completeness. NYC's DNA. Distribution. The visual object you see.
- NYC — specific, local, not trying to be everywhere. Civic pride. This is ours.

---

## EVIDENCE OF THE PROBLEM

### Claim 1 — "Planners are making decisions using data that is months old"

The Supply Gap Analysis is completed annually by the Mayor's Office for Economic Opportunity. Data on food demand comes from the latest Feeding America report on food hardship, sourced from U.S. Census data that is typically 12 to 18 months old by the time it is processed and published.

For returning providers, allocations are based on service, reach, capacity, and effective resource management history — not current conditions. A pantry that had strong numbers three years ago continues to receive funding based on that historical record even if conditions in its neighborhood have dramatically changed.

From City Council hearing testimony (March 17, 2025), the DSS official confirmed: *"In terms of setting the allocations every year we start with the pantries that we've been working with."* They start with who they already know. That is a historical record, not a real-time signal.

### Claim 2 — "Some neighborhoods barely show up in the data"

**The Census undercount problem:** Households lacking internet access are more likely to be people of color, impoverished, less educated, outside of the labor force, or elderly. A digital Census potentially threatens to obscure vulnerable populations within New York City that are most in need of accurate representation. The neighborhoods least likely to self-respond are the same neighborhoods most likely to need the services funded by Census data.

**The geographic granularity problem:** The city defines neighborhoods by dividing the boroughs into 59 community districts. The U.S. Census Bureau, however, divides the boroughs into 55 Public Use Micro Areas. Four community districts in New York City are combined into single Census units — meaning those four districts literally do not exist as independent units in the primary federal data infrastructure. They are invisible in the data at the level where decisions get made.

**The sample size suppression problem:** When sample sizes in a neighborhood tabulation area are too small to generate statistically reliable estimates, the data is simply suppressed — marked as unavailable. The neighborhoods with the smallest, most transient, most undocumented populations are precisely the ones most likely to disappear from the data entirely.

### Claim 3 — "The ones that barely show up are usually the ones that need the most"

*"A 2024 analysis of the Community Food Connection program found that while the Bronx has the highest food insecurity rate, it has the second-lowest number of active food pantry site hours, according to the report done by the New York City Independent Budget Office."* — Mott Haven Herald

Read that again. Highest need. Second lowest service hours.

- The Bronx has the highest deli-to-supermarket disparity across the five boroughs. In some neighborhoods, bodegas and delis outnumber supermarkets 25 to 1.
- 40% of Bronx adults self-reported that they are always, sometimes or usually stressed about affording food — the highest percentage across the five boroughs.
- When a Council Member asked DSS how they planned to fix the pantry gap in the Bronx, the official response was: *"I don't have the answer yet. It is on our radar."*

**Combined evidence paragraph (use in presentations):**
"The city's own data shows this. The Supply Gap Analysis — the primary tool driving food resource allocation — is updated once a year using Census data that is 12 to 18 months old by the time it is published. The Bronx has the highest food insecurity rate of any borough in New York City. Forty percent of Bronx adults report being stressed about affording food. And yet a 2024 Independent Budget Office analysis found the Bronx has the second-lowest number of active pantry service hours of any borough. When a City Council member asked DSS how they planned to fix that in March 2025 testimony, the official answer was: 'I don't have the answer yet.' The data was right there. The need was right there. The gap between them is exactly the problem The Grid is built to close."

---

## DATA LAYERS — THE FIVE DIMENSIONS

### Layer 1 — Food Vulnerability (existing)
SNAP enrollment, child poverty, rent burden, unemployment, non-citizen population

### Layer 2 — Housing Stability
HPD violations, displacement risk, affordable housing %, eviction rates

**Key sources:**
- NYC PLUTO — land use, building age, vacant lots, zoning
- HPD Housing Violations — active code violations by address and CD
- NYC DOB Permits — new construction and renovation activity
- Affordable Housing Production — new affordable units by CD (NYC HDC, HPD)
- NYCHA Development Map — public housing locations and resident counts
- Displacement Risk Index — NYU Furman Center

**Why it matters:** A neighborhood where violations are rising, permits for affordable units are absent, and foreclosures are climbing is a neighborhood where food insecurity will get worse regardless of what MOFP does — because the underlying housing crisis is driving the population deeper into poverty.

### Layer 3 — Cost of Living
Rent-to-income ratio, rent growth YoY, utility arrears, economic pressure index

**Key sources:**
- NYC Rent Index by NTA — NYC Rent Guidelines Board
- NYC Housing Vacancy Survey — NYC DCP
- Consumer Price Index NYC Metro — BLS
- NYC Food Price Survey — NYC DOHMH
- Utility Arrears by ZIP — Con Edison/NYPA via NYC HRA
- Eviction Filings — NYC Courts Open Data

**Why it matters:** Transforms your vulnerability score into a purchasing power score — showing not just that rent burden is high, but that it got 12% worse this year and that grocery prices in that neighborhood are 18% above the city median.

### Layer 4 — Health Burden
Life expectancy, chronic disease rates, asthma rate, mental health access

**Key sources:**
- NYC Community Health Profiles — NYC DOHMH (500+ health indicators)
- NYC SPARCS Hospital Discharge — NYSDOH
- Childhood Lead Exposure — NYC DOHMH EH Portal
- Life Expectancy by NTA — NYC DOHMH (varies by up to 10 years across NYC)
- Chronic Disease Rates — NYC DOHMH Community Health Survey

**Why it matters:** Life expectancy in the South Bronx is nearly 10 years lower than in parts of Manhattan. That is not just a health statistic — it is the cumulative result of food insecurity, housing stress, environmental exposure, and economic deprivation compounding over decades.

### Layer 5 — Economic Stress
Unemployment, median income, business closure rates, workforce participation

**Key sources:**
- NYS Department of Labor Quarterly — labor.ny.gov QCEW data
- NYC Business Atlas — active businesses, openings, closings by CD
- NYC Workforce1 Career Center Usage — NYC SBS
- Income Growth by NTA — ACS via CCC KTO Portal

**Why it matters:** When businesses close and employment falls, food insecurity follows 6 to 18 months later. This data layer gives the tool genuine predictive power.

### Composite: Equity Score
Average of all five dimensions. Answers: "For any dollar the city is considering spending, where will it do the most good — and what does the evidence say right now?"

---

## THE FUND ALLOCATION VISUALIZATION

### Scenario Builder (built)
The planner enters a budget amount. The tool calculates impact per dollar across all 59 districts, surfaces the top allocation recommendation, and shows what changes:

```
You have $5,000,000 to allocate.
Optimal allocation to maximize food security impact:

1. East Tremont — $1.2M → new pantry site + mobile market
2. University Heights — $900K → capacity expansion + SNAP outreach
3. Mott Haven — $800K → pantry hours expansion
4. Morrisania — $750K → mobile market deployment
5. Brownsville — $650K → new satellite pantry site
Remaining $700K → citywide SNAP enrollment outreach

Projected: 47,000 additional residents served per month
```

### Equity Gap Map (built)
A choropleth showing not just current vulnerability but the delta between need and investment. Neighborhoods that are high-need and low-investment show up in a different color. This is the map a Deputy Mayor actually looks at when deciding where to target new programs.

---

## WHO USES THE GRID NYC

- Mayor's Office of Food Policy
- Department of Housing Preservation & Development
- Department of Health & Mental Hygiene
- Office of Economic Opportunity
- Community Boards
- Nonprofits and foundations making grant decisions

---

## BUILD HISTORY

### Repository
`https://github.com/CurlyCr8tive/MAYOR-OFFICE-OF-FOOD-POLICY.git` (master branch)

### Tech Stack
- **Frontend:** Single-page HTML/CSS/JS (Leaflet.js for maps, Canvas for trend charts)
- **Backend:** Python HTTP server (`main.py`) — serves static files + proxies Anthropic API
- **AI:** Claude (claude-opus-4) via Anthropic API — food policy analyst persona
- **Data:** NYC Open Data, ACS Census, NYC DOHMH EH Portal, CCC KTO Portal
- **Map data:** NYC Community Districts GeoJSON (59 districts)
- **Deployment:** Railway (Python, PORT from env, Procfile)

### Commit History (most recent first)

| Commit | Feature |
|--------|---------|
| `4445369` | Add District Scorecard — all 5 dimensions in one view |
| `a954586` | Add Equity Gap Map — need vs. investment gap overlay |
| `790b593` | Update sidebar stat cards to reflect active layer |
| `dfa8935` | Add Scenario Builder — AI-optimized fund allocation tool |
| `e2d9c55` | Phase 1: Rebrand to The Grid NYC + 6-layer intelligence platform |
| `0acf1d0` | Add Procfile and clean up requirements.txt for Railway deployment |
| `995f9b5` | Add options to customize response format and save chat history |
| `c31141a` | Add PDF export functionality and enhance AI context with district data |
| `5e7c7fc` | Add specific pantry locations and names to the map display |
| `508c569` | Adapt data fetching to handle API limitations and dataset changes |
| `6249182` | Add functionality to refresh and analyze food insecurity data |
| `46699d4` | Update AI chat to use a server-side API proxy |
| `e865ea6` | Improve dashboard readability and UX with enhanced typography |
| `88011b0` | Enable AI assistant to use Anthropic API by proxying requests |
| `c77712e` | Update dashboard to display real-time vulnerability data |
| `1abc08c` | Update data pipeline and server configuration for dashboard |
| `f08897d` | Add NYC Food Insecurity Vulnerability Dashboard with API and UI components |
| `78ccd91` | Initial commit |

### Build Phases

**Phase 1 (completed this session):**
- Rebrand to The Grid NYC with tagline
- 6 layer navigation tabs: Food · Housing · Cost of Living · Health · Economic · Equity Score
- LAYER_SCORES data for all 59 community districts across 4 new dimensions
- Map choropleth recolors dynamically per layer
- Sidebar re-ranks all 59 districts by active layer score
- District detail panel shows layer-appropriate indicators

**Phase 1 additions (this session):**
- Scenario Builder with AI-optimized fund allocation
- Sidebar stat cards update per layer
- Equity Gap Map toggle (need vs. investment)
- District Scorecard (all 5 dimensions at once)

**Remaining roadmap:**
- AI context update (AI aware of all 5 layers)
- Agency Lens toggles (MOFP/HPD/DOHMH views)
- PDF export upgrade (multi-layer scorecard in brief)
- Mobile responsiveness pass

---

## SOURCE LIST (62 sources)

### Federal Policy & SNAP Cuts
- The City NYC — SNAP Work Requirements Take Effect March 1 (thecity.nyc)
- Healthbeat NYC — Here's What to Know as SNAP Work Requirements Take Effect
- Documented NY — New York SNAP Recipients Face Stricter Work Rules Starting in 2026
- City Limits — What You Need to Know: New SNAP Work Requirements in NYC
- Propel — Full Guide to SNAP Work Requirements in 2026
- NYS OTDA — SNAP Work Requirements Official State Guidance (otda.ny.gov)
- NYC Mayor's Office of Food Policy — Get Help: SNAP Guidance and Resources
- NYC Food Policy Center (Hunter College) — Debt Ceiling Deal Limits SNAP Eligibility
- New York Focus — What's Next for New Yorkers on SNAP?

### NYC Funding & Budget
- NYC Comptroller Mark Levine — Comments on NYC FY2026 Adopted Budget
- NYC Comptroller — NYC's Federal Funding: Outlook Under Trump
- NYS Office of the State Comptroller — Nutritional Assistance Federal Funding
- NYS OSC — Federal Spending by Major Funding Streams and Functions
- NYS OSC — DiNapoli Releases Analysis of Federal Funding for NYC
- NYS OSC — Review of Categorical Grants
- Citizens Budget Commission — How NYC Should Prepare for Changes in Federal Funding
- FPWA — FY2026 NYC Budget Analysis
- NYC Council — Fiscal Year 2026 Budget

### Food Insecurity Data & Research
- Robin Hood / Columbia University Poverty Tracker — Many New Yorkers Rely on Food Pantries (2024)
- New York Health Foundation — Hunger on the Rise: NYC Food Insufficiency Rates Hit New Highs (2024)
- NYS Council on Hunger and Food Policy — 2025 Annual Report
- NYS Department of Health — Self-Reported Food Insecurity Among NY Adults, BRFSS 2021
- NYC Food Policy Center (Hunter College) — Food Reports and Research Publications
- NYC Food Policy Center — Six Food Policies We're Watching in 2026
- NYC Mayor's Office of Food Policy — Food by the Numbers 2024
- NYC Mayor's Office of Food Policy — Food Forward NYC: 2-Year Progress Report (July 2023)

### The Bronx Specifically
- Mott Haven Herald — Small Businesses Address Food Insecurity in the Bronx (December 2025)
- Bronx Times — Year-in-Review: Food Insecurity Surges in the Bronx (2024)
- Bronx Times — State Report Shows Food Insecurity Affects 39% of Bronx Adults
- Bronx Times — Our Forgotten Borough: Bronx Food Pantries Brace for Surge (April 2026)
- Grassroots Grocery — The Bronx Paradox
- PMC / NIH — Predictors of Food Insecurity and Childhood Hunger in the Bronx During COVID-19

### CFC Program & Resource Allocation
- NYC Mayor's Office of Food Policy — Community Food Connection FAQ (March 2025)
- NYC Mayor's Office of Food Policy — Supply Gap Analysis FAQ
- NYC Mayor's Office of Food Policy — Supply Gap Overview and Map
- NYC Mayor's Office of Food Policy — CFC Impact Report
- NYC Mayor's Office of Food Policy — Community Food Connection Program Page
- NYC Independent Budget Office — Yours, Mine, and Hours: Analysis of the CFC Program (November 2024)
- NYC City Meetings — CFC Program Funding and Distribution Challenges (March 17, 2025)

### Neighborhood & District Data
- NYC Council Data Team — Emergency Food in NYC Dashboard
- NYU Furman Center — State of New York City's Housing and Neighborhood Report
- NYU Furman Center — NYC Neighborhood Data Profiles (CoreData.nyc)
- NYC Mayor's Office of Food Policy — About MOFP
- Where We Live NYC 2025 — Goal 6: Confronting Segregation

### Data Sources Powering Vulnerability Score
- Citizens Committee for Children of NYC (CCC) — KTO Data Portal (SNAP, poverty data)
- NYC DOHMH — Environment and Health Data Portal (child poverty, rent burden, unemployment)
- NYC Open Data (HRA) — SNAP Population by Community District (dataset: jye8-w4d7)
- NYC Open Data (311) — Daily Food Complaint Data (dataset: erm2-nwe9)
- NYC Open Data (CFC) — Pantry Utilization Data (dataset: unw5-rvbq)
- U.S. Census Bureau — American Community Survey 5-Year Estimates (2017–2021)
- U.S. Census Bureau — American Community Survey 1-Year Estimates (2023)

### Census & Data Infrastructure
- NYC Comptroller — Census and the City: Overcoming NYC's Digital Divide
- Baruch College Research Guide — NYC Neighborhood Data Geography and Sources
- NYC Opportunity — Poverty Data Tool

### Machine Learning & Optimization Research
- ScienceDirect — Potential and Limitations of ML for Forecasting Acute Food Insecurity (2025)
- Nature — Forecasting Trends in Food Security with Real Time Data (2024)
- Nature Food — ML Can Guide Food Security Efforts When Primary Data Are Not Available (2022)
- Cambridge Core — Food Security Analysis and Forecasting: ML Case Study in Southern Malawi
- ScienceDirect — A Data-Driven Approach Improves Food Insecurity Crisis Prediction (2019)
- arXiv — Modeling Urban Food Insecurity with Google Street View Images (2025)

### Google Maps & Technical Sources
- Google Maps Platform — Data-Driven Styling for Boundaries Overview
- Google Maps Platform — Make a Choropleth Map
- Google Maps Platform — See Your Data in Real Time with Data-Driven Styling
- Google Maps Platform — Announcing Data-Driven Styling
- Google Maps Platform — Import GeoJSON Data into Maps
- NYC Environmental Health (nycehs) GitHub — NYC Community Districts GeoJSON

### NYC Planning & Land Use
- Citizens Budget Commission — Improving NYC's Land Use Decision-Making Process (2022)
- Manhattan Institute — Reforming NYC's Land-Use Process (2025)
- NYC City Council — Community Planning Framework Press Release (May 2025)
- NYC HPD — NYC Neighborhood Planning Playbook

---

## NYC BOROUGH GRID HISTORY (context for The Grid name)

**Manhattan** — Pure grid. Commissioner's Plan of 1811 laid out 12 avenues + 155 numbered streets above Houston Street. Below Houston = colonial-era crooked streets from when it was New Amsterdam.

**The Bronx** — Partial grid. Southern/western parts follow Manhattan's system (annexed 1870s–1890s). The Grand Concourse (1909) is modeled on the Champs-Élysées — cuts diagonally through the grid. Northern Bronx breaks into terrain-following streets where hills pushed back.

**Brooklyn** — A grid of grids that don't align. Was dozens of independent villages before 1898 consolidation. Each neighborhood has its own grid oriented differently. The famous Atlantic/Flatbush/4th Ave six-way intersection is three grid systems colliding at one point.

**Queens** — Most chaotic. Assembled from the largest number of independent communities. Streets that change names mid-block. The same number appearing as street, avenue, road, drive, place, and lane within blocks of each other. The 1930s numbering system was overlaid on streets that didn't cooperate — hence all the gaps and jogs.

**Staten Island** — Topography wins. Significant hills, wetlands, and irregular coastline made comprehensive grid planning impractical. Streets follow the natural landscape. North Shore has the most legible patterns; South Shore has postwar suburban curvilinear streets — the deliberate anti-grid.

**Why this matters for The Grid:** The five boroughs were never designed as a unified system. They were assembled from dozens of independent municipalities. The community district system (59 districts) was itself an attempt in the 1960s–1970s to impose a rational administrative layer over this chaotic inherited geography. Your tool does the same thing at the data level. The Grid NYC is the recurring attempt to make a sprawling, chaotic, historically assembled city governable, equitable, and legible.

---

*Document compiled April 15, 2026. Repository: CurlyCr8tive/MAYOR-OFFICE-OF-FOOD-POLICY*
