/**
 * PRISM Studio Main Entry Point
 * Initializes all module aggregators and sets up global references
 */

// Import all module aggregators
import * as ProjectsModule from './modules/projects/index.js?v=20260515-4';
import * as ConverterModule from './modules/converter/index.js';
import * as SurveyModule from './modules/survey/index.js';
import * as ToolsModule from './modules/tools/index.js';

// Make modules available globally for page scripts
// This maintains compatibility while providing modular structure
window.ProjectsModule = ProjectsModule;
window.ConverterModule = ConverterModule;
window.SurveyModule = SurveyModule;
window.ToolsModule = ToolsModule;

// Initialize the Projects page from a single modular entrypoint.
if (document.getElementById('projectsRoot')) {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => ProjectsModule.initializeProjectsPage());
    } else {
        ProjectsModule.initializeProjectsPage();
    }
}

// Initialize the Share & Archive page (export, DataLad server, rsync).
if (document.getElementById('shareRoot')) {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => ProjectsModule.initializeSharePage());
    } else {
        ProjectsModule.initializeSharePage();
    }
}
