/**
 * BIDS JSON Editor - Main Application
 * Coordinates form generation, API calls, and UI updates
 */

class BIDSJSONEditor {
  constructor() {
    this.api = new BIDSAPIClient();
    this.currentFileType = null;
    this.currentData = {};
    this.schema = {};

    this.init();
  }

  async init() {
    this._setupEventListeners();
    await this._loadFileList();
  }

  _setupEventListeners() {
    // File selector change
    const fileSelector = document.getElementById("fileSelector");
    if (fileSelector) {
      fileSelector.addEventListener("change", (e) =>
        this._onFileSelected(e.target.value)
      );
    }

    // Load button
    const loadBtn = document.getElementById("loadBtn");
    if (loadBtn) {
      loadBtn.addEventListener("click", () => this._loadFile());
    }

    // Save button
    const saveBtn = document.getElementById("saveBtn");
    if (saveBtn) {
      saveBtn.addEventListener("click", () => this._saveFile());
    }

    // Validate button
    const validateBtn = document.getElementById("validateBtn");
    if (validateBtn) {
      validateBtn.addEventListener("click", () => this._validateFile());
    }

    // BIDS folder input
    const folderInput = document.getElementById("bidsFolderInput");
    if (folderInput) {
      folderInput.addEventListener("change", (e) =>
        this._setBIDSFolder(e.target.value)
      );
    }

    // New file button
    const newFileBtn = document.getElementById("newFileBtn");
    if (newFileBtn) {
      newFileBtn.addEventListener("click", () => this._createNewFile());
    }
  }

  async _loadFileList() {
    try {
      const fileList = await this.api.listFiles();

      const fileSelector = document.getElementById("fileSelector");
      if (!fileSelector) return;

      fileSelector.innerHTML = '<option value="">-- Select File --</option>';

      fileList.forEach((file) => {
        const option = document.createElement("option");
        option.value = file.type;
        option.textContent = `${file.filename}${file.exists ? "" : " (new)"}${file.type.includes("required") ? " (required)" : ""}`;
        fileSelector.appendChild(option);
      });

      // Display folder info
      const folderInfo = document.getElementById("folderInfo");
      if (folderInfo) {
        const folder = await this.api.getBIDSFolder();
        folderInfo.textContent = `BIDS Folder: ${folder}`;
      }
    } catch (error) {
      this._showError(`Failed to load file list: ${error.message}`);
    }
  }

  async _onFileSelected(fileType) {
    if (!fileType) {
      this._clearForm();
      return;
    }

    this.currentFileType = fileType;

    try {
      // Load schema
      this.schema = await this.api.getSchema(fileType);

      // Generate form based on file type
      const formContainer = document.getElementById("formContainer");
      if (formContainer) {
        let form;

        if (fileType === "participants") {
          // Display participants.json content directly as JSON
          form = this._generateJSONDisplay();
        } else if (fileType.startsWith("task-")) {
          // Task files
          form = BIDSFormGenerator.generateForm(this.schema);
        } else {
          // Default form generation
          form = BIDSFormGenerator.generateForm(this.schema);
        }

        formContainer.textContent = "";
        formContainer.appendChild(form);
      }

      // Check if file exists and pre-load
      try {
        this.currentData = await this.api.loadFile(fileType);
        const form = document.querySelector(".bids-form");
        if (form && this.currentData) {
          if (fileType === "participants") {
            this._populateJSONDisplay(form, this.currentData);
          } else {
            BIDSFormGenerator.setFormData(form, this.currentData);
          }
        }
        this._showSuccess(`Loaded existing ${fileType}`);
      } catch (e) {
        // File doesn't exist yet, that's OK
        this._showInfo(`Creating new ${fileType}`);
      }
    } catch (error) {
      this._showError(`Failed to load schema: ${error.message}`);
    }
  }

  async _loadFile() {
    if (!this.currentFileType) {
      this._showError("Please select a file type first");
      return;
    }

    try {
      this.currentData = await this.api.loadFile(this.currentFileType);
      const form = document.querySelector(".bids-form");
      if (form) {
        BIDSFormGenerator.setFormData(form, this.currentData);
      }
      this._showSuccess(`Loaded ${this.currentFileType}`);
    } catch (error) {
      this._showError(`Failed to load file: ${error.message}`);
    }
  }

  async _saveFile() {
    if (!this.currentFileType) {
      this._showError("Please select a file type first");
      return;
    }

    try {
      const form = document.querySelector(".bids-form");
      if (!form) {
        this._showError("Form not loaded");
        return;
      }

      let data;
      if (this.currentFileType === "participants") {
        data = this._getJSONDisplayData(form);
      } else {
        data = BIDSFormGenerator.getFormData(form);
      }

      // Validate before saving
      const validation = await this.api.validateJSON(this.currentFileType, data);
      if (!validation.valid) {
        this._showError(
          `Validation failed:\n${validation.errors.join("\n")}`
        );
        return;
      }

      // Save
      await this.api.saveFile(this.currentFileType, data);
      this.currentData = data;
      this._showSuccess(`Saved ${this.currentFileType} successfully`);
    } catch (error) {
      this._showError(`Failed to save file: ${error.message}`);
    }
  }

  async _validateFile() {
    if (!this.currentFileType) {
      this._showError("Please select a file type first");
      return;
    }

    try {
      const form = document.querySelector(".bids-form");
      if (!form) {
        this._showError("Form not loaded");
        return;
      }

      let data;
      if (this.currentFileType === "participants") {
        data = this._getParticipantsFormData(form);
      } else {
        data = BIDSFormGenerator.getFormData(form);
      }

      const validation = await this.api.validateJSON(this.currentFileType, data);

      if (validation.valid) {
        this._showSuccess("✓ Valid JSON! Ready to save.");
      } else {
        this._showError(
          `Validation errors:\n${validation.errors.join("\n")}`
        );
      }
    } catch (error) {
      this._showError(`Validation failed: ${error.message}`);
    }
  }

  async _setBIDSFolder(folderPath) {
    if (!folderPath) return;

    try {
      await this.api.setBIDSFolder(folderPath);
      this._showSuccess(`BIDS folder set to ${folderPath}`);
      await this._loadFileList();
    } catch (error) {
      this._showError(`Failed to set BIDS folder: ${error.message}`);
    }
  }

  _createNewFile() {
    this._clearForm();
    const fileSelector = document.getElementById("fileSelector");
    if (fileSelector) {
      fileSelector.value = "";
    }
    this.currentFileType = null;
    this.currentData = {};
    this._showInfo("Ready to create new file. Select a file type from the dropdown.");
  }

  _clearForm() {
    const formContainer = document.getElementById("formContainer");
    if (formContainer) {
      formContainer.innerHTML = "<p class='info'>Select a file type to begin</p>";
    }
  }

  /**
   * Generate a special form for participants.json (columns format)
   */
  _generateParticipantsForm() {
    const form = document.createElement("div");
    form.className = "bids-form participants-form";

    // Add header
    const header = document.createElement("h3");
    header.textContent = "Participants Column Definitions";
    form.appendChild(header);

    // Add info
    const info = document.createElement("p");
    info.className = "form-description";
    info.textContent =
      "Define the columns that appear in participants.tsv. Each row below represents one column.";
    form.appendChild(info);

    // Add button to add new column
    const addBtn = document.createElement("button");
    addBtn.className = "btn-add-column";
    addBtn.textContent = "+ Add Column";
    addBtn.onclick = () => this._addParticipantColumn(form);
    form.appendChild(addBtn);

    // Container for columns
    const columnsContainer = document.createElement("div");
    columnsContainer.id = "participantsColumnsContainer";
    form.appendChild(columnsContainer);

    return form;
  }

  /**
   * Populate participants form with existing data
   */
  _populateParticipantsForm(form, data) {
    const container = form.querySelector("#participantsColumnsContainer");
    if (!container) return;

    container.textContent = ""; // Clear

    Object.entries(data).forEach(([columnName, columnDef]) => {
      this._addParticipantColumnWithData(form, columnName, columnDef);
    });
  }

  /**
   * Add a new participant column to the form
   */
  _addParticipantColumn(form) {
    this._addParticipantColumnWithData(form, "", {});
  }

  /**
   * Add a participant column with data
   */
  _addParticipantColumnWithData(form, columnName = "", columnDef = {}) {
    const container = form.querySelector("#participantsColumnsContainer");
    if (!container) return;

    const columnDiv = document.createElement("div");
    columnDiv.className = "participant-column-group";
    columnDiv.style.cssText =
      "border: 1px solid #ddd; padding: 12px; margin-bottom: 12px; border-radius: 4px;";

    // Column name
    const nameGroup = document.createElement("div");
    nameGroup.className = "form-group";
    const nameLabel = document.createElement("label");
    nameLabel.textContent = "Column Name";
    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.className = "form-control";
    nameInput.value = columnName;
    nameInput.placeholder = "e.g., age, sex, group";
    nameInput.dataset.type = "columnName";
    nameGroup.appendChild(nameLabel);
    nameGroup.appendChild(nameInput);
    columnDiv.appendChild(nameGroup);

    // Description
    const descGroup = document.createElement("div");
    descGroup.className = "form-group";
    const descLabel = document.createElement("label");
    descLabel.textContent = "Description";
    const descInput = document.createElement("textarea");
    descInput.className = "form-control";
    descInput.value = columnDef.Description || "";
    descInput.placeholder = "Description of this column";
    descInput.rows = 3;
    descInput.dataset.type = "Description";
    descGroup.appendChild(descLabel);
    descGroup.appendChild(descInput);
    columnDiv.appendChild(descGroup);

    // Units (optional)
    const unitsGroup = document.createElement("div");
    unitsGroup.className = "form-group";
    const unitsLabel = document.createElement("label");
    unitsLabel.textContent = "Units (optional)";
    const unitsInput = document.createElement("input");
    unitsInput.type = "text";
    unitsInput.className = "form-control";
    unitsInput.value = columnDef.Units || "";
    unitsInput.placeholder = "e.g., year, meter, kg";
    unitsInput.dataset.type = "Units";
    unitsGroup.appendChild(unitsLabel);
    unitsGroup.appendChild(unitsInput);
    columnDiv.appendChild(unitsGroup);

    // Remove button
    const removeBtn = document.createElement("button");
    removeBtn.textContent = "✕ Remove";
    removeBtn.style.cssText =
      "background-color: #d9534f; color: white; padding: 8px 12px; border: none; border-radius: 4px; cursor: pointer; margin-top: 8px;";
    removeBtn.onclick = () => columnDiv.remove();
    columnDiv.appendChild(removeBtn);

    container.appendChild(columnDiv);
  }

  /**
   * Get participants form data
   */
  _getParticipantsFormData(form) {
    const data = {};
    const columns = form.querySelectorAll(".participant-column-group");

    columns.forEach((columnDiv) => {
      const nameInput = columnDiv.querySelector('input[data-type="columnName"]');
      const columnName = nameInput.value.trim();

      if (!columnName) return; // Skip empty columns

      const columnDef = {};

      const descInput = columnDiv.querySelector('textarea[data-type="Description"]');
      if (descInput && descInput.value.trim()) {
        columnDef.Description = descInput.value.trim();
      }

      const unitsInput = columnDiv.querySelector('input[data-type="Units"]');
      if (unitsInput && unitsInput.value.trim()) {
        columnDef.Units = unitsInput.value.trim();
      }

      data[columnName] = columnDef;
    });

    return data;
  }

  /**
   * Generate a simple JSON display for participants.json
   */
  _generateJSONDisplay() {
    const form = document.createElement("div");
    form.className = "bids-form json-display-form";

    // Add header
    const header = document.createElement("h3");
    header.textContent = "JSON Content";
    form.appendChild(header);

    // Add info
    const info = document.createElement("p");
    info.className = "form-description";
    info.textContent = "Edit the JSON content directly. The content will be validated as JSON when saved.";
    form.appendChild(info);

    // JSON textarea
    const textarea = document.createElement("textarea");
    textarea.id = "jsonContent";
    textarea.className = "form-control json-textarea";
    textarea.placeholder = "Enter JSON content here...";
    textarea.rows = 20;
    textarea.style.cssText = "width: 100%; font-family: 'Courier New', monospace; font-size: 12px;";
    form.appendChild(textarea);

    return form;
  }

  /**
   * Populate JSON display with existing data
   */
  _populateJSONDisplay(form, data) {
    const textarea = form.querySelector("#jsonContent");
    if (textarea && data) {
      textarea.value = JSON.stringify(data, null, 2);
    }
  }

  /**
   * Get data from JSON display textarea
   */
  _getJSONDisplayData(form) {
    const textarea = form.querySelector("#jsonContent");
    if (!textarea) {
      throw new Error("JSON textarea not found");
    }

    const content = textarea.value.trim();
    if (!content) {
      return {};
    }

    try {
      return JSON.parse(content);
    } catch (error) {
      throw new Error(`Invalid JSON: ${error.message}`);
    }
  }

  // ==================== UI Helpers ====================

  _showError(message) {
    this._showMessage(message, "error");
  }

  _showSuccess(message) {
    this._showMessage(message, "success");
  }

  _showInfo(message) {
    this._showMessage(message, "info");
  }

  _showMessage(message, type) {
    const alertContainer = document.getElementById("alertContainer");
    if (!alertContainer) return;

    const alert = document.createElement("div");
    alert.className = `alert alert-${type}`;
    alert.textContent = message;

    alertContainer.appendChild(alert);

    // Auto-remove after 5 seconds
    setTimeout(() => alert.remove(), 5000);
  }
}

// Initialize when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  window.editor = new BIDSJSONEditor();
});
