:orphan:

# Pavlovia Converter Implementation Plan

## Decision: Use PRISM JSON as Source ✅

### Rationale

1. **Platform Independence**: PRISM JSON is already normalized and platform-agnostic
2. **Complete Metadata**: Includes Position, Levels, Items, Conditions - all valuable for Pavlovia
3. **Architecture Consistency**: Follows existing bidirectional converter pattern (LimeSurvey ↔ PRISM)
4. **Future Extensibility**: Other platforms (Qualtrics, REDCap) can also convert via PRISM

### Alternative Considered (Not Recommended)

❌ **Using LimeSurvey as Intermediate**: Would require:
- Extra conversion step (LimeSurvey → PRISM → Pavlovia)
- Loss of PRISM-specific metadata
- Dependency on LimeSurvey-specific structures
- Duplication of conversion logic

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PRISM Survey JSON                        │
│  (Platform-agnostic, validated, normalized)                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         src/converters/pavlovia.py                          │
│  • Parse PRISM JSON                                         │
│  • Map question types to PsychoPy components                │
│  • Generate .psyexp XML                                     │
│  • Create conditions spreadsheet                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│             PsychoPy/Pavlovia Output                        │
│  • task-name.psyexp (XML experiment definition)             │
│  • conditions.csv (question parameters)                     │
│  • README.md (usage instructions)                           │
└─────────────────────────────────────────────────────────────┘
```

## Question Type Mapping

### PRISM → PsychoPy Component Types

| PRISM Structure | PsychoPy Component | Implementation Priority |
|----------------|-------------------|------------------------|
| Single question + Levels (3-10 options) | Slider with labels | ⭐ High |
| Single question + Levels (many options) | Form (radio) | ⭐ High |
| Free text (no Levels) | Textbox | ⭐ High |
| Array with Items | Loop + conditions.csv | 🔶 Medium |
| Question with Condition | Code component + if-statement | 🔶 Medium |
| Multiple questions in Group | Separate routines | ⭐ High |
| Mandatory flag | Validation in code | 🔵 Low |

### Example Mappings

#### 1. Likert Scale → Slider Component

**PRISM:**
```json
{
  "BDI01": {
    "Description": "Sadness",
    "Levels": {
      "0": "Not at all",
      "1": "A little",
      "2": "Moderately",
      "3": "Extremely"
    }
  }
}
```

**PsychoPy:**
- Component: Slider
- Labels: ["0: Not at all", "1: A little", "2: Moderately", "3: Extremely"]
- Ticks: [0, 1, 2, 3]
- Style: Radio buttons

#### 2. Array Question → Loop

**PRISM:**
```json
{
  "STAI": {
    "Description": "State Anxiety Inventory",
    "Items": {
      "01": {"Description": "I feel calm", "Order": 1},
      "02": {"Description": "I feel secure", "Order": 2},
      "03": {"Description": "I feel tense", "Order": 3}
    },
    "Levels": {
      "1": "Not at all",
      "2": "Somewhat",
      "3": "Moderately",
      "4": "Very much"
    }
  }
}
```

**PsychoPy:**
- Component: Loop
- Conditions file:
  ```text
  question_text,level_1,level_2,level_3,level_4
  I feel calm,Not at all,Somewhat,Moderately,Very much
  I feel secure,Not at all,Somewhat,Moderately,Very much
  I feel tense,Not at all,Somewhat,Moderately,Very much
  ```
- Inside loop: Slider with `$question_text` and `[$level_1, $level_2, ...]`

#### 3. Conditional Question → Code Component

**PRISM:**
```json
{
  "PHQ9_10": {
    "Description": "If you checked any problems, how difficult...",
    "Condition": "PHQ9_01 + PHQ9_02 + PHQ9_03 > 0"
  }
}
```

**PsychoPy:**
- Code Component (Begin Routine):
  ```python
  # Skip this question if no previous problems reported
  if (PHQ9_01.response + PHQ9_02.response + PHQ9_03.response) == 0:
      continueRoutine = False
  ```

## Implementation Phases

### Phase 1: Minimal Viable Product (MVP) ✅

**Status**: Basic structure created in `src/converters/pavlovia.py`

Features:
- [x] Parse PRISM JSON
- [x] Extract questions, filter metadata
- [x] Generate basic .psyexp XML structure
- [x] Create welcome/thanks routines
- [x] Group questions by Position.Group
- [x] Generate README with instructions

**Testing**:
- Export simple questionnaire (e.g., BDI with 21 Likert items)
- Open in PsychoPy Builder
- Verify structure is valid

### Phase 2: Component Refinement 🚧

**Next Steps**:

1. **Implement Slider Components** (most common)
   - Detect numeric Levels (1-5, 0-3, etc.)
   - Create slider with labeled ticks
   - Add styling (radio vs continuous)

2. **Implement Form Components**
   - For questions with many options (>10)
   - Handle text responses
   - Add validation for mandatory questions

3. **Implement Textbox Components**
   - Detect free-text questions
   - Set height based on QuestionType (Short/Long)

4. **Test Suite**
   - Create test JSON files covering all question types
   - Automated export and validation

### Phase 3: Advanced Features 🔜

1. **Loop Implementation**
   - Generate conditions.csv correctly
   - Create loop structure in Flow
   - Handle nested Items

2. **Conditional Logic**
   - Parse PRISM Condition field
   - Generate Python code for `continueRoutine` control
   - Handle simple expressions (>, <, ==, !=)

3. **Randomization**
   - Detect RandomizeGroup in Position
   - Set loop randomization
   - Implement counterbalancing

4. **Styling & Appearance**
   - Extract colors/fonts from PRISM metadata
   - Apply consistent theme
   - Handle RTL languages

### Phase 4: Data Round-Trip 🔮

1. **Import from Pavlovia**
   - Parse Pavlovia CSV format
   - Map columns back to PRISM question codes
   - Convert to PRISM TSV + JSON
   - Preserve reaction times in separate events file

2. **Validation**
   - Ensure exported → collected → imported data matches original structure
   - Handle missing data appropriately

## File Structure

```
src/converters/
├── pavlovia.py          # Main converter (created ✅)
├── pavlovia_utils.py    # Helper functions (planned)
└── pavlovia_templates/  # XML templates (planned)
  ├── slider.xml
  ├── form.xml
  └── textbox.xml

docs/
└── PAVLOVIA_EXPORT.md   # User documentation (created ✅)

tests/
└── test_pavlovia.py     # Unit tests (planned)
```

## Technical Considerations

### PsychoPy .psyexp Structure

The `.psyexp` file is XML with this hierarchy:

```xml
<PsychoPy2experiment version="2024.1.1">
  <Settings>
    <Param name="Window size (pixels)" val="[1920, 1080]"/>
    <!-- ... -->
  </Settings>
  
  <Routines>
    <Routine name="welcome">
      <TextComponent name="welcome_text">
        <Param name="text" val="Welcome!"/>
        <!-- ... -->
      </TextComponent>
    </Routine>
    
    <Routine name="question_1">
      <SliderComponent name="BDI01">
        <Param name="labels" val="['Not at all', 'A little', ...]"/>
        <!-- ... -->
      </SliderComponent>
    </Routine>
  </Routines>
  
  <Flow>
    <Routine name="welcome"/>
    <Routine name="question_1"/>
    <Routine name="thanks"/>
  </Flow>
</PsychoPy2experiment>
```

### Component Parameter Reference

**Slider Component** (most common):
- `name`: Variable name (e.g., "BDI01")
- `labels`: List of text labels
- `ticks`: List of numeric values
- `size`: Width and height
- `style`: "rating", "radio", "slider", "labels45", "whiteOnBlack"
- `storeRating`: True
- `storeRatingTime`: True (for RT)

**Form Component** (multiple questions on one screen):
- `items`: List of form item dicts
- `randomize`: False
- `size`: [width, height]

**Textbox Component**:
- `text`: Default text
- `editable`: True
- `multiline`: True/False
- `letterHeight`: 0.03

### Known Limitations

1. **Complex Conditions**: 
   - PRISM: `"(Q1=1 OR Q2=2) AND Q3>5"`
   - PsychoPy: Would require complex code component
   - **Solution**: Warn user, create placeholder, require manual edit

2. **Piping** (inserting previous answers):
   - PRISM doesn't store this info
   - PsychoPy supports via `$variableName`
   - **Solution**: Document as manual customization

3. **Dual-Scale Arrays**:
   - PRISM Items can have `ScaleId: 0` and `ScaleId: 1`
   - PsychoPy doesn't have native dual-scale component
   - **Solution**: Create as two separate loops

4. **Media Embeddings**:
   - PRISM Items can have `MediaUrls`
   - PsychoPy can display images via ImageComponent
   - **Solution**: Phase 3 enhancement

## Integration with Existing Tools

### Update Web Interface

`prism-studio.py` should offer Pavlovia export:

```python
@app.route('/export/pavlovia/<session_id>')
def export_pavlovia(session_id):
    """Export validated dataset to Pavlovia format."""
    # Get survey JSON files from session
    # Call pavlovia.export_to_pavlovia()
    # Return ZIP with .psyexp + conditions.csv + README
```

### Update CLI

`prism.py` should support export flag:

```bash
python prism.py /path/to/dataset --export-pavlovia
```

### Schema Update

Consider adding to `survey.schema.json`:

```json
{
  "Technical": {
    "ExportFormats": {
      "type": "array",
      "items": {"enum": ["LimeSurvey", "Pavlovia", "Qualtrics"]},
      "description": "Supported export formats for this questionnaire"
    }
  }
}
```

## Testing Strategy

### Test Cases

1. **Simple Likert Scale**
   - 10 questions, 5-point scale
   - Expected: 10 slider components in sequence

2. **Mixed Question Types**
   - Likert + free text + yes/no
   - Expected: Sliders + textboxes + radio buttons

3. **Array Questions**
   - STAI (20 items, 4-point scale)
   - Expected: Loop with conditions.csv

4. **Grouped Questions**
   - BDI (Group A: Mood, Group B: Physical)
   - Expected: 2 routines in flow

5. **Conditional Questions**
   - PHQ-9 with suicide follow-up
   - Expected: Code component with if-statement

### Validation Checklist

- [ ] .psyexp file opens in PsychoPy without errors
- [ ] All questions display correctly
- [ ] Response data saves with correct variable names
- [ ] conditions.csv loads correctly in loop
- [ ] Experiment runs without crashes
- [ ] Data format matches PRISM column names

## Timeline Estimate

- **Phase 1 (MVP)**: ✅ Complete (basic structure)
- **Phase 2 (Components)**: 2-3 days
  - Slider implementation: 4 hours
  - Form implementation: 4 hours
  - Textbox implementation: 2 hours
  - Testing: 4 hours
  
- **Phase 3 (Advanced)**: 1 week
  - Loops: 1 day
  - Conditionals: 2 days
  - Randomization: 1 day
  - Styling: 1 day
  - Testing: 2 days
  
- **Phase 4 (Round-trip)**: 3-4 days
  - Import parser: 2 days
  - Validation: 1-2 days

**Total**: ~2-3 weeks for full implementation

## Resources

### Documentation
- PsychoPy Builder Components: https://psychopy.org/builder/components.html
- Pavlovia Documentation: https://pavlovia.org/docs
- PsychoPy Forum: https://discourse.psychopy.org

### Example Experiments
- Pavlovia Demos: https://gitlab.pavlovia.org/demos
- BART Task: https://gitlab.pavlovia.org/demos/bart (referenced by user)

### Python Libraries
- `defusedxml`: XML parsing (already used in limesurvey.py)
- `pandas`: CSV generation (already imported)

## Questions for User

1. **Priority**: Is Pavlovia export high priority, or is this exploratory?
2. **Question Types**: Which question types are most critical? (Likert scales vs arrays vs conditionals)
3. **Integration**: Should this be in CLI only, or also in web interface?
4. **Data Round-Trip**: Is importing Pavlovia data back to PRISM needed immediately?

## Next Actions

1. ✅ Create basic converter structure
2. ✅ Write documentation (PAVLOVIA_EXPORT.md)
3. 🚧 Implement slider components (most common use case)
4. 🚧 Test with real PRISM survey JSON (e.g., from official/library/)
5. 🔜 Add to PRISM CLI and web interface
6. 🔜 Create unit tests
