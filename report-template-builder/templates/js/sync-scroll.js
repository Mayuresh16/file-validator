/**
 * Synchronized Scrolling Module
 * Handles synchronized scrolling between dual panes
 */

// Data Comparison Panes
let isSyncingSource = false;
let isSyncingTarget = false;

// Header Panes
let isSyncingHeaderSource = false;
let isSyncingHeaderTarget = false;

// Trailer Panes
let isSyncingTrailerSource = false;
let isSyncingTrailerTarget = false;

/**
 * Initialize synchronized scrolling for all dual pane sections
 */
function initSyncScrolling() {
    // Data Comparison Dual Panes
    const sourceScroll = document.getElementById('sourceScroll');
    const targetScroll = document.getElementById('targetScroll');

    if (sourceScroll && targetScroll) {
        sourceScroll.addEventListener('scroll', function() {
            if (!isSyncingSource) {
                isSyncingTarget = true;
                targetScroll.scrollTop = this.scrollTop;
                targetScroll.scrollLeft = this.scrollLeft;
            }
            isSyncingSource = false;
        });

        targetScroll.addEventListener('scroll', function() {
            if (!isSyncingTarget) {
                isSyncingSource = true;
                sourceScroll.scrollTop = this.scrollTop;
                sourceScroll.scrollLeft = this.scrollLeft;
            }
            isSyncingTarget = false;
        });
    }

    // Header Dual Panes
    const headerSourceScroll = document.getElementById('headerSourceScroll');
    const headerTargetScroll = document.getElementById('headerTargetScroll');

    if (headerSourceScroll && headerTargetScroll) {
        headerSourceScroll.addEventListener('scroll', function() {
            if (!isSyncingHeaderSource) {
                isSyncingHeaderTarget = true;
                headerTargetScroll.scrollTop = this.scrollTop;
                headerTargetScroll.scrollLeft = this.scrollLeft;
            }
            isSyncingHeaderSource = false;
        });

        headerTargetScroll.addEventListener('scroll', function() {
            if (!isSyncingHeaderTarget) {
                isSyncingHeaderSource = true;
                headerSourceScroll.scrollTop = this.scrollTop;
                headerSourceScroll.scrollLeft = this.scrollLeft;
            }
            isSyncingHeaderTarget = false;
        });
    }

    // Trailer Dual Panes
    const trailerSourceScroll = document.getElementById('trailerSourceScroll');
    const trailerTargetScroll = document.getElementById('trailerTargetScroll');

    if (trailerSourceScroll && trailerTargetScroll) {
        trailerSourceScroll.addEventListener('scroll', function() {
            if (!isSyncingTrailerSource) {
                isSyncingTrailerTarget = true;
                trailerTargetScroll.scrollTop = this.scrollTop;
                trailerTargetScroll.scrollLeft = this.scrollLeft;
            }
            isSyncingTrailerSource = false;
        });

        trailerTargetScroll.addEventListener('scroll', function() {
            if (!isSyncingTrailerTarget) {
                isSyncingTrailerSource = true;
                trailerSourceScroll.scrollTop = this.scrollTop;
                trailerSourceScroll.scrollLeft = this.scrollLeft;
            }
            isSyncingTrailerTarget = false;
        });
    }

    console.log('🔄 Synchronized scrolling initialized');
}

/**
 * Apply sticky headers to scrollable containers
 */
function applyStickyHeaders() {
    const sideHeader = document.getElementById('side-by-side-header');
    const stackedHeader = document.getElementById('stacked-header');

    if (sideHeader) {
        sideHeader.style.position = 'sticky';
        sideHeader.style.top = '0';
        sideHeader.style.zIndex = '10';
        sideHeader.style.backgroundColor = '#fff';
    }

    if (stackedHeader) {
        stackedHeader.style.position = 'sticky';
        stackedHeader.style.top = '0';
        stackedHeader.style.zIndex = '10';
        stackedHeader.style.backgroundColor = '#fff';
    }

    // Apply to all headers in scrollable containers
    const headers = document.querySelectorAll('.scrollable-table-container thead th, .pane-content table thead th');
    headers.forEach(header => {
        header.style.position = 'sticky';
        header.style.top = '0';
        header.style.zIndex = '10';
        header.style.backgroundColor = '#34495e';
        header.style.color = 'white';
        header.style.boxShadow = '0 2px 5px rgba(0, 0, 0, 0.1)';
    });
}


