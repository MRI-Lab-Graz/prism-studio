// Real-time validation for required project fields
function validateProjectField(fieldId) {
    const field = document.getElementById(fieldId);
    if (!field) return;
    
    const isValid = field.value.trim() !== '';
    
    // For projectName, also validate pattern
    if (fieldId === 'projectName' && isValid) {
        const isValidPattern = /^[a-zA-Z0-9_-]+$/.test(field.value.trim());
        if (!isValidPattern) {
            field.classList.remove('required-field-filled');
            field.classList.add('required-field-empty');
            return;
        }
    }
    
    if (isValid) {
        field.classList.remove('required-field-empty');
        field.classList.add('required-field-filled');
    } else {
        field.classList.remove('required-field-filled');
        field.classList.add('required-field-empty');
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
