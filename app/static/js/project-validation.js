// Real-time validation for required project fields
function validateProjectField(fieldId) {
    const field = document.getElementById(fieldId);
    if (!field) return;
    
    const isValid = field.value.trim() !== '';
    
    let isPatternValid = true;

    // For projectName, also validate pattern
    if (fieldId === 'projectName' && isValid) {
        isPatternValid = /^[a-zA-Z0-9_-]+$/.test(field.value.trim());
        if (!isPatternValid) {
            field.classList.remove('required-field-filled');
            field.classList.add('required-field-empty');
        }
    }
    
    if (isValid && isPatternValid) {
        field.classList.remove('required-field-empty');
        field.classList.add('required-field-filled');
    } else {
        field.classList.remove('required-field-filled');
        field.classList.add('required-field-empty');
    }

    const label = document.querySelector(`label[for="${fieldId}"]`);
    const badge = label ? label.querySelector('.badge') : null;
    if (badge) {
        if (isValid && isPatternValid) {
            badge.classList.remove('bg-danger');
            badge.classList.add('bg-success');
        } else {
            badge.classList.remove('bg-success');
            badge.classList.add('bg-danger');
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Add event listeners for real-time validation
    const projectNameField = document.getElementById('projectName');
    const projectPathField = document.getElementById('projectPath');
    
    if (projectNameField) {
        projectNameField.addEventListener('input', function() {
            validateProjectField('projectName');
        });
        projectNameField.addEventListener('blur', function() {
            validateProjectField('projectName');
        });
        validateProjectField('projectName');
    }
    
    if (projectPathField) {
        projectPathField.addEventListener('input', function() {
            validateProjectField('projectPath');
        });
        projectPathField.addEventListener('blur', function() {
            validateProjectField('projectPath');
        });
        validateProjectField('projectPath');
    }
    
    // Update validation after browse button click
    const browseProjectPathBtn = document.getElementById('browseProjectPath');
    if (browseProjectPathBtn) {
        browseProjectPathBtn.addEventListener('click', function() {
            setTimeout(() => {
                validateProjectField('projectPath');
            }, 100);
        });
    }
});
