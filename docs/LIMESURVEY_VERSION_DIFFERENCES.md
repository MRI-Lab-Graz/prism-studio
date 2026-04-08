# LimeSurvey Version Differences (.lss XML Format)

This document describes the structural differences in the `.lss` XML export format between LimeSurvey versions, relevant for PRISM Studio's export compatibility.

## DBVersion Mapping

| LimeSurvey Version | DBVersion | Notes |
|-------------------|-----------|-------|
| 3.x | 350 | Legacy, inline localization |
| 4.x | ~400 | Transitional |
| 5.x | 415 | Separate l10n tables introduced |
| 6.x | 636+ | CDATA wrapping, `<fields>` declarations, `aid` required |

## Key Structural Differences

### 1. `<fields>` Declarations (LS 6.x only)

LS 6.x (DBVersion 636+) exports include `<fields>` elements before `<rows>` that declare the expected column names:

```xml
<!-- LS 6.x -->
<answers>
  <fields>
    <fieldname>aid</fieldname>
    <fieldname>qid</fieldname>
    <fieldname>code</fieldname>
    <fieldname>sortorder</fieldname>
    <fieldname>assessment_value</fieldname>
    <fieldname>scale_id</fieldname>
  </fields>
  <rows>...</rows>
</answers>
```

LS 3.x/5.x do NOT have `<fields>` declarations.

**Impact**: The import helper reads these to determine column structure. Missing `<fields>` may cause import issues in LS 6.x.

### 2. CDATA Wrapping (LS 6.x only)

LS 6.x wraps all field values in `<![CDATA[...]]>`:

```xml
<!-- LS 6.x -->
<row>
  <aid><![CDATA[1708]]></aid>
  <qid><![CDATA[1683]]></qid>
  <code><![CDATA[1]]></code>
</row>

<!-- LS 3.x / 5.x / PRISM current -->
<row>
  <qid>101</qid>
  <code>0</code>
</row>
```

**Impact**: CDATA is optional for import (XML parsers handle both), but LS 6.x exports always use it.

### 3. Answer Localization (`answers` vs `answer_l10ns`)

This is the **critical difference** that causes missing answer labels in LS 6.x imports.

#### LS 3.x (DBVersion 350): Inline Localization

Answer text is stored directly in the `answers` table, one row per language:

```xml
<answers>
  <rows>
    <row>
      <qid>803813</qid>
      <code>1</code>
      <sortorder>1</sortorder>
      <assessment_value>0</assessment_value>
      <language>de</language>
      <scale_id>0</scale_id>
      <answer>Kein Abschluss</answer>    <!-- TEXT HERE -->
    </row>
  </rows>
</answers>
<!-- No answer_l10ns section -->
```

#### LS 6.x (DBVersion 636): Separate Localization Table

Answer text is in a separate `answer_l10ns` table, linked by `aid`:

```xml
<answers>
  <fields>
    <fieldname>aid</fieldname>    <!-- REQUIRED -->
    <fieldname>qid</fieldname>
    <fieldname>code</fieldname>
    <fieldname>sortorder</fieldname>
    <fieldname>assessment_value</fieldname>
    <fieldname>scale_id</fieldname>
  </fields>
  <rows>
    <row>
      <aid>1708</aid>              <!-- UNIQUE ANSWER ID -->
      <qid>1683</qid>
      <code>1</code>
      <sortorder>0</sortorder>
      <assessment_value>0</assessment_value>
      <scale_id>0</scale_id>
      <!-- NO answer text, NO language -->
    </row>
  </rows>
</answers>

<answer_l10ns>
  <fields>
    <fieldname>id</fieldname>
    <fieldname>aid</fieldname>    <!-- LINKS TO answers.aid -->
    <fieldname>answer</fieldname>
    <fieldname>language</fieldname>
  </fields>
  <rows>
    <row>
      <id>1646</id>
      <aid>1708</aid>              <!-- MATCHES answers.aid above -->
      <answer>Right-handed</answer>
      <language>de</language>
    </row>
  </rows>
</answer_l10ns>
```

#### PRISM Current Export (BROKEN for LS 6.x)

PRISM currently exports DBVersion 415 with `answer_l10ns` but uses **wrong fields**:

```xml
<answers>
  <rows>
    <row>
      <qid>101</qid>              <!-- NO aid field! -->
      <code>0</code>
      <sortorder>1</sortorder>
      <assessment_value>0</assessment_value>
      <scale_id>0</scale_id>
    </row>
  </rows>
</answers>

<answer_l10ns>
  <rows>
    <row>
      <id>7</id>
      <qid>101</qid>              <!-- WRONG: should be aid, not qid -->
      <code>0</code>              <!-- WRONG: not expected -->
      <answer>Rarely/Never</answer>
      <language>en</language>
      <sid>123456</sid>            <!-- WRONG: not expected -->
    </row>
  </rows>
</answer_l10ns>
```

**Problems:**
1. `answers` rows are missing `aid` field
2. `answer_l10ns` uses `qid` + `code` instead of `aid` to link
3. `answer_l10ns` has extra fields (`code`, `sid`) that are not expected
4. No `<fields>` declarations
5. No CDATA wrapping (minor)

### 4. Question Localization (`question_l10ns`)

#### LS 6.x Expected Fields
```
id, qid, question, help, script, language
```

#### PRISM Current Export
```
id, qid, question, help, language [, sid]
```

**Difference**: LS 6.x expects `script` field (for JavaScript). PRISM doesn't include it but this is likely not critical (defaults to NULL on import).

### 5. Group Localization (`group_l10ns`)

#### LS 6.x Expected Fields
```
id, gid, group_name, description, language, sid, group_order, randomization_group, grelevance
```

PRISM includes `id, gid, group_name, description, language, sid` which is a subset. The missing fields (`group_order`, `randomization_group`, `grelevance`) may cause issues.

### 6. Survey Settings

LS 6.x has significantly more survey settings fields (60+) including:
- `gsid` (global survey ID)
- `ipanonymize`
- `access_mode`
- `tokenencryptionoptions`
- Various email/bounce settings

PRISM only generates a minimal subset. Missing fields should default on import.

## Fix Required for PRISM Exporter

### Priority 1: Answer Localization (Critical)

The answer labels are completely missing in LS 6.x because:

1. **Add `aid` to `answers` rows**: Each answer needs a unique `aid` that links to `answer_l10ns`
2. **Use `aid` in `answer_l10ns`**: Replace `qid` + `code` with `aid` reference
3. **Remove extra fields from `answer_l10ns`**: Remove `code`, `sid` (not in LS 6.x schema)
4. **Add `<fields>` declarations**: Optional but recommended for LS 6.x compatibility

### Priority 2: CDATA Wrapping (Recommended)

Wrap all field values in CDATA for LS 6.x compatibility. Low risk, improves import reliability.

### Priority 3: DBVersion Update

Consider using DBVersion 636 instead of 415 when targeting LS 6.x to match the expected schema.
