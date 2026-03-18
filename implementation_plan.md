# File Reorganization Plan

## Problem

The project currently has **3 overlapping data directories**:

| Directory | Contents | Role |
|---|---|---|
| `stock_data/{stock_id}/` | [data.csv](file:///d:/Jay%20PhD/Code/stock/revenue/1268/data.csv), [financial.csv](file:///d:/Jay%20PhD/Code/stock/revenue/1268/financial.csv), `price.csv`, etc. | Main cache (used by [stock_cache.py](file:///d:/Jay%20PhD/Code/stock/analysis/stock_cache.py)) |
| `revenue/{stock_id}/` | [data.csv](file:///d:/Jay%20PhD/Code/stock/revenue/1268/data.csv), [financial.csv](file:///d:/Jay%20PhD/Code/stock/revenue/1268/financial.csv) | **Duplicate** — same files, same stock IDs |
| `analysis/Stock_base_data/` | `cache_meta.json`, `stock_info.csv` | Old metadata dir (orphaned) |

The source code (`analysis/stock_cache.py`) has `CACHE_DIR = stock_data/` and also has a dead `REVENUE_BASE_DIR` constant and unused `_save_to_revenue_folder()` method which caused the duplicate `revenue/` directory to be created.

**Goal:** Consolidate everything into a single, clean structure:
```
stock/
├── main.py
├── migrate_data.py
├── .gitignore
├── analysis/          ← all Python source files
│   ├── stock_cache.py
│   ├── ai_analyst.py
│   ├── ...other .py files
│   └── templates/
└── data/              ← unified data directory (renamed from stock_data)
    ├── cache_meta.json
    ├── stock_info.csv
    └── {stock_id}/
        ├── price.csv
        ├── institutional.csv
        ├── margin.csv
        ├── per_pbr.csv
        ├── revenue.csv
        └── financial.csv
```

## User Review Required

> [!IMPORTANT]
> **`revenue/` and `stock_data/` have identical per-stock files for tested stock 1268.** Before deleting `revenue/`, we need to check: do **any** stocks exist in `revenue/` that are **missing** from `stock_data/`? The plan includes a pre-check script to verify this before any deletion.

> [!WARNING]
> `analysis/Stock_base_data/` only has `cache_meta.json` and `stock_info.csv`. We will move these two files into the consolidated `data/` directory. The `Stock_base_data` folder in `analysis/` can then be deleted.

> [!NOTE]
> The rename from `stock_data/` → `data/` is optional. If you prefer to keep the name `stock_data/`, just let me know and I'll skip that rename.

## Proposed Changes

### Step 1: Pre-check script (verify no data loss before restructure)

Run a quick PowerShell/Python command to compare which stocks are in `revenue/` vs `stock_data/` and check for any that exist in one but not the other.

### Step 2: Code cleanup in `analysis/stock_cache.py`

#### [MODIFY] [stock_cache.py](file:///d:/Jay%20PhD/Code/stock/analysis/stock_cache.py)

- Rename `CACHE_DIR` path from `stock_data` → `data`
- Remove dead constant `REVENUE_BASE_DIR`
- Remove unused method `_save_to_revenue_folder()`
- Remove duplicate `_save_meta` call and `self.batch_delay` assignment (line 38 duplicate)
- Remove orphaned `download_deep_fundamental` hardcoded path (`data.csv`) — fix it to consistently use `revenue.csv`

### Step 3: Move metadata files

Move `analysis/Stock_base_data/cache_meta.json` and `analysis/Stock_base_data/stock_info.csv` into `data/` (the main cache dir), then delete `analysis/Stock_base_data/`.

> [!NOTE]
> `data/stock_info.csv` may already exist in `stock_data/` — if so, keep the version in `stock_data/`, don't overwrite.

### Step 4: Merge `revenue/` data into `stock_data/` (or `data/`)

For each stock in `revenue/{stock_id}/`:
- If the same file exists in `stock_data/{stock_id}/`, verify they are identical (skip if so)
- If missing from `stock_data/`, copy it over

Then delete the `revenue/` directory.

### Step 5 (Optional): Rename `stock_data/` → `data/`

A simple folder rename. The `CACHE_DIR` in `stock_cache.py` would be updated to match.

## Verification Plan

### Automated check
```powershell
# Check if any stocks exist in revenue/ but NOT in stock_data/
python -c "
import os
rev = set(d for d in os.listdir('revenue') if os.path.isdir(f'revenue/{d}'))
sd  = set(d for d in os.listdir('stock_data') if os.path.isdir(f'stock_data/{d}'))
only_in_rev = rev - sd
print('Only in revenue/:', only_in_rev if only_in_rev else 'None (safe to delete)')
"
```

### Manual check after completion
1. Run `python main.py --cache-status` — should still show the same stock count
2. Run `python main.py` and open `http://localhost:5000` — app should still function normally
