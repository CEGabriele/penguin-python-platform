function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + "=")) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

class FeedbackManager {
    constructor(projectId, isTeacher = false) {
        this.projectId = projectId;
        this.isTeacher = isTeacher;
        this.feedback = { overall: null, line_comments: [] };
        this.currentFile = null;
    }

    async loadFeedback() {
        try {
            const response = await fetch(`/dashboard/project/${this.projectId}/feedback/`);
            const data = await response.json();

            if (data.ok) {
                this.feedback = data;
                return data;
            } else {
                console.error('Failed to load feedback:', data.error);
                return null;
            }
        } catch (error) {
            console.error('Error loading feedback:', error);
            return null;
        }
    }

    async saveOverallComment(comment) {
        if (!this.isTeacher) {
            console.error('Only teachers can save feedback');
            return null;
        }

        try {
            const response = await fetch(`/dashboard/project/${this.projectId}/feedback/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify({ comment })
            });

            const data = await response.json();
            if (data.ok) {
                this.feedback.overall = data.feedback;
                return data.feedback;
            } else {
                console.error('Failed to save feedback:', data.error);
                return null;
            }
        } catch (error) {
            console.error('Error saving feedback:', error);
            return null;
        }
    }

    async saveLineComment(filePath, lineNumber, comment, endLine = null) {
        if (!this.isTeacher) {
            console.error('Only teachers can save line comments');
            return null;
        }

        const startLine = Math.min(lineNumber, endLine ?? lineNumber);
        const lastLine = Math.max(lineNumber, endLine ?? lineNumber);

        try {
            const response = await fetch(`/dashboard/project/${this.projectId}/line-comment/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify({ file_path: filePath, line_number: startLine, end_line: lastLine, comment })
            });

            const data = await response.json();
            if (data.ok) {
                // Update local feedback
                const existing = this.feedback.line_comments.find(
                    lc => lc.file_path === filePath && lc.line_number === startLine
                );
                if (existing) {
                    Object.assign(existing, data.line_comment);
                } else {
                    this.feedback.line_comments.push(data.line_comment);
                }
                return data.line_comment;
            } else {
                console.error('Failed to save line comment:', data.error);
                return null;
            }
        } catch (error) {
            console.error('Error saving line comment:', error);
            return null;
        }
    }

    async deleteLineComment(commentId) {
        if (!this.isTeacher) {
            console.error('Only teachers can delete line comments');
            return false;
        }

        try {
            const response = await fetch(`/dashboard/project/${this.projectId}/line-comment/${commentId}/`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                }
            });

            const data = await response.json();
            if (data.ok) {
                this.feedback.line_comments = this.feedback.line_comments.filter(lc => lc.id !== commentId);
                return true;
            } else {
                console.error('Failed to delete line comment:', data.error);
                return false;
            }
        } catch (error) {
            console.error('Error deleting line comment:', error);
            return false;
        }
    }

    getLineCommentsForFile(filePath) {
        return this.feedback.line_comments.filter(lc => lc.file_path === filePath);
    }

    // Returns the comment covering lineNumber, whether it's a single line or a range.
    getLineCommentForLine(filePath, lineNumber) {
        return this.feedback.line_comments.find(lc => {
            if (lc.file_path !== filePath) return false;
            const end = lc.end_line || lc.line_number;
            return lineNumber >= lc.line_number && lineNumber <= end;
        });
    }
}

// Helper to add line numbers and comment UI to code display
function renderCodeWithFeedback(codeText, filePath, feedbackManager) {
    const lines = codeText.split('\n');
    let html = '<table class="code-viewer-table"><tbody>';

    lines.forEach((line, index) => {
        const lineNumber = index + 1;
        const lineComment = feedbackManager.getLineCommentForLine(filePath, lineNumber);
        const isCommentedRange = !!lineComment;
        // Only render the comment box once, on the last line of its range.
        const showCommentBox = lineComment && lineNumber === (lineComment.end_line || lineComment.line_number);

        html += `<tr class="code-line${isCommentedRange ? ' commented-line' : ''}" data-line="${lineNumber}">`;
        html += `<td class="line-number" data-line="${lineNumber}">${lineNumber}</td>`;
        html += '<td class="code-cell">';
        html += `<pre class="code-line-content">${escapeHtml(line)}</pre>`;

        if (showCommentBox) {
            const rangeLabel = lineComment.end_line && lineComment.end_line !== lineComment.line_number
                ? `Lines ${lineComment.line_number}-${lineComment.end_line}`
                : `Line ${lineComment.line_number}`;
            html += '<div class="line-comment-display">';
            html += `<div class="line-comment-range">${rangeLabel}</div>`;
            html += `<strong>${escapeHtml(lineComment.grader_name)}:</strong> ${escapeHtml(lineComment.comment)}`;
            if (feedbackManager.isTeacher) {
                html += `<button class="edit-comment-btn" data-id="${lineComment.id}">Edit</button>`;
                html += `<button class="delete-comment-btn" data-id="${lineComment.id}">Delete</button>`;
            }
            html += '</div>';
        }

        html += '</td></tr>';
    });

    html += '</tbody></table>';
    return html;
}

// Attaches click / shift-click gutter selection to the line-number cells of a
// rendered code table so a teacher can select one or more contiguous lines
// before adding a comment. Calls onRangeSelected(startLine, endLine) once a
// selection is made (a plain click selects a single line).
function attachLineSelection(container, onRangeSelected) {
    let selectionStart = null;

    container.querySelectorAll('td.line-number').forEach(cell => {
        cell.classList.add('selectable');

        // Without this, shift+click triggers the browser's native text-selection
        // (a dark overlay spanning both clicks) instead of just our range logic.
        cell.addEventListener('mousedown', (e) => e.preventDefault());

        cell.onclick = (e) => {
            const lineNumber = parseInt(cell.dataset.line, 10);

            if (e.shiftKey && selectionStart !== null) {
                highlightSelection(container, selectionStart, lineNumber);
                onRangeSelected(Math.min(selectionStart, lineNumber), Math.max(selectionStart, lineNumber));
            } else {
                selectionStart = lineNumber;
                highlightSelection(container, lineNumber, lineNumber);
                onRangeSelected(lineNumber, lineNumber);
            }
        };
    });
}

function highlightSelection(container, startLine, endLine) {
    const lo = Math.min(startLine, endLine);
    const hi = Math.max(startLine, endLine);

    container.querySelectorAll('tr.code-line').forEach(row => {
        const lineNumber = parseInt(row.dataset.line, 10);
        row.classList.toggle('selected-line', lineNumber >= lo && lineNumber <= hi);
    });
}

function clearLineSelection(container) {
    container.querySelectorAll('tr.selected-line').forEach(row => row.classList.remove('selected-line'));
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}
