/**
 * PRISM Studio Main Entry Point
 * Initializes all module aggregators and sets up global references
 */

// Import all module aggregators
import * as ProjectsModule from './modules/projects/index.js';
import * as ConverterModule from './modules/converter/index.js';
import * as SurveyModule from './modules/survey/index.js';
import * as ToolsModule from './modules/tools/index.js';

// Make modules available globally for page scripts
// This maintains compatibility while providing modular structure
window.ProjectsModule = ProjectsModule;
window.ConverterModule = ConverterModule;
window.SurveyModule = SurveyModule;
window.ToolsModule = ToolsModule;

console.log('PRISM Studio modules initialized');
console.log('Available modules: ProjectsModule, ConverterModule, SurveyModule, ToolsModule');
