// Auto-expand error sections if there are errors
document.addEventListener('DOMContentLoaded', function() {
    const errorCount = Number('{{ results.summary.total_errors if results.summary else (results.errors|length if results.errors else 0) }}');
    if (errorCount > 0) {
        // Keep invalid files section expanded by default (already has 'show' class)
    }
});
</script>
