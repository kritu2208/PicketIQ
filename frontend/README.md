# PicketIQ Frontend

**Next.js + TypeScript + Tailwind CSS Business Intelligence Command Center**

> *"When the numbers move, PicketIQ finds out why."*

---

## Overview

The PicketIQ Frontend provides an evidence-driven, interactive command-center dashboard for browsing statistical anomalies in business KPIs, executing deterministic investigations against the live Olist Brazilian E-Commerce database, and reviewing evidence-grounded AI root-cause analyses.

### Capabilities Implemented (Phase 6)

1. **Anomaly Feed / Dashboard**:
   - Live stream of detected statistical anomalies loaded directly from PostgreSQL via FastAPI backend.
   - Filter by business KPI metric (`order_count`, `daily_revenue`, `cancellation_rate`, etc.).
   - Filter by severity tier (`High` $|z| \ge 5.0$, `Medium`, `Low`).
   - Sort by strongest statistical deviation ($|z|$-score) or chronological event date.
   - Real-time search across metric names, dates (`YYYY-MM-DD`), and record IDs (`#19`).
   - Visual severity badges and investigation completion indicators.

2. **Anomaly Detail Workspace**:
   - Complete anomaly baseline details: actual value, expected rolling baseline, net delta, percentage change, and $|z|$-score deviation.
   - One-click **"Investigate Anomaly"** / **"Re-Run Investigation"** action.
   - Real-time scanning state with multi-step progress indicators.

3. **Multi-Dimensional Evidence Chain (Phase 5B)**:
   - **Step 1: Regional Segment Breakdown (`customer_state`)**: Top contributor (`SP`), percentage share of net deviation (`+38.39%`), and top 5 state contribution table.
   - **Step 2: Day-of-Week Seasonality Analysis**: Incident weekday (`Friday`), same-weekday baseline mean & standard deviation, same-DOW $|z|$-score (`+40.32`), and non-seasonal shift verdict.
   - **Step 3: Trajectory & Recent Trend Analysis**: 14-day trailing classification (`SUDDEN`), single-day step jump (`+893 orders`), baseline mean, and regression daily slope ($\beta$).

4. **Evidence-Grounded AI Root Cause (Phase 5D)**:
   - Identified Primary Root Cause headline.
   - Detailed analytical explanation.
   - Confidence assessment (`HIGH` / `MEDIUM` / `LOW`).
   - Affected segment tag (`SP`).
   - Verified step citations citing Steps 1, 2, and 3.
   - Recommended operational mitigation action.
   - Programmatic validation audit badge (`AUDIT PASSED`).

---

## Setup & Running Locally

### 1. Configure Environment Variables

Create `.env.local` in `frontend/`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 2. Install Dependencies

```powershell
npm install
```

### 3. Run Development Server

```powershell
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### 4. Production Build

```powershell
npm run build
npm run start
```
