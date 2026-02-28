/**
 * View Switching Module
 * Handles switching between side-by-side, stacked, and inline views
 */

function switchView(mode) {
    const body = document.body;
    const sideBtn = document.getElementById('sideViewBtn');
    const stackedBtn = document.getElementById('stackedViewBtn');
    const inlineBtn = document.getElementById('inlineViewBtn');
    const workspace = document.getElementById('comparisonWorkspace');
    const headerWorkspace = document.getElementById('headerWorkspace');
    const trailerWorkspace = document.getElementById('trailerWorkspace');
    const stackedHint = document.getElementById('stackedViewHint');
    const stackedHeaderHint = document.getElementById('stackedHeaderHint');
    const stackedTrailerHint = document.getElementById('stackedTrailerHint');

    // Remove all active classes (with null checks)
    if (sideBtn) sideBtn.classList.remove('active');
    if (stackedBtn) stackedBtn.classList.remove('active');
    if (inlineBtn) inlineBtn.classList.remove('active');

    if (mode === 'side') {
        body.className = 'side-view';
        if (sideBtn) sideBtn.classList.add('active');
        if (workspace) {
            workspace.className = 'comparison-workspace vertical side-view-only';
        }
        if (headerWorkspace) {
            headerWorkspace.className = 'comparison-workspace vertical side-view-only';
        }
        if (trailerWorkspace) {
            trailerWorkspace.className = 'comparison-workspace vertical side-view-only';
        }
        if (stackedHint) stackedHint.style.display = 'none';
        if (stackedHeaderHint) stackedHeaderHint.style.display = 'none';
        if (stackedTrailerHint) stackedTrailerHint.style.display = 'none';
    } else if (mode === 'stacked') {
        body.className = 'side-view';  // Use side-view class to show workspace
        if (stackedBtn) stackedBtn.classList.add('active');
        if (workspace) {
            workspace.className = 'comparison-workspace horizontal side-view-only';
        }
        if (headerWorkspace) {
            headerWorkspace.className = 'comparison-workspace horizontal side-view-only';
        }
        if (trailerWorkspace) {
            trailerWorkspace.className = 'comparison-workspace horizontal side-view-only';
        }
        if (stackedHint) stackedHint.style.display = 'block';
        if (stackedHeaderHint) stackedHeaderHint.style.display = 'block';
        if (stackedTrailerHint) stackedTrailerHint.style.display = 'block';
    } else {
        body.className = 'inline-view';
        if (inlineBtn) inlineBtn.classList.add('active');
        if (stackedHint) stackedHint.style.display = 'none';
        if (stackedHeaderHint) stackedHeaderHint.style.display = 'none';
        if (stackedTrailerHint) stackedTrailerHint.style.display = 'none';
    }

    // Save preference to localStorage
    localStorage.setItem('comparisonView', mode);

    // Reset diff navigation when switching views
    if (typeof currentDiffIndex !== 'undefined') {
        currentDiffIndex = -1;
    }
    document.querySelectorAll('.highlighted').forEach(r => r.classList.remove('highlighted'));

    console.log(`🔄 Switched to ${mode} view`);
}

