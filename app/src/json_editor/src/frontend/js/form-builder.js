/**
 * BIDS JSON Form Generator
 * Dynamically generates HTML forms from BIDS schema definitions
 */

class BIDSFormGenerator {
  /**
   * Create a form from schema definition
   * @param {Object} schema - Schema object for the JSON type
   * @param {Object} data - Existing data to populate form (optional)
   * @returns {HTMLElement} Form div containing all fields
   */
  static generateForm(schema, data = {}) {
    const form = document.createElement("div");
    form.className = "bids-form";

    if (!schema || !schema.properties) {
      form.innerHTML = "<p class='error'>No schema available for this file type</p>";
      return form;
    }

    const properties = schema.properties;
    const required = schema.required || [];

    // Sort fields: required first, then alphabetically
    const fieldNames = Object.keys(properties).sort((a, b) => {
      const aRequired = required.includes(a) ? 0 : 1;
      const bRequired = required.includes(b) ? 0 : 1;
      if (aRequired !== bRequired) return aRequired - bRequired;
      return a.localeCompare(b);
    });

    // Generate form sections
    fieldNames.forEach((fieldName) => {
      const fieldSchema = properties[fieldName];
      const isRequired = required.includes(fieldName);
      const value = data[fieldName] || "";

      const fieldElement = this._createField(
        fieldName,
        fieldSchema,
        isRequired,
        value
      );
      form.appendChild(fieldElement);
    });

    return form;
  }

  /**
   * Create a single form field
   * @private
   */
  static _createField(fieldName, fieldSchema, isRequired, value) {
    const container = document.createElement("div");
    container.className = "form-group";

    // Label
    const label = document.createElement("label");
    label.className = "form-label";
    label.textContent = fieldName;
    if (isRequired) {
      const required = document.createElement("span");
      required.className = "required";
      required.textContent = "*";
      label.appendChild(required);
    }
    container.appendChild(label);

    // Description
    if (fieldSchema.description) {
      const description = document.createElement("p");
      description.className = "form-description";
      description.textContent = fieldSchema.description;
      container.appendChild(description);
    }

    // Input field based on type
    let input;
    if (fieldSchema.enum) {
      input = this._createEnumField(fieldName, fieldSchema, value);
    } else if (fieldSchema.type === "boolean") {
      input = this._createBooleanField(fieldName, value);
    } else if (fieldSchema.type === "array") {
      input = this._createArrayField(fieldName, fieldSchema, value);
    } else if (fieldSchema.type === "integer" || fieldSchema.type === "number") {
      input = this._createNumberField(fieldName, fieldSchema, value);
    } else {
      input = this._createTextField(fieldName, fieldSchema, value);
    }

    input.id = fieldName;
    input.name = fieldName;
    input.required = isRequired;
    input.dataset.fieldName = fieldName;
    input.dataset.fieldType = fieldSchema.type || "string";

    container.appendChild(input);

    return container;
  }

  /**
   * Create text input field
   * @private
   */
  static _createTextField(fieldName, fieldSchema, value) {
    const input = document.createElement("input");
    input.type = "text";
    input.className = "form-control";
    input.placeholder = fieldSchema.description || fieldName;
    input.value = value || "";

    // Add pattern if specified
    if (fieldSchema.pattern) {
      input.pattern = fieldSchema.pattern;
    }

    return input;
  }

  /**
   * Create enum select field
   * @private
   */
  static _createEnumField(fieldName, fieldSchema, value) {
    const select = document.createElement("select");
    select.className = "form-control";

    // Add empty option
    const emptyOption = document.createElement("option");
    emptyOption.value = "";
    emptyOption.textContent = "-- Select --";
    select.appendChild(emptyOption);

    // Add enum options
    fieldSchema.enum.forEach((enumValue) => {
      const option = document.createElement("option");
      option.value = enumValue;
      option.textContent = enumValue;
      if (enumValue === value) {
        option.selected = true;
      }
      select.appendChild(option);
    });

    return select;
  }

  /**
   * Create boolean checkbox field
   * @private
   */
  static _createBooleanField(fieldName, value) {
    const input = document.createElement("input");
    input.type = "checkbox";
    input.className = "form-control-checkbox";
    input.checked = value === true || value === "true";

    return input;
  }

  /**
   * Create array field (textarea)
   * @private
   */
  static _createArrayField(fieldName, fieldSchema, value) {
    const textarea = document.createElement("textarea");
    textarea.className = "form-control";
    textarea.placeholder = "Enter comma-separated values or JSON array";
    textarea.rows = 4;

    if (Array.isArray(value)) {
      textarea.value = JSON.stringify(value, null, 2);
    } else if (value) {
      textarea.value = value;
    }

    return textarea;
  }

  /**
   * Create number input field
   * @private
   */
  static _createNumberField(fieldName, fieldSchema, value) {
    const input = document.createElement("input");
    input.type = fieldSchema.type === "integer" ? "number" : "text";
    input.className = "form-control";
    input.value = value || "";

    if (fieldSchema.minimum !== undefined) {
      input.min = fieldSchema.minimum;
    }
    if (fieldSchema.maximum !== undefined) {
      input.max = fieldSchema.maximum;
    }

    return input;
  }

  /**
   * Extract form data into JSON object
   * @param {HTMLElement} formElement - Form element
   * @returns {Object} JSON data from form
   */
  static getFormData(formElement) {
    const data = {};
    const fields = formElement.querySelectorAll("[data-field-name]");

    fields.forEach((field) => {
      const fieldName = field.dataset.fieldName;
      const fieldType = field.dataset.fieldType;

      let value;
      if (field.type === "checkbox") {
        value = field.checked;
      } else if (fieldType === "array") {
        // Try to parse as JSON array, otherwise split by comma
        const rawValue = field.value.trim();
        if (rawValue.startsWith("[")) {
          try {
            value = JSON.parse(rawValue);
          } catch (e) {
            value = rawValue.split(",").map((v) => v.trim());
          }
        } else if (rawValue) {
          value = rawValue.split(",").map((v) => v.trim());
        } else {
          value = [];
        }
      } else if (fieldType === "integer") {
        value = field.value ? parseInt(field.value) : null;
      } else if (fieldType === "number") {
        value = field.value ? parseFloat(field.value) : null;
      } else {
        value = field.value || null;
      }

      // Only include non-empty values
      if (value !== null && value !== "" && value !== false) {
        data[fieldName] = value;
      }
    });

    return data;
  }

  /**
   * Populate form from data
   * @param {HTMLElement} formElement - Form element
   * @param {Object} data - Data to populate
   */
  static setFormData(formElement, data) {
    if (!data) return;

    Object.entries(data).forEach(([fieldName, value]) => {
      const field = formElement.querySelector(`[name="${fieldName}"]`);
      if (!field) return;

      if (field.type === "checkbox") {
        field.checked = value === true;
      } else if (field.dataset.fieldType === "array") {
        if (Array.isArray(value)) {
          field.value = JSON.stringify(value, null, 2);
        } else {
          field.value = value;
        }
      } else {
        field.value = value || "";
      }
    });
  }
}

// Export for use
if (typeof module !== "undefined" && module.exports) {
  module.exports = BIDSFormGenerator;
}
