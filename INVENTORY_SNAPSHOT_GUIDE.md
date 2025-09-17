# Inventory Snapshot System Guide

This guide explains how to use the new snapshot-based inventory system, which maintains persistent inventory counts that aren't affected by transaction timestamps.

## Overview

The system now uses snapshots (point-in-time records of inventory counts) as the source of truth for inventory levels, rather than always recalculating from all transactions. This solves the problem where newer reset transactions would override historical usage transactions.

## Available Scripts

### 1. Reset Inventory Counts

```
python scripts/reset_inventory_counts.py [--count COUNT] [--date YYYY-MM-DD] [--all] [--dry-run] [--notes NOTES]
```

Creates a new inventory snapshot with all items set to the specified count.

- `--count`: The target count to set for each item (default: 500)
- `--date`: Date for the snapshot (default: today)
- `--all`: Process all items, not just recently active ones
- `--dry-run`: Don't actually save changes, just report what would be done
- `--notes`: Optional notes for the snapshot

### 2. Check Inventory As Of Date

```
python scripts/check_inventory_as_of_date.py [--date YYYY-MM-DD] [--item ITEM_ID] [--verbose]
```

Displays inventory counts as of a specific date.

- `--date`: Date to check in YYYY-MM-DD format (default: today)
- `--item`: Specific item ID to check
- `--verbose`: Show additional information like available snapshots

### 3. Create Snapshot From Current

```
python scripts/create_snapshot_from_current.py [--date YYYY-MM-DD] [--notes NOTES] [--dry-run]
```

Creates a new snapshot based on current calculated levels as of a specific date.

- `--date`: Date for the snapshot (default: today)
- `--notes`: Optional notes for the snapshot
- `--dry-run`: Don't actually save the snapshot

## Typical Workflow

1. **Process Historical POS Data**:
   ```
   python scripts/run_pos_usage_for_date.py YYYYMMDD
   ```

2. **Create a Snapshot of the Resulting Levels**:
   ```
   python scripts/create_snapshot_from_current.py --date YYYY-MM-DD
   ```

3. **Reset Inventory for Testing**:
   ```
   python scripts/reset_inventory_counts.py --count 500
   ```

4. **Check Inventory Levels**:
   ```
   python scripts/check_inventory_as_of_date.py --date YYYY-MM-DD
   ```

## Technical Details

- Snapshots are stored in `data/inventory_snapshots.json`
- The UI and reports will show inventory levels based on the most recent snapshot plus any transactions that have occurred since
- Historical queries (checking inventory as of a specific date) will find the nearest snapshot before the reference date and apply transactions up to that date

## Benefits

- Inventory counts are now persistent, not just derived from transactions
- Reset operations won't interfere with historical data analysis
- You can easily create a reliable baseline at any point in time
- Inventory calculation is more efficient since it doesn't need to process all historical transactions
