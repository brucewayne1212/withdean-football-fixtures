// JavaScript for Withdean Youth FC Fixture Manager

document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        if (alert.classList.contains('alert-success') || alert.classList.contains('alert-info')) {
            setTimeout(() => {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }, 5000);
        }
    });
    
    // Add loading states to form submissions
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn && !submitBtn.disabled) {
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
                submitBtn.disabled = true;
            }
        });
    });
    
    // Auto-refresh dashboard data every 30 seconds
    if (window.location.pathname === '/') {
        setInterval(refreshDashboardData, 30000);
    }
});

// Utility functions
function showToast(message, type = 'success') {
    const toastContainer = getOrCreateToastContainer();
    
    const toastElement = document.createElement('div');
    toastElement.className = `toast align-items-center text-white bg-${type} border-0`;
    toastElement.setAttribute('role', 'alert');
    toastElement.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toastElement);
    
    const toast = new bootstrap.Toast(toastElement);
    toast.show();
    
    // Clean up after toast is hidden
    toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
    });
}

function getOrCreateToastContainer() {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1050';
        document.body.appendChild(container);
    }
    return container;
}

function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

function refreshDashboardData() {
    fetch('/api/summary')
        .then(response => response.json())
        .then(data => {
            // Update summary cards
            updateSummaryCard('pending', data.pending);
            updateSummaryCard('waiting', data.waiting);
            updateSummaryCard('in_progress', data.in_progress);
            updateSummaryCard('completed', data.completed);
        })
        .catch(error => {
            console.error('Error refreshing dashboard data:', error);
        });
}

function updateSummaryCard(type, value) {
    const card = document.querySelector(`.card.bg-${getCardColor(type)} h2`);
    if (card && card.textContent !== value.toString()) {
        card.textContent = value;
        // Add a subtle flash effect
        card.parentElement.parentElement.style.transform = 'scale(1.05)';
        setTimeout(() => {
            card.parentElement.parentElement.style.transform = 'scale(1)';
        }, 200);
    }
}

function getCardColor(type) {
    const colors = {
        'pending': 'warning',
        'waiting': 'info',
        'in_progress': 'primary',
        'completed': 'success'
    };
    return colors[type] || 'secondary';
}

// Copy to clipboard functionality
function copyToClipboard(text, successMessage = 'Copied to clipboard!') {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            showToast(successMessage);
        }).catch(err => {
            // Fallback for older browsers
            fallbackCopyToClipboard(text, successMessage);
        });
    } else {
        fallbackCopyToClipboard(text, successMessage);
    }
}

function fallbackCopyToClipboard(text, successMessage) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        const successful = document.execCommand('copy');
        if (successful) {
            showToast(successMessage);
        } else {
            showToast('Failed to copy to clipboard', 'error');
        }
    } catch (err) {
        showToast('Copy to clipboard not supported', 'warning');
    }
    
    document.body.removeChild(textArea);
}

// Task management functions
function markTaskCompleted(taskId, notes = '') {
    return fetch(`/mark_completed/${taskId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ notes: notes })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Task marked as completed!');
            return true;
        } else {
            showToast('Error marking task as completed', 'danger');
            return false;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('Error marking task as completed', 'danger');
        return false;
    });
}

function markTaskInProgress(taskId) {
    return fetch(`/mark_in_progress/${taskId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Task marked as in progress!');
            return true;
        } else {
            showToast('Error marking task as in progress', 'danger');
            return false;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('Error marking task as in progress', 'danger');
        return false;
    });
}

// File upload enhancements
document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('file');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const fileSize = file.size / 1024 / 1024; // Convert to MB
                if (fileSize > 16) {
                    showToast('File size exceeds 16MB limit', 'danger');
                    e.target.value = '';
                    return;
                }
                
                const fileName = file.name;
                const allowedExtensions = ['csv', 'xlsx', 'xls'];
                const fileExtension = fileName.split('.').pop().toLowerCase();
                
                if (!allowedExtensions.includes(fileExtension)) {
                    showToast('Please select a CSV or Excel file', 'warning');
                    e.target.value = '';
                    return;
                }
                
                // Update label or add file info
                const label = document.querySelector('label[for="file"]');
                if (label) {
                    label.innerHTML = `Selected: ${fileName} <small class="text-muted">(${fileSize.toFixed(2)} MB)</small>`;
                }
            }
        });
    }
});

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + U for upload page
    if ((e.ctrlKey || e.metaKey) && e.key === 'u') {
        e.preventDefault();
        window.location.href = '/upload';
    }
    
    // Ctrl/Cmd + T for tasks page
    if ((e.ctrlKey || e.metaKey) && e.key === 't') {
        e.preventDefault();
        window.location.href = '/tasks';
    }
    
    // Ctrl/Cmd + H for home/dashboard
    if ((e.ctrlKey || e.metaKey) && e.key === 'h') {
        e.preventDefault();
        window.location.href = '/';
    }
});

// Add keyboard shortcut hints to footer
document.addEventListener('DOMContentLoaded', function() {
    const footer = document.querySelector('footer p');
    if (footer && window.innerWidth > 768) {
        footer.innerHTML += ' | <small class="text-muted">Shortcuts: Ctrl+H (Home), Ctrl+T (Tasks), Ctrl+U (Upload)</small>';
    }
});