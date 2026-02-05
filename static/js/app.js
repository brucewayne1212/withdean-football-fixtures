// JavaScript for Withdean Youth FC Fixture Manager

document.addEventListener('DOMContentLoaded', function () {
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
        form.addEventListener('submit', function () {
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
document.addEventListener('DOMContentLoaded', function () {
    const fileInput = document.getElementById('file');
    if (fileInput) {
        fileInput.addEventListener('change', function (e) {
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
document.addEventListener('keydown', function (e) {
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

// Away Email Response Generator Functions
function generateAwayEmail(taskId, teamName) {
    console.log(`[generateAwayEmail] Triggered for Task: ${taskId}, Team: ${teamName}`);

    // Show the modal - it should be defined in the main template
    const modalElement = document.getElementById('awayEmailModal');
    if (!modalElement) {
        console.error('[generateAwayEmail] awayEmailModal not found in DOM');
        alert('Internal Error: awayEmailModal not found. Please refresh the page.');
        return;
    }

    // Use getOrCreateInstance for robustness
    let modal = bootstrap.Modal.getOrCreateInstance(modalElement);
    console.log('[generateAwayEmail] Showing modal...');
    modal.show();

    // Set team name in modal title
    const modalTeamName = document.getElementById('modalTeamName');
    if (modalTeamName) modalTeamName.textContent = teamName;

    // Show loading state
    const loadingSection = document.getElementById('loadingSection');
    const contentSection = document.getElementById('contentSection');
    const errorSection = document.getElementById('errorSection');

    if (loadingSection) loadingSection.style.display = 'block';
    if (contentSection) contentSection.style.display = 'none';
    if (errorSection) errorSection.style.display = 'none';

    // Store task ID for completion marking
    const copyBtn = document.getElementById('copyAndCompleteBtn');
    if (copyBtn) {
        copyBtn.dataset.taskId = taskId;
        copyBtn.disabled = false; // Reset button state
        copyBtn.innerHTML = '<i class="fas fa-copy"></i> Copy & Mark Task Complete';
    }

    // Get CSRF token from meta tag
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
    if (!csrfToken) {
        console.warn('[generateAwayEmail] CSRF token not found in meta tag');
    }

    // Generate the email response
    fetch('/api/generate-away-match-response', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            team_name: teamName
        })
    })
        .then(response => response.json())
        .then(data => {
            if (loadingSection) loadingSection.style.display = 'none';

            if (data.success) {
                const responseText = document.getElementById('awayResponseText');
                if (responseText) responseText.textContent = data.response_text;
                if (contentSection) contentSection.style.display = 'block';
            } else {
                const errorMessage = document.getElementById('errorMessage');
                if (errorMessage) errorMessage.textContent = data.message || 'Unknown error';
                if (errorSection) errorSection.style.display = 'block';
            }
        })
        .catch(error => {
            console.error('Error generating away email:', error);
            if (loadingSection) loadingSection.style.display = 'none';
            const errorMessage = document.getElementById('errorMessage');
            if (errorMessage) errorMessage.textContent = 'Network error: ' + error.message;
            if (errorSection) errorSection.style.display = 'block';
        });
}

// Copy response text and mark task complete
function copyAwayResponseAndMarkComplete() {
    const responseTextElement = document.getElementById('awayResponseText');
    const responseText = responseTextElement ? responseTextElement.textContent.trim() : '';
    const copyBtn = document.getElementById('copyAndCompleteBtn');
    const taskId = copyBtn ? copyBtn.dataset.taskId : null;

    if (!responseText) {
        alert('No response text to copy!');
        return;
    }

    if (!taskId) {
        alert('Task ID missing!');
        return;
    }

    // Copy to clipboard first
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(responseText).then(() => {
            handleCopySuccess(copyBtn, taskId);
        }).catch(err => {
            console.error('Failed to copy: ', err);
            fallbackCopyAwayResponse(responseText, copyBtn, taskId);
        });
    } else {
        fallbackCopyAwayResponse(responseText, copyBtn, taskId);
    }
}

function handleCopySuccess(copyBtn, taskId) {
    // Show copy success briefly
    const originalHTML = copyBtn.innerHTML;
    copyBtn.innerHTML = '<i class="fas fa-check"></i> Copied - Marking Complete...';
    copyBtn.disabled = true;

    // Get CSRF token
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

    // Mark task as completed
    fetch(`/mark_completed/${taskId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            notes: 'Away email response generated and sent to opposition'
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                copyBtn.innerHTML = '<i class="fas fa-check-double"></i> Done!';
                showToast('Response copied and task marked complete!');

                // Close modal after a delay
                setTimeout(() => {
                    const modalElement = document.getElementById('awayEmailModal');
                    const modal = bootstrap.Modal.getInstance(modalElement);
                    if (modal) {
                        console.log('[handleCopySuccess] Hiding awayEmailModal');
                        modal.hide();
                    }
                    // Reload page to update task status
                    location.reload();
                }, 1000);
            } else {
                copyBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Copied but failed to complete task';
                alert('Response copied but failed to mark task as complete: ' + (data.error || 'Unknown error'));
                copyBtn.disabled = false;
                copyBtn.innerHTML = originalHTML;
            }
        })
        .catch(error => {
            console.error('Error marking task complete:', error);
            alert('Response copied but network error marking task as complete.');
            copyBtn.disabled = false;
            copyBtn.innerHTML = originalHTML;
        });
}

function fallbackCopyAwayResponse(text, copyBtn, taskId) {
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
            handleCopySuccess(copyBtn, taskId);
        } else {
            alert('Failed to copy to clipboard.');
        }
    } catch (err) {
        alert('Failed to copy to clipboard.');
    }

    document.body.removeChild(textArea);
}

// Add keyboard shortcut hints to footer
document.addEventListener('DOMContentLoaded', function () {
    const footer = document.querySelector('footer p');
    if (footer && window.innerWidth > 768) {
        footer.innerHTML += ' | <small class="text-muted">Shortcuts: Ctrl+H (Home), Ctrl+T (Tasks), Ctrl+U (Upload)</small>';
    }
});

// Function to update task status via form submission (handles redirects)
function updateTaskStatus(taskId, status) {
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/update_task_status';

    const taskIdInput = document.createElement('input');
    taskIdInput.type = 'hidden';
    taskIdInput.name = 'task_id';
    taskIdInput.value = taskId;
    form.appendChild(taskIdInput);

    const statusInput = document.createElement('input');
    statusInput.type = 'hidden';
    statusInput.name = 'status';
    statusInput.value = status;
    form.appendChild(statusInput);

    // Add CSRF token if available
    const csrfToken = document.querySelector('meta[name="csrf-token"]');
    if (csrfToken) {
        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrf_token';
        csrfInput.value = csrfToken.content;
        form.appendChild(csrfInput);
    }

    document.body.appendChild(form);
    form.submit();
}