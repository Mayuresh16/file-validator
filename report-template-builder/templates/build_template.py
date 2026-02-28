# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the MIT License (the "License"); you may not
# use this file except in compliance with the License.
#
# MIT License
#
# Copyright (c) 2026 Mayuresh Kedari
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom
# the Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
# KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS
# OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
Template Builder for File Validator Report.

This script compiles all modular template parts into a single standalone HTML template.
This is necessary because the generated HTML report needs to be self-contained
without external file dependencies.

Usage:
    python build_template.py

This will generate/update the report_template.html file in the parent directory.
"""

from __future__ import annotations

import re
from pathlib import Path


def build_template():
    """Build the complete template from modular parts."""
    templates_dir = Path(__file__).parent

    # Read all CSS files
    css_files = [
        "css/base.css",
        "css/components.css",
        "css/comparison.css",
        "css/workspace.css",
        "css/char-diff.css",
        "css/search-filter.css",
        "css/controls.css",
        "css/dark-mode.css",
    ]

    css_content = ""
    for css_file in css_files:
        css_path = templates_dir / css_file
        if css_path.exists():
            css_content += f"\n        /* ===== {css_file} ===== */\n"
            css_content += css_path.read_text(encoding="utf-8")

    # Read all JS files - organized by script block
    #  1: View switching & sync scrolling
    js_block1_files = [
        "js/view-switcher.js",
        "js/sync-scroll.js",
    ]

    # Script Block 2: Pagination & character diff
    js_block2_files = [
        "js/pagination.js",
        "js/char-diff.js",
    ]

    # Script Block 3: Enhancements (search, navigation, theme, timezone, utilities)
    js_block3_files = [
        "js/search-filter.js",
        "js/navigation.js",
        "js/theme.js",
        "js/timezone.js",
        "js/utilities.js",
    ]

    def read_js_files(file_list):
        contents = ""
        for js_file in file_list:
            js_path = templates_dir / js_file
            if js_path.exists():
                contents += f"\n        // ===== {js_file} =====\n"
                contents += js_path.read_text(encoding="utf-8")
        return contents

    js_block1 = read_js_files(js_block1_files)
    js_block2 = read_js_files(js_block2_files)
    js_block3 = read_js_files(js_block3_files)

    # Read all partial HTML files
    partials = {
        "ui_controls": "partials/ui_controls.html",
        "job_section": "partials/job_section.html",
        "insights_panel": "partials/insights_panel.html",
        "search_filter": "partials/search_filter.html",
        "view_controls": "partials/view_controls.html",
        "legend": "partials/legend.html",
        "summary": "partials/summary.html",
        "file_naming": "partials/file_naming.html",
        "header_comparison": "partials/header_comparison.html",
        "trailer_comparison": "partials/trailer_comparison.html",
        "rejected_rows": "partials/rejected_rows.html",
        "data_comparison": "partials/data_comparison.html",
    }

    partial_contents = {}
    for name, partial_file in partials.items():
        partial_path = templates_dir / partial_file
        if partial_path.exists():
            content = partial_path.read_text(encoding="utf-8")
            # Remove Jinja comments that are just for documentation
            content = re.sub(r"\{#.*?#}", "", content, flags=re.DOTALL)
            partial_contents[name] = content.strip()

    # Build the complete template with 3 script blocks (matching original structure)
    template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <title>Validation Report</title>
    <meta charset="UTF-8">
    <style>
{css_content}
    </style>
</head>
<body class="side-view">
    {partial_contents.get("ui_controls", "")}

    <div class="container">
        <h1>📊 Data File Validation Report</h1>

        {partial_contents.get("job_section", "")}

        {partial_contents.get("insights_panel", "")}

        {partial_contents.get("search_filter", "")}

        {partial_contents.get("view_controls", "")}

        {partial_contents.get("legend", "")}

        {partial_contents.get("summary", "")}

        {partial_contents.get("file_naming", "")}

        {partial_contents.get("header_comparison", "")}

        {partial_contents.get("trailer_comparison", "")}

        {partial_contents.get("rejected_rows", "")}

        {partial_contents.get("data_comparison", "")}
    </div>

    <script>
        // ===== SCRIPT BLOCK 1: View Switching & Sync Scrolling =====
{js_block1}
    </script>

    <script>
        // ===== SCRIPT BLOCK 2: Pagination & Character Diff =====

        // Pagination variables
        let sideCurrentlyVisible = Math.min(20, {{{{ total_sample_records }}}});
        const sideTotalRecords = {{{{ total_sample_records }}}};
        let inlineCurrentlyVisible = Math.min(20, {{{{ total_sample_records }}}});
        const inlineTotalRecords = {{{{ total_sample_records }}}};

{js_block2}
    </script>

    <script>
        // ===== SCRIPT BLOCK 3: Enhancements =====

        // Timezone data - LOCAL is the system timezone where report was generated
        const timezoneData = {{
            local: "{{{{ report_time_local }}}}",
            utc: "{{{{ report_time_utc }}}}",
            ist: "{{{{ report_time_ist }}}}",
            et: "{{{{ report_time_et }}}}"
        }};

        // Store local timezone info for display
        const localTzName = "{{{{ local_tz_name }}}}";
        const localTzAbbr = "{{{{ local_tz_abbr }}}}";

{js_block3}

        // ===== CENTRALIZED INITIALIZATION =====
        document.addEventListener('DOMContentLoaded', function() {{
            console.log('🚀 Initializing report components...');

            // Script Block 1: View & Scroll
            const savedView = localStorage.getItem('comparisonView') || 'side';
            switchView(savedView);
            initSyncScrolling();
            applyStickyHeaders();

            // Script Block 2: Character diff
            makeClickableMismatchCells();
            applyCharDiffToInlineView();

            // Script Block 3: Enhancements
            collectAllRows();
            setupSearchFilterListeners();
            setupKeyboardShortcuts();
            setupNavigationListeners();
            setTimeout(setupRowHighlighting, 200);
            setupThemeToggle();
            loadUserPreferences();
            initializeTimezone();

            // Utilities
            setTimeout(addCopyButtons, 500);
            setTimeout(addRowNumbers, 100);
            addButtonHoverEffects();

            console.log('✨ All components initialized successfully!');
        }});
    </script>
</body>
</html>
"""

    # Write the compiled template
    output_path = templates_dir.parent / "report_template.html"
    output_path.write_text(template, encoding="utf-8")

    print(f"✅ Template built successfully: {output_path}")
    print(f"   - CSS files: {len(css_files)}")
    print(f"   - JS Block 1 files: {len(js_block1_files)}")
    print(f"   - JS Block 2 files: {len(js_block2_files)}")
    print(f"   - JS Block 3 files: {len(js_block3_files)}")
    print(f"   - Partial files: {len(partials)}")

    # Also save a backup of the modular version
    modular_output = templates_dir / "report_template_compiled.html"
    modular_output.write_text(template, encoding="utf-8")
    print(f"   - Compiled copy saved to: {modular_output}")


if __name__ == "__main__":
    build_template()
