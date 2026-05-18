export function createMetadataOrcidController({
    escapeHtml,
    extractOrcidId,
    fetchWithApiFallback,
    setButtonLoading,
    showToast,
    applyOrcidCandidateToAuthorRow,
}) {
    function normalizeNameForMatch(value) {
        return String(value || '')
            .trim()
            .toLowerCase()
            .replace(/[^a-z0-9\s]/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
    }

    async function chooseOrcidCandidate(candidates, firstName, lastName, currentOrcid = '') {
        if (!Array.isArray(candidates) || candidates.length === 0) return null;
        if (candidates.length === 1) return candidates[0];

        const currentOrcidId = extractOrcidId(currentOrcid);

        const targetFirst = normalizeNameForMatch(firstName);
        const targetLast = normalizeNameForMatch(lastName);
        const exactMatches = candidates.filter(candidate => {
            const candidateFirst = normalizeNameForMatch(candidate.given_names || '');
            const candidateLast = normalizeNameForMatch(candidate.family_name || '');
            return targetFirst && targetLast && candidateFirst === targetFirst && candidateLast === targetLast;
        });
        if (exactMatches.length === 1) {
            return exactMatches[0];
        }

        if (!(window.bootstrap && typeof window.bootstrap.Modal === 'function')) {
            const defaultIndex = Math.max(
                0,
                candidates.findIndex((candidate) => {
                    const candidateOrcid = candidate.orcid_id || candidate.orcid || '';
                    return currentOrcidId && extractOrcidId(candidateOrcid) === currentOrcidId;
                })
            );
            const options = candidates
                .map((candidate, index) => {
                    const displayName = String(candidate.display_name || '').trim() || `Candidate ${index + 1}`;
                    const orcidId = String(candidate.orcid_id || '').trim() || String(candidate.orcid || '').trim();
                    const marker = currentOrcidId && extractOrcidId(orcidId) === currentOrcidId
                        ? ' [current]'
                        : '';
                    return `${index + 1}. ${displayName} (${orcidId})${marker}`;
                })
                .join('\n');

            const choice = window.prompt(
                `Multiple ORCID matches found.${currentOrcidId ? `\nCurrent ORCID in field: ${currentOrcidId}` : ''}\nEnter a number (1-${candidates.length}) to choose:\n\n${options}`,
                String(defaultIndex + 1)
            );
            if (choice === null) {
                return null;
            }

            const selectedIndex = Number.parseInt(choice, 10) - 1;
            if (Number.isNaN(selectedIndex) || selectedIndex < 0 || selectedIndex >= candidates.length) {
                return null;
            }

            return candidates[selectedIndex];
        }

        return new Promise((resolve) => {
            const modalEl = document.createElement('div');
            modalEl.className = 'modal fade';
            modalEl.tabIndex = -1;
            modalEl.setAttribute('aria-hidden', 'true');

            const defaultSelectedIndex = currentOrcidId
                ? candidates.findIndex((candidate) => {
                    const candidateOrcid = candidate.orcid_id || candidate.orcid || '';
                    return extractOrcidId(candidateOrcid) === currentOrcidId;
                })
                : -1;
            const selectedIndex = defaultSelectedIndex >= 0 ? defaultSelectedIndex : 0;

            const candidateRows = candidates
                .map((candidate, index) => {
                    const displayName = String(candidate.display_name || '').trim() || `Candidate ${index + 1}`;
                    const givenName = String(candidate.given_names || '').trim();
                    const familyName = String(candidate.family_name || '').trim();
                    const normalizedName = [givenName, familyName].filter(Boolean).join(' ').trim();
                    const nameLabel = normalizedName || displayName;
                    const orcidId = String(candidate.orcid_id || '').trim() || String(candidate.orcid || '').trim();
                    const normalizedOrcidId = extractOrcidId(orcidId);
                    const orcidUrl = String(candidate.orcid || '').trim();
                    const affiliation = String(candidate.affiliation || '').trim();
                    const publicDataAvailable = Boolean(candidate.public_data_available);
                    const publicDataStatus = String(candidate.public_data_status || '').trim()
                        || (publicDataAvailable ? 'Public profile data available' : 'Limited public profile data');
                    const isCurrent = Boolean(currentOrcidId && normalizedOrcidId === currentOrcidId);
                    const checked = index === selectedIndex ? ' checked' : '';
                    const currentBadge = isCurrent
                        ? '<span class="badge text-bg-info ms-2">Current value</span>'
                        : '';
                    const affiliationLabel = affiliation
                        ? escapeHtml(affiliation)
                        : '<span class="text-muted">No public affiliation data</span>';
                    const availabilityBadge = publicDataAvailable
                        ? `<span class="badge text-bg-success">${escapeHtml(publicDataStatus)}</span>`
                        : `<span class="badge text-bg-secondary">${escapeHtml(publicDataStatus)}</span>`;
                    return `
                        <tr>
                            <td class="text-center align-middle">
                                <input
                                    class="form-check-input"
                                    type="radio"
                                    name="orcidCandidate"
                                    value="${index}"
                                    aria-label="Select ${escapeHtml(nameLabel)}"
                                    ${checked}
                                >
                            </td>
                            <td class="align-middle">${escapeHtml(nameLabel)}${currentBadge}</td>
                            <td class="align-middle"><code>${escapeHtml(orcidId || 'n/a')}</code></td>
                            <td class="align-middle">${affiliationLabel}</td>
                            <td class="align-middle">${availabilityBadge}</td>
                            <td class="align-middle">${orcidUrl ? `<a href="${escapeHtml(orcidUrl)}" target="_blank" rel="noopener noreferrer">Open</a>` : '-'}</td>
                        </tr>
                    `;
                })
                .join('');

            const currentOrcidNotice = currentOrcidId
                ? `<div class="alert alert-info py-2 mb-2"><strong>Current ORCID in field:</strong> <code>${escapeHtml(currentOrcidId)}</code></div>`
                : '';

            modalEl.innerHTML = `
                <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Multiple ORCID matches found</h5>
                            <button type="button" class="btn-close" aria-label="Close" data-role="close"></button>
                        </div>
                        <div class="modal-body">
                            <p class="mb-2">Select the correct person before filling the ORCID field.</p>
                            ${currentOrcidNotice}
                            <p class="text-muted small mb-2">Some ORCID profiles expose limited public data. Missing affiliation does not mean the ORCID is invalid.</p>
                            <div class="table-responsive border rounded">
                                <table class="table table-sm align-middle mb-0">
                                    <thead class="table-light">
                                        <tr>
                                            <th scope="col" class="text-center">Pick</th>
                                            <th scope="col">Name</th>
                                            <th scope="col">ORCID</th>
                                            <th scope="col">Affiliation</th>
                                            <th scope="col">Public data</th>
                                            <th scope="col">Profile</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${candidateRows}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-outline-secondary" data-role="cancel">Cancel</button>
                            <button type="button" class="btn btn-primary" data-role="apply">Use selected ORCID</button>
                        </div>
                    </div>
                </div>
            `;

            document.body.appendChild(modalEl);

            const modal = new window.bootstrap.Modal(modalEl, {
                backdrop: 'static',
                keyboard: false,
            });

            const applyBtn = modalEl.querySelector('[data-role="apply"]');
            const cancelBtn = modalEl.querySelector('[data-role="cancel"]');
            const closeBtn = modalEl.querySelector('[data-role="close"]');
            let selectedCandidate = candidates[selectedIndex] || null;

            const applySelection = () => {
                const selectedInput = modalEl.querySelector('input[name="orcidCandidate"]:checked');
                const selectedCandidateIndex = Number.parseInt(String(selectedInput?.value || ''), 10);
                if (!Number.isNaN(selectedCandidateIndex) && selectedCandidateIndex >= 0 && selectedCandidateIndex < candidates.length) {
                    selectedCandidate = candidates[selectedCandidateIndex];
                } else {
                    selectedCandidate = null;
                }
                modal.hide();
            };

            const cancelSelection = () => {
                selectedCandidate = null;
                modal.hide();
            };

            applyBtn?.addEventListener('click', applySelection);
            cancelBtn?.addEventListener('click', cancelSelection);
            closeBtn?.addEventListener('click', cancelSelection);

            modalEl.addEventListener('hidden.bs.modal', () => {
                modal.dispose();
                modalEl.remove();
                resolve(selectedCandidate);
            }, { once: true });

            modal.show();
        });
    }

    async function lookupOrcidForAuthorRow(row) {
        if (!row) return;

        const first = String(row.querySelector('.author-first')?.value || '').trim();
        const last = String(row.querySelector('.author-last')?.value || '').trim();
        const currentOrcid = String(row.querySelector('.author-orcid')?.value || '').trim();
        if (!first && !last) {
            showToast('Enter first name and/or last name before ORCID lookup.', 'warning');
            return;
        }

        const lookupBtn = row.querySelector('.author-orcid-find');
        const originalBtnText = lookupBtn ? setButtonLoading(lookupBtn, true, 'Searching...') : null;

        try {
            const params = new URLSearchParams();
            if (first) params.set('given_names', first);
            if (last) params.set('family_name', last);
            if (currentOrcid) params.set('current_orcid', currentOrcid);
            params.set('limit', '10');

            const response = await fetchWithApiFallback(`/api/projects/orcid/search?${params.toString()}`);
            const payload = await response.json();
            if (!response.ok || !payload?.success) {
                throw new Error(payload?.error || 'ORCID lookup failed');
            }

            if (!document.body.contains(row)) {
                return;
            }

            const candidates = Array.isArray(payload.candidates) ? payload.candidates : [];
            if (candidates.length === 0) {
                showToast('No ORCID match found for this name.', 'warning');
                return;
            }

            const chosenCandidate = await chooseOrcidCandidate(candidates, first, last, currentOrcid);
            if (!chosenCandidate) {
                showToast('ORCID selection canceled.', 'warning');
                return;
            }

            applyOrcidCandidateToAuthorRow(row, chosenCandidate);
            showToast(`ORCID selected: ${chosenCandidate.orcid_id || chosenCandidate.orcid || 'n/a'}`, 'success');
        } catch (error) {
            showToast(error?.message || 'ORCID lookup failed', 'danger');
        } finally {
            if (lookupBtn) {
                setButtonLoading(
                    lookupBtn,
                    false,
                    'Searching...',
                    originalBtnText || '<i class="fas fa-magnifying-glass"></i>'
                );
            }
        }
    }

    return {
        lookupOrcidForAuthorRow,
    };
}