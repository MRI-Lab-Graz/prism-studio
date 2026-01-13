/**
 * API Client for BIDS JSON Editor
 * Handles all communication with Flask backend
 */

class BIDSAPIClient {
  constructor(baseUrl = "http://localhost:5000") {
    this.baseUrl = baseUrl;
  }

  /**
   * Get schema for a JSON type
   * @param {string} jsonType - 'dataset_description', 'participants', etc.
   * @returns {Promise<Object>} Schema object
   */
  async getSchema(jsonType) {
    const response = await fetch(`${this.baseUrl}/api/schema/${jsonType}`);
    const result = await response.json();
    if (!result.success) {
      throw new Error(result.error || "Failed to load schema");
    }
    return result.schema;
  }

  /**
   * Load a BIDS JSON file
   * @param {string} jsonType - 'dataset_description', 'participants', etc.
   * @returns {Promise<Object>} JSON data
   */
  async loadFile(jsonType) {
    const response = await fetch(`${this.baseUrl}/api/file/${jsonType}`);
    const result = await response.json();
    if (!result.success) {
      throw new Error(result.error || "Failed to load file");
    }
    return result.data;
  }

  /**
   * Save a BIDS JSON file
   * @param {string} jsonType - 'dataset_description', 'participants', etc.
   * @param {Object} data - JSON data to save
   * @returns {Promise<Object>} Result
   */
  async saveFile(jsonType, data) {
    const response = await fetch(`${this.baseUrl}/api/file/${jsonType}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });
    const result = await response.json();
    if (!result.success) {
      throw new Error(result.error || "Failed to save file");
    }
    return result;
  }

  /**
   * Validate JSON against schema
   * @param {string} jsonType - 'dataset_description', 'participants', etc.
   * @param {Object} data - JSON data to validate
   * @returns {Promise<Object>} Validation result with errors
   */
  async validateJSON(jsonType, data) {
    const response = await fetch(`${this.baseUrl}/api/validate/${jsonType}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });
    const result = await response.json();
    if (!result.success) {
      throw new Error(result.error || "Validation failed");
    }
    return result;
  }

  /**
   * List available files in BIDS folder
   * @returns {Promise<Array>} List of available files
   */
  async listFiles() {
    const response = await fetch(`${this.baseUrl}/api/files`);
    const result = await response.json();
    if (!result.success) {
      throw new Error(result.error || "Failed to list files");
    }
    return result.files;
  }

  /**
   * Get current BIDS folder path
   * @returns {Promise<string>} BIDS folder path
   */
  async getBIDSFolder() {
    const response = await fetch(`${this.baseUrl}/api/bids-folder`);
    const result = await response.json();
    if (!result.success) {
      throw new Error(result.error || "Failed to get BIDS folder");
    }
    return result.folder;
  }

  /**
   * Set BIDS folder path
   * @param {string} folder - Path to BIDS folder
   * @returns {Promise<Object>} Result
   */
  async setBIDSFolder(folder) {
    const response = await fetch(`${this.baseUrl}/api/bids-folder`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ folder }),
    });
    const result = await response.json();
    if (!result.success) {
      throw new Error(result.error || "Failed to set BIDS folder");
    }
    return result;
  }
}

// Export for use
if (typeof module !== "undefined" && module.exports) {
  module.exports = BIDSAPIClient;
}
