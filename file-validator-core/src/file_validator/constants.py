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
Constants for file validation.

This module contains color constants and other configuration values used throughout
the file validator, particularly for Excel export styling.
"""

from enum import StrEnum


class HeaderColor(StrEnum):
    """Header and background colors for Excel sheets."""

    LIGHT_BLUE = "D9E1F2"  # Standard headers
    DARK_BLUE = "4472C4"  # Source data headers
    GREEN = "70AD47"  # Target data headers
    LIGHT_GREEN = "E2EFDA"  # Target sub-headers
    PEACH = "FCE4D6"  # Error/reject headers
    LIGHT_GREEN_MATCH = "C6EFCE"  # Match indicators


class StatusColor(StrEnum):
    """Status indicator colors for validation results."""

    MATCH = "C6EFCE"  # Light green for matches
    MISMATCH = "FFCCCC"  # Light red for mismatches


class TextColor(StrEnum):
    """Text colors for various UI elements."""

    BLACK = "000000"  # Default text
    WHITE = "FFFFFF"  # Text on dark backgrounds
    DARK_BLUE = "1F4E78"  # Titles
    RED = "C00000"  # Errors/rejects
    GREEN = "006100"  # Success messages
