export function getParticipantsMergeSummaryView({
    canApply,
    existingOnlyCount,
    newParticipantCount,
    mergeQuality,
    sessionResolutionRequired,
    conflictCount,
}) {
    if (Boolean(canApply)) {
        const existingCount = Number(existingOnlyCount || 0);
        let summaryText = existingCount > 0
            ? `This merge can be applied safely. ${existingCount} existing participant${existingCount === 1 ? '' : 's'} will stay unchanged.`
            : 'This merge can be applied safely. All overlapping non-empty values agree.';

        const safeMergeQuality = (mergeQuality && typeof mergeQuality === 'object')
            ? mergeQuality
            : {};
        const incomingTotalCells = Number(safeMergeQuality.incoming_new_participant_total_value_cells || 0);
        const incomingMissingCells = Number(safeMergeQuality.incoming_new_participant_missing_value_cells || 0);
        const incomingAllMissingRows = Number(safeMergeQuality.incoming_new_participants_all_missing_values || 0);
        if (Number(newParticipantCount || 0) > 0 && incomingTotalCells > 0 && incomingMissingCells > 0) {
            const missingPercent = Math.round((incomingMissingCells / incomingTotalCells) * 100);
            const allMissingNote = incomingAllMissingRows > 0
                ? ` ${incomingAllMissingRows} new participant row${incomingAllMissingRows === 1 ? ' is' : 's are'} fully empty in the imported file.`
                : '';
            summaryText += ` Imported values for new participants are sparse (${incomingMissingCells}/${incomingTotalCells} missing cells, ${missingPercent}%).${allMissingNote}`;
        }

        return {
            alertToneClass: 'alert-success',
            titleText: 'Merge Preview Ready',
            summaryText,
        };
    }

    if (Boolean(sessionResolutionRequired) && Number(conflictCount || 0) === 0) {
        return {
            alertToneClass: 'alert-warning',
            titleText: 'Merge Preview Blocked',
            summaryText: 'This merge is blocked until session resolution is chosen for columns that vary across repeated participant rows.',
        };
    }

    return {
        alertToneClass: 'alert-warning',
        titleText: 'Merge Preview Blocked',
        summaryText: 'This merge is blocked because conflicting non-empty values were found. Existing participants.tsv remains authoritative until conflicts are resolved.',
    };
}

export function getParticipantsMergeBadgeTexts({
    matchedCount,
    newParticipantCount,
    fillCount,
    conflictCount,
}) {
    const safeMatchedCount = Number(matchedCount || 0);
    const safeNewParticipantCount = Number(newParticipantCount || 0);
    const safeFillCount = Number(fillCount || 0);
    const safeConflictCount = Number(conflictCount || 0);

    return {
        matchedText: `${safeMatchedCount} matched`,
        newParticipantsText: `${safeNewParticipantCount} new participant${safeNewParticipantCount === 1 ? '' : 's'}`,
        fillText: `${safeFillCount} filled value${safeFillCount === 1 ? '' : 's'}`,
        conflictText: `${safeConflictCount} conflict${safeConflictCount === 1 ? '' : 's'}`,
    };
}

export function getParticipantsMergeHarmonizationStatusView({
    harmonizationState,
    isRefreshPending,
    conflictCount,
}) {
    const safeState = (harmonizationState && typeof harmonizationState === 'object')
        ? harmonizationState
        : {};

    if (safeState.hasInvalidKeepBoth) {
        return {
            toneClass: 'text-danger',
            text: 'Fix Keep both column names before applying merge.',
        };
    }

    if (isRefreshPending) {
        return {
            toneClass: 'text-muted',
            text: 'Refreshing merge preview with updated harmonization settings...',
        };
    }

    if (Number(conflictCount || 0) > 0) {
        return {
            toneClass: 'text-warning',
            text: 'Harmonization can resolve equivalent coding only. Remaining conflicts must be fixed in source data.',
        };
    }

    return {
        toneClass: 'text-success',
        text: 'Merge is conflict-free. Confirm harmonization choices, then apply merge.',
    };
}

export function getParticipantsMergeConvertHintText({
    hasInvalidKeepBoth,
    sessionResolutionRequired,
    conflictCount,
    canConvert,
}) {
    if (Boolean(hasInvalidKeepBoth)) {
        return 'Fix Keep both column names before applying merge';
    }

    if (Boolean(sessionResolutionRequired) && Number(conflictCount || 0) === 0) {
        return 'Choose session resolution before applying merge';
    }

    return Boolean(canConvert)
        ? 'Ready to apply conflict-free merge'
        : 'Resolve merge conflicts first';
}

export function getParticipantsMergeConflictActionsView({
    conflictCount,
}) {
    const hasConflicts = Number(conflictCount || 0) > 0;
    return {
        showActions: hasConflicts,
        isDownloadEnabled: hasConflicts,
    };
}

export function getParticipantsMergeNewColumnsView({
    newColumns,
}) {
    const safeColumns = Array.isArray(newColumns)
        ? newColumns.map((column) => String(column || '').trim()).filter(Boolean)
        : [];

    if (safeColumns.length === 0) {
        return {
            isVisible: false,
            text: '',
        };
    }

    return {
        isVisible: true,
        text: `New columns from the import: ${safeColumns.join(', ')}`,
    };
}

export function getParticipantsMergeConflictListView({
    conflicts,
    buildConflictListHtml,
}) {
    const safeConflicts = Array.isArray(conflicts) ? conflicts : [];
    if (safeConflicts.length === 0) {
        return {
            isVisible: false,
            html: '',
        };
    }

    const renderConflictList = typeof buildConflictListHtml === 'function'
        ? buildConflictListHtml
        : (() => '');

    return {
        isVisible: true,
        html: String(renderConflictList(safeConflicts) || ''),
    };
}

export function getParticipantsMergeConvertButtonView({
    canConvert,
}) {
    const isEnabled = Boolean(canConvert);
    return {
        isEnabled,
        toneClass: isEnabled ? 'btn-success' : 'btn-outline-secondary',
    };
}

export function getParticipantsMergeHarmonizationFieldView({
    action,
    errorText,
    targetName,
}) {
    const normalizedAction = String(action || '').trim();
    if (normalizedAction !== 'keep_both') {
        return {
            isInvalid: false,
            feedbackText: '',
            hintText: 'No extra column will be created for this field.',
        };
    }

    const normalizedErrorText = String(errorText || '').trim();
    if (normalizedErrorText) {
        return {
            isInvalid: true,
            feedbackText: normalizedErrorText,
            hintText: '',
        };
    }

    const normalizedTargetName = String(targetName || '').trim();
    return {
        isInvalid: false,
        feedbackText: '',
        hintText: normalizedTargetName
            ? `Incoming coding will be written to ${normalizedTargetName}.`
            : 'Enter the new incoming-coded column name.',
    };
}
