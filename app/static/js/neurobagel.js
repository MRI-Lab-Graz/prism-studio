// NeuroBagel helper for participants suggestions
async function fetchNeurobagelParticipants() {
  try {
    const resp = await fetch('/api/neurobagel/participants');
    if (!resp.ok) throw new Error('Network response not ok');
    const json = await resp.json();
    // Return augmented data with hierarchical structure
    return json.augmented || json.data;
  } catch (err) {
    console.warn('NeuroBagel fetch failed, using fallback suggestions:', err);
    // Provide sensible fallback suggestions with hierarchical structure when network is unavailable
    return {
      properties: {
        participant_id: {
          description: "A participant ID",
          data_type: "text",
          standardized_variable: "participant_id"
        },
        age: {
          description: "Age of participant in years",
          data_type: "continuous",
          unit: "years",
          standardized_variable: "age"
        },
        sex: {
          description: "Biological sex of participant",
          data_type: "categorical",
          standardized_variable: "biological_sex",
          levels: {
            "M": {
              label: "Male",
              description: "Male biological sex",
              uri: "http://purl.obolibrary.org/obo/PATO_0000384"
            },
            "F": {
              label: "Female",
              description: "Female biological sex",
              uri: "http://purl.obolibrary.org/obo/PATO_0000383"
            },
            "O": {
              label: "Other",
              description: "Other biological sex",
              uri: "http://purl.obolibrary.org/obo/PATO_0000385"
            }
          }
        },
        group: {
          description: "Participant group (e.g., control, patient)",
          data_type: "categorical",
          standardized_variable: "participant_group"
        }
      }
    };
  }
}

// Populate a suggestions dropdown for participants (attaches to window)
window.populateParticipantsSuggestions = async function populateParticipantsSuggestions(selectEl) {
  const data = await fetchNeurobagelParticipants();
  if (!data) {
    // Fallback: add a placeholder
    selectEl.innerHTML = '<option>No suggestions available</option>';
    return;
  }
  // Extract properties and build options with additional metadata
  const fields = Object.keys((data && data.properties) || {});
  selectEl.innerHTML = '';
  if (fields.length === 0) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'No fields found';
    selectEl.appendChild(opt);
    return;
  }
  fields.forEach(f => {
    const opt = document.createElement('option');
    opt.value = f;
    const colData = data.properties[f];
    const dataType = colData.data_type || 'unknown';
    // Show field name with data type hint
    opt.textContent = `${f} (${dataType})`;
    // Store metadata on the option element
    opt.dataset.columnMetadata = JSON.stringify(colData);
    selectEl.appendChild(opt);
  });
  // cache the raw NeuroBagel data on window for reuse
  window.__neurobagel_participants = data;
};

// Apply a NeuroBagel suggestion into matching fields in the participants form
window.applyNeurobagelSuggestion = async function applyNeurobagelSuggestion(fieldKey) {
  if (!fieldKey) {
    return;
  }
  let data = window.__neurobagel_participants;
  if (!data) {
    data = await fetchNeurobagelParticipants();
    if (!data) {
      console.warn('No NeuroBagel data available to apply suggestion');
      return;
    }
    window.__neurobagel_participants = data;
  }

  const fieldDef = (data.properties || {})[fieldKey];
  if (!fieldDef) {
    console.warn('Selected field not found in NeuroBagel data:', fieldKey);
    return;
  }

  // Build suggestion based on hierarchical data type
  let suggestion = '';
  const dataType = fieldDef.data_type;
  
  if (dataType === 'categorical' && fieldDef.levels) {
    // For categorical: show all levels with descriptions
    const levelsList = Object.entries(fieldDef.levels)
      .map(([k, v]) => {
        const label = v.label || k;
        const uri = v.uri ? ` (${v.uri})` : '';
        return `${k}: ${label}${uri}`;
      })
      .join('\n');
    suggestion = `Categorical levels:\n${levelsList}`;
  } else if (dataType === 'continuous' && fieldDef.unit) {
    // For continuous: show unit + description
    suggestion = `${fieldDef.description} (Unit: ${fieldDef.unit})`;
  } else if (fieldDef.description) {
    suggestion = fieldDef.description;
  } else {
    suggestion = JSON.stringify(fieldDef, null, 2);
  }

  // Find all textareas in the participants form that have a data-json-path starting with the fieldKey
  const selector = `[data-json-path^="${fieldKey}"]`;
  const matches = Array.from(document.querySelectorAll(selector));
  if (matches.length === 0) {
    // If no direct matches, try matching any path that contains the fieldKey
    const fallback = Array.from(document.querySelectorAll('[data-json-path]')).filter(el => el.dataset.jsonPath.includes(fieldKey));
    if (fallback.length === 0) {
      console.warn('No form fields found for NeuroBagel key:', fieldKey);
      return;
    }
    fallback.forEach(el => { el.value = suggestion; });
    // Notify user
    if (typeof showAlert === 'function') showAlert(`Inserted NeuroBagel suggestion for ${fieldKey} (${dataType})`, 'success');
    return;
  }

  matches.forEach(el => {
    el.value = suggestion;
  });

  if (typeof showAlert === 'function') showAlert(`Inserted NeuroBagel suggestion for ${fieldKey} (${dataType})`, 'success');
};
