# Integration Profiles

Integration profiles are JSON files that overlay integration-specific context onto
standard HL7 field definitions. When working with a specific system, a profile tells
the viewer how that system uses each field — custom names, expected values, component
meanings, and implementation notes.

Profiles do not replace the HL7 spec definitions; they add to them. All tools in this
project support profiles: the web viewer, CLI, TUI, and MCP server.

## Schema reference

### Top-level

```json
{
  "name": "My Integration v2.5",
  "hl7Version": "2.5",
  "description": "Optional description of this integration",
  "segments": { }
}
```

| Field       | Type   | Required | Description                                                              |
|-------------|--------|----------|--------------------------------------------------------------------------|
| name        | string | yes      | Display name shown in toolbar/status bar when loaded                     |
| hl7Version  | string | no       | HL7 version hint: `"2.3"` or `"2.5"`. Auto-selects version when loaded  |
| description | string | no       | Free text description of the integration                                 |
| segments    | object | no       | Segment overrides keyed by segment name (MSH, PID, OBR, etc.)           |

### Segment definition

Each key under `segments` is a segment name. The value is an object:

| Field       | Type    | Description                                                                          |
|-------------|---------|--------------------------------------------------------------------------------------|
| description | string  | Segment-level description shown in detail panel                                      |
| custom      | boolean | Set `true` for Z-segments. Provides "Custom Segment" label and type info             |
| fields      | object  | Field overrides keyed by field number (as string: `"3"`, `"9"`, etc.)                |

### Field definition

Each key under `fields` is the HL7 field number as a string. The value is an object
with any combination of:

| Field      | Type    | Description                                                                        |
|------------|---------|------------------------------------------------------------------------------------|
| customName | string  | Replaces the standard HL7 field name. Shown with a "Custom" badge                  |
| description| string  | Shown in the detail panel under "Profile Description"                               |
| notes      | string  | Implementation notes shown in the detail panel under "Profile Notes"                |
| dt         | string  | Override data type (useful for Z-segment fields not in the spec)                    |
| required   | boolean | When `true`, validation flags this field if empty (red indicator)                   |
| valueMap   | object  | Maps coded values to descriptions. Current value highlighted in detail panel         |
| components | object  | Component-level descriptions keyed by component number (as string, 1-based)          |

### Component definition

Each key under `components` is the component position as a string (`"1"`, `"2"`, etc.):

| Field       | Type   | Description                           |
|-------------|--------|---------------------------------------|
| description | string | Component-level description           |

### Validation behavior

When a profile is loaded, the viewer and `hl7_validate` check two things:

- **Required fields** (`"required": true`): flagged if the field is empty in the message.
- **Value maps** (`"valueMap"`): flagged if the field's value doesn't match any key in the map.

Additionally, the viewer shows:

- **Missing segments**: segments defined in the profile but absent from the message.
- **Unexpected segments**: segments present in the message but not defined in the profile.

## Tutorial: building a profile from a sample message

This walkthrough builds a profile for the ORM^O01 order message in `samples/orm-o01-order-v23.hl7`.

### Step 1: start with the skeleton

Every profile starts the same way:

```json
{
  "name": "Central Hospital RIS/PACS v2.3",
  "hl7Version": "2.3",
  "description": "Radiology order interface between HIS and PACS",
  "segments": {}
}
```

### Step 2: identify fields worth documenting

Parse the message and look for fields that aren't self-explanatory. Standard fields
like PID-5 (Patient Name) or PID-7 (Date of Birth) rarely need profiles. Focus on:

- Fields with coded values (OBR-4 procedure codes, OBR-25 result status)
- Fields with integration-specific meaning (MSH-3 sending application)
- Custom Z-segments (ZDS)
- Fields that must be present for the integration to work

Looking at the ORM sample, the interesting fields are:

| Address | Raw value               | Why document it                                |
|---------|-------------------------|------------------------------------------------|
| MSH-3   | RADIS                   | Identifies the sending application              |
| PID-3   | PAT55210^^^CENTRAL_HOSP | MRN — required for patient matching             |
| OBR-4   | CR^Computed Radiography | Procedure code from local catalog               |
| OBR-25  | P                       | Single-letter status code, needs value map      |
| ZDS-1   | 1.2.840...^CARESTREAM   | Custom segment, no spec definition exists        |

### Step 3: add MSH — sending application

```json
"MSH": {
  "fields": {
    "3": {
      "customName": "Sending Application (RIS)",
      "description": "Identifies the RIS instance sending the message"
    }
  }
}
```

Only one field documented. No need to list every MSH field — the HL7 spec definitions
already cover the standard ones.

### Step 4: add PID — mark the MRN as required

```json
"PID": {
  "fields": {
    "3": {
      "customName": "Patient MRN",
      "required": true,
      "description": "Medical Record Number from HIS patient master index",
      "components": {
        "1": { "description": "MRN value" },
        "4": { "description": "Assigning authority — must match PACS config" },
        "5": { "description": "Always 'PI' (Patient Internal Identifier)" }
      }
    }
  }
}
```

The `required: true` means validation will flag this field if empty. Component
descriptions explain what each part of the composite CX value means in this context.

### Step 5: add OBR — procedure codes and status

```json
"OBR": {
  "description": "Procedure details for PACS",
  "fields": {
    "4": {
      "customName": "Procedure Code",
      "description": "PACS procedure code from RIS catalog",
      "valueMap": {
        "CR": "Computed Radiography",
        "US": "Ultrasound",
        "CT": "Computed Tomography",
        "MR": "Magnetic Resonance",
        "XR": "X-Ray"
      },
      "components": {
        "1": { "description": "Procedure code" },
        "2": { "description": "Procedure description text" },
        "3": { "description": "Coding system (usually 'L' for local)" }
      }
    },
    "25": {
      "customName": "Result Status",
      "valueMap": {
        "P": "Preliminary",
        "F": "Final",
        "C": "Corrected",
        "X": "Cancelled"
      }
    }
  }
}
```

The `valueMap` on OBR-4 documents the local procedure code table. The viewer matches
component 1 of the field value against the map keys and highlights the match.

### Step 6: add ZDS — custom Z-segment

Z-segments have no spec definition, so the profile is the only source of field names
and types:

```json
"ZDS": {
  "description": "DICOM Study reference (custom Z-segment)",
  "custom": true,
  "fields": {
    "1": {
      "customName": "Study Instance UID",
      "dt": "RP",
      "description": "DICOM Study Instance UID as a Reference Pointer"
    }
  }
}
```

Setting `"custom": true` tells the viewer this is a Z-segment. The `"dt": "RP"` provides
the data type that the spec can't supply.

### Result

The complete profile is about 50 lines of JSON. See `profiles/sample-profile.json` for
a fuller example covering more fields with notes and additional value maps.

## Tips

1. **Start from a real message.** Parse a sample in the viewer, note which fields the
   integration populates, and only document those.

2. **Use field numbers from the viewer.** The address column shows the exact field
   number to use as the key (e.g., `MSH-3` → key `"3"`).

3. **Focus on non-obvious fields.** Standard fields like PID-5 rarely need profiles.
   Document fields with integration-specific meaning: procedure codes, device
   references, local value sets.

4. **One profile per integration system.** The profile name appears in the toolbar when
   loaded.

5. **Component descriptions** are most useful when the integration requires specific
   subfield values (e.g., PID-3.4 Assigning Authority must be a specific string).

6. **Value maps don't need to be exhaustive.** Document the codes you actually encounter.
   Unknown codes aren't flagged as errors — only codes present in the map but not
   matching the field value trigger a warning.
