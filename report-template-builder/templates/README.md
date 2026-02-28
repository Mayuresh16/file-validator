# Report Template Builder

**Version:** 1.0  
**Last Updated:** February 18, 2026  
**Status:** Maintenance Mode

Modular HTML report template structure for the File Validator tool.

---

> **IMPORTANT**: The current working `report_template.html` was restored from `../../backups/report_template.html`.  
> The modular structure in this directory is for **future development** and maintenance.  
> Running `python build_template.py` will **overwrite** the main template with the modular version.

---

---

## Overview

This directory contains the modularized HTML report template for the File Validator tool. The original monolithic `report_template.html` (4K+ lines) has been split into organized, maintainable modules.

**Purpose:** Improve maintainability by separating concerns into focused CSS, JavaScript, and HTML partial files that can be compiled into a single standalone HTML template.

---

## Table of Contents

1. [Overview](#overview)
2. [Directory Structure](#directory-structure)
3. [How It Works](#how-it-works)
4. [Module Descriptions](#module-descriptions)
5. [Usage](#usage)
6. [Development Workflow](#development-workflow)
7. [Template Features](#template-features)

---

## Directory Structure

```
templates/
├── build_template.py           # Script to compile modules into single HTML file
├── report_template_modular.html # Jinja2 template with includes (for reference)
├── report_template_compiled.html # Compiled standalone HTML template
├── css/                        # Modular CSS stylesheets
│   ├── base.css               # Core styles, tables, scrollbars
│   ├── components.css         # Job section, legend, summary, insights
│   ├── comparison.css         # View toggle, cell styles, inline view
│   ├── workspace.css          # Dual pane layout, sticky headers
│   ├── char-diff.css          # Character-level diff highlighting, modal
│   ├── search-filter.css      # Search bar, filters, copy buttons
│   ├── controls.css           # Theme toggle, navigation, shortcuts
│   └── dark-mode.css          # Dark theme overrides
├── js/                         # Modular JavaScript files
│   ├── view-switcher.js       # Side-by-side, stacked, inline view switching
│   ├── sync-scroll.js         # Synchronized scrolling between panes
│   ├── char-diff.js           # Character diff highlighting and modal
│   ├── search-filter.js       # Global search and filter functionality
│   ├── navigation.js          # Keyboard shortcuts and diff navigation
│   ├── theme.js               # Dark mode toggle and preferences
│   ├── timezone.js            # Timezone switching for timestamps
│   └── utilities.js           # Copy buttons, row numbers, lazy loading
└── partials/                   # Reusable HTML template fragments
    ├── job_section.html       # Job ID, file comparison header, timestamps
    ├── insights_panel.html    # Data quality insights cards
    ├── search_filter.html     # Search bar and filter buttons
    ├── view_controls.html     # View toggle buttons
    ├── legend.html            # Color legend for status indicators
    ├── summary.html           # Summary stats and primary keys
    ├── file_naming.html       # File naming convention analysis
    ├── header_comparison.html # Header lines comparison views
    ├── trailer_comparison.html # Trailer lines comparison views
    ├── rejected_rows.html     # Rejected rows section
    ├── data_comparison.html   # Main data comparison tables
    └── ui_controls.html       # Fixed UI elements (modal, buttons, overlay)
```

## How It Works

### For Development

1. **Edit individual modules** - Make changes to specific CSS, JS, or HTML partial files
2. **Run build script** - Execute `python build_template.py` to compile everything
3. **Test** - The compiled template is automatically written to `../report_template.html`

### Build Process

The `build_template.py` script:
1. Reads all CSS files and concatenates them
2. Reads all JS files and concatenates them
3. Reads all HTML partial files
4. Combines everything into a single standalone HTML file
5. Writes to `../report_template.html` (used by report_generator.py)

### Why Inline Everything?

The generated HTML reports need to be **self-contained** and portable:
- No external CSS/JS file dependencies
- Can be opened in any browser without a web server
- Easy to share via email or file transfer
- Works offline

## Module Descriptions

### CSS Modules

| File | Purpose |
|------|---------|
| `base.css` | Core body styles, table styling, scrollbar customization |
| `components.css` | Job section header, legend, summary stats, insights panel |
| `comparison.css` | Cell styling for matches/mismatches, inline view layout |
| `workspace.css` | Dual-pane workspace, side-by-side/stacked layouts |
| `char-diff.css` | Character-level diff highlighting, detail modal |
| `search-filter.css` | Search bar, filter buttons, copy buttons, row numbers |
| `controls.css` | Fixed position controls (theme toggle, navigation) |
| `dark-mode.css` | Complete dark theme overrides |

### JavaScript Modules

| File | Purpose |
|------|---------|
| `view-switcher.js` | Toggle between side-by-side, stacked, inline views |
| `sync-scroll.js` | Synchronized scrolling between source/target panes |
| `char-diff.js` | Character-by-character diff analysis and modal |
| `search-filter.js` | Global search across all columns, filter by status |
| `navigation.js` | Keyboard shortcuts, navigate between differences |
| `theme.js` | Dark mode toggle and preference persistence |
| `timezone.js` | Switch between LOCAL, UTC, IST, ET timezones |
| `utilities.js` | Copy buttons, row numbers, button hover effects |

### HTML Partials

| File | Purpose |
|------|---------|
| `job_section.html` | Report header with file names, job ID, timestamps |
| `insights_panel.html` | Data quality KPI cards |
| `search_filter.html` | Search input and filter buttons |
| `view_controls.html` | View mode toggle buttons |
| `legend.html` | Color-coded legend for status types |
| `summary.html` | Summary statistics and primary key display |
| `file_naming.html` | File naming convention analysis |
| `header_comparison.html` | Header line comparison (all views) |
| `trailer_comparison.html` | Trailer line comparison (all views) |
| `rejected_rows.html` | Rows that failed parsing |
| `data_comparison.html` | Main data comparison tables (all views) |
| `ui_controls.html` | Modal, theme toggle, nav buttons, shortcuts |

## Making Changes

### Adding New CSS

1. Create a new `.css` file in the `css/` directory
2. Add the filename to the `css_files` list in `build_template.py`
3. Run `python build_template.py`

### Adding New JavaScript

1. Create a new `.js` file in the `js/` directory
2. Add the filename to the `js_files` list in `build_template.py`
3. Run `python build_template.py`

### Adding New HTML Partial

1. Create a new `.html` file in the `partials/` directory
2. Add entry to the `partials` dict in `build_template.py`
3. Add the include location in the template section of the build script
4. Run `python build_template.py`

## Benefits of Modular Structure

1. **Maintainability** - Each file has a single responsibility
2. **Readability** - Smaller files are easier to understand
3. **Collaboration** - Multiple developers can work on different modules
4. **Testing** - Individual modules can be tested in isolation
5. **Reusability** - Modules can be reused in other templates
6. **Version Control** - Better diff visibility for changes

## Usage

### Building the Template

```bash
# From the templates directory
cd report-template-builder/templates

# Run the build script
python build_template.py

# Or with uv
uv run python build_template.py
```

**Output:**
- `report_template_compiled.html` - Compiled template in this directory
- `../../file-validator-core/src/file_validator/report_template.html` - Copied to core package

### Testing the Template

After building, test the template by running a validation:

```bash
# From repository root
cd ../../

# Run validation to generate a test report
uv run python -c "
from file_validator.auditor import FileAuditor
from file_validator.config import FileConfig
from file_validator.report_generator import generate_html_report

# Your test code here
"
```

---

## Development Workflow

### 1. Make Changes to Modules

Edit the specific module you need to change:

**Example: Update dark mode colors**
```bash
# Edit the dark mode CSS
vim css/dark-mode.css
```

**Example: Add new JavaScript feature**
```bash
# Create or edit JavaScript module
vim js/my-feature.js
```

### 2. Update Build Script (if needed)

If you added a new file, update `build_template.py`:

```python
# Add to css_files list
css_files = [
    'base.css',
    'components.css',
    # ... existing files
    'my-new-styles.css',  # Add your new file
]

# Or add to js_files list
js_files = [
    'view-switcher.js',
    # ... existing files
    'my-feature.js',  # Add your new file
]
```

### 3. Build and Test

```bash
# Build the template
python build_template.py

# Check the output
ls -lh report_template_compiled.html

# Test by generating a report
cd ../../
uv run pytest file-validator-core/tests/test_file_validator.py
```

### 4. Verify Changes

Open a generated report in a browser and verify:
- ✅ CSS changes are applied
- ✅ JavaScript features work
- ✅ No console errors
- ✅ Dark mode still works
- ✅ All view modes function

---

## Template Features

### Interactive Features

1. **View Modes**
   - Side-by-side: Dual panes with source/target
   - Stacked: Single pane with source over target
   - Inline: Alternating source/target columns

2. **Dark Mode**
   - Toggle with button or keyboard shortcut
   - Persistent preference (localStorage)
   - Theme-appropriate colors

3. **Search & Filter**
   - Global search across all columns
   - Filter by status: All, Matched, Mismatched, Source Only, Target Only
   - Real-time results

4. **Navigation**
   - Keyboard shortcuts (?, n/p, f, etc.)
   - Jump to next/previous difference
   - Smooth scrolling

5. **Character Diff**
   - Click any mismatch cell
   - Modal with char-by-char comparison
   - Highlighted differences

6. **Synchronized Scrolling**
   - Scroll source/target panes together
   - Toggle on/off
   - Smooth animation

7. **Timezone Support**
   - Switch between LOCAL, UTC, IST, ET
   - Updates all timestamps
   - Persistent preference

### Visual Components

1. **File Naming Section**
   - Side-by-side file cards
   - Pattern analysis table
   - Match indicators

2. **Primary Key Indicators**
   - 🔑 icons on PK columns
   - Green highlighting
   - Dedicated PK section

3. **Insights Panel**
   - Match percentage gauge
   - Row distribution
   - Quality metrics

4. **Legend**
   - Color-coded status indicators
   - PK highlighting explanation
   - Clear visual guide

---

## Template Variables

The report template expects these Jinja2 variables from `report_generator.py`:

**Primary Data:**
- `pks` - List of primary key column names
- `cols` - List of data column names  
- `data` - List of comparison result rows
- `sample_data` - Sample matching rows (for 100% match scenarios)

**Comparison Results:**
- `header_comparison` - Header line comparison data
- `trailer_comparison` - Trailer line comparison data
- `source_rejects` / `target_rejects` - Rejected row data

**File Information:**
- `source_filename` / `target_filename` - File names
- `source_full_path` / `target_full_path` - Full file paths
- `source_file_type` / `target_file_type` - File types (csv, psv, fwf)
- `source_delimiter` / `target_delimiter` - Delimiters
- `source_col_specs` / `target_col_specs` - FWF column specs

**Metadata:**
- `job_id` - Unique job identifier
- `report_time_local` / `report_time_utc` / etc. - Timestamps in various timezones
- `source_count` / `target_count` - Row counts
- `matching_rows` / `match_percentage` - Match statistics
- `missing_in_source` / `missing_in_target` - Missing row counts
- `total_sample_records` - Count of sample records
- `source_file_size` / `target_file_size` - File sizes

---

## Troubleshooting

### Build Script Issues

**Template not updating:**
```bash
# Check build script output
python build_template.py

# Verify file was copied
ls -lh ../../file-validator-core/src/file_validator/report_template.html
```

**Missing files error:**
```bash
# Ensure all CSS/JS files exist
ls css/
ls js/
ls partials/

# Check build_template.py file lists match actual files
```

### Template Rendering Issues

**Variables not showing:**
- Check Jinja2 variable names match exactly
- Verify data is passed from `report_generator.py`
- Check for typos in template

**JavaScript errors:**
- Open browser console (F12)
- Check for syntax errors
- Verify all functions are defined

**CSS not applying:**
- Check CSS is in the `<style>` block
- Verify selectors match HTML structure
- Check for CSS conflicts

---

## Contributing

When contributing changes to the template:

1. **Test thoroughly** - All view modes, dark/light themes
2. **Document changes** - Update this README if adding features
3. **Follow conventions** - Use existing naming patterns
4. **Keep modular** - Don't create monolithic files
5. **Build before commit** - Always run build script

---

## License

Internal use only - Verizon proprietary.

---

## Author

**Mayuresh Kedari**  
Email: mayuresh.kedari@onixnet.com

---

## See Also

- [File Validator Core](../../file-validator-core/README.md) - Core library
- [File Validator WebServer](../../file-validator-webserver/README.md) - Web UI
- [Main README](../../README.md) - Project overview

