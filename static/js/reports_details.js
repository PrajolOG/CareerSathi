/**
 * Career Sathi - Report Details Interface Logic
 * Handles career switching, roadmap progress, and Profile Radar Chart.
 */

// 1. Data Store Management
const store = document.getElementById('aiDataStore');
function safeParse(raw) {
    if (!raw || raw === '[]' || raw === 'null') return [];
    try {
        const parsed = JSON.parse(raw);
        if (typeof parsed === 'string') return JSON.parse(parsed);
        return parsed;
    } catch (e) {
        console.warn('JSON parse failed:', e, raw);
        return [];
    }
}

const DB_SPECIFIC_ROADMAPS = safeParse(store.dataset.roadmap);
const DB_MATCHING_FACTORS = safeParse(store.dataset.factors);
const USER_FEATURES = safeParse(store.dataset.features);

const ROADMAP_FALLBACK = [
    { icon: "fa-seedling", color: "#10B981", title: "Foundation", steps: ["Complete +2 / relevant degree", "Build basic subject knowledge", "Identify your strengths & interests"] },
    { icon: "fa-book-open", color: "#3B82F6", title: "Core Skills", steps: ["Enroll in a bachelor's program", "Learn domain-specific tools & software", "Join clubs and competitions"] },
    { icon: "fa-medal", color: "#8B5CF6", title: "Specialization", steps: ["Choose a sub-field to specialize in", "Complete internships & projects", "Earn relevant certifications"] },
    { icon: "fa-briefcase", color: "#F59E0B", title: "Career Entry", steps: ["Build a strong portfolio / CV", "Apply for entry-level roles", "Network through LinkedIn & events"] },
];

let activeCareerIndex = 0;
let radarChartInstance = null;

function getRadarVisualProfile() {
    const isMobile = window.matchMedia('(max-width: 640px)').matches;
    const isTablet = window.matchMedia('(max-width: 1024px)').matches;
    if (isMobile) {
        return { labelSize: 10, pointRadius: 3, pointHoverRadius: 4 };
    }
    if (isTablet) {
        return { labelSize: 11, pointRadius: 4, pointHoverRadius: 6 };
    }
    return { labelSize: 13, pointRadius: 5, pointHoverRadius: 7 };
}

// 2. Profile Alignment Radar Chart
function initAlignmentRadar() {
    const ctx = document.getElementById('profileRadarChart');
    if (!ctx || !USER_FEATURES) return;
    const radarProfile = getRadarVisualProfile();

    // Mapping Grade -> Score
    const mapGrade = (g) => {
        const scores = { 'A': 100, 'B': 80, 'C': 60, 'D': 40, 'E': 20 };
        return scores[g] || 0;
    };

    // Calculate score for each axis (0-100 scale)
    const axes = [
        { 
            id: 'technical',
            label: 'Technical', 
            val: (mapGrade(USER_FEATURES.grade_computer) + mapGrade(USER_FEATURES.grade_physics) + (USER_FEATURES.interest_technology || 0) * 10 + (USER_FEATURES.interest_construction || 0) * 10) / 4 
        },
        { 
            id: 'analytical',
            label: 'Analytical', 
            val: (mapGrade(USER_FEATURES.grade_math) + (USER_FEATURES.interest_math_stats || 0) * 10 + (USER_FEATURES.interest_gaming_entertainment || 0) * 10) / 3 
        },
        { 
            id: 'creative',
            label: 'Creative', 
            val: ((USER_FEATURES.interest_art_design || 0) * 10 + (USER_FEATURES.interest_history_culture || 0) * 10 + (USER_FEATURES.interest_hospitality_food || 0) * 10) / 3 
        },
        { 
            id: 'social',
            label: 'Social', 
            val: (mapGrade(USER_FEATURES.grade_social) + mapGrade(USER_FEATURES.grade_law) + (USER_FEATURES.interest_social_people || 0) * 10 + (USER_FEATURES.interest_law_politics || 0) * 10) / 4 
        },
        { 
            id: 'bio',
            label: 'Bio-Health', 
            val: (mapGrade(USER_FEATURES.grade_biology) + mapGrade(USER_FEATURES.grade_chemistry) + (USER_FEATURES.interest_bio_health || 0) * 10 + (USER_FEATURES.interest_nature_agri || 0) * 10) / 4 
        },
        { 
            id: 'business',
            label: 'Business', 
            val: (mapGrade(USER_FEATURES.grade_accounts) + mapGrade(USER_FEATURES.grade_economics) + (USER_FEATURES.interest_business_money || 0) * 10) / 3 
        }
    ];

    // Update legend scores
    axes.forEach(axis => {
        const legendItem = document.querySelector(`.legend-item[data-axis="${axis.id}"]`);
        if (legendItem) {
            const scoreEl = legendItem.querySelector('.legend-score');
            if (scoreEl) scoreEl.textContent = `${Math.round(axis.val)}%`;
        }
    });

    const data = {
        labels: axes.map(a => a.label),
        datasets: [{
            label: 'Your Alignment Profile',
            data: axes.map(a => a.val),
            fill: true,
            backgroundColor: 'rgba(79, 70, 229, 0.08)', 
            borderColor: 'rgb(79, 70, 229)',
            borderWidth: 2,
            pointBackgroundColor: [
                '#ef4444', // Technical (Red)
                '#3b82f6', // Analytical (Blue)
                '#f59e0b', // Creative (Amber)
                '#10b981', // Social (Emerald)
                '#8b5cf6', // Bio-Health (Violet)
                '#ec4899'  // Business (Pink)
            ],
            pointBorderColor: '#fff',
            pointRadius: radarProfile.pointRadius,
            pointHoverRadius: radarProfile.pointHoverRadius
        }]
    };

    const config = {
        type: 'radar',
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    angleLines: { display: true, color: 'rgba(0,0,0,0.05)' },
                    suggestedMin: 0,
                    suggestedMax: 100,
                    ticks: { display: false },
                    pointLabels: {
                        font: { family: 'Outfit, sans-serif', size: radarProfile.labelSize, weight: '600' },
                        color: '#64748b'
                    }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    };

    radarChartInstance = new Chart(ctx, config);
}

// 3. UI Interactions (Switching, Roadmap, Progress)
function renderRoadmap(careerName, index, skipAnimation = false) {
    let data = (DB_SPECIFIC_ROADMAPS && DB_SPECIFIC_ROADMAPS[index]) ? DB_SPECIFIC_ROADMAPS[index] : null;
    let phases = data ? data.phases : ROADMAP_FALLBACK;
    const timeline = document.getElementById('roadmapTimeline');
    const rdCareerName = document.getElementById('roadmapCareerName');
    if (rdCareerName) rdCareerName.textContent = careerName;

    timeline.innerHTML = phases.map((phase, i) => {
        let completedSteps = 0;
        let totalSteps = phase.steps.length;
        
        phase.steps.forEach(s => {
            const isChecked = typeof s === 'string' ? false : s.completed;
            if (isChecked) completedSteps++;
        });

        let isCompleted = (completedSteps === totalSteps && totalSteps > 0) ? "completed" : "";
        let isActive = (!isCompleted && completedSteps > 0) ? "active" : "";
        let phaseSpecificIcon = phase.icon || (i === 3 ? "fa-award" : "fa-ellipsis");
        let icon = isCompleted ? "fa-check" : phaseSpecificIcon;

        return `
        <div class="roadmap-phase ${isActive} ${isCompleted} ${skipAnimation ? 'no-animate' : ''}" style="animation-delay: ${i * 0.15}s">
            <div class="phase-indicator-wrap">
                <div class="phase-indicator">
                    <i class="fa-solid ${icon}"></i>
                </div>
            </div>
            <div class="phase-card">
                <div class="phase-card-header">
                    <div class="phase-meta">
                        <span class="phase-label">Phase 0${i + 1}</span>
                        <h3 class="phase-title">${phase.title}</h3>
                    </div>
                </div>
                <div class="phase-card-content">
                    <div class="phase-steps-col">
                        <div class="phase-steps">
                            ${phase.steps.map((s, si) => {
                                const textStr = typeof s === 'string' ? s : s.text;
                                const isChecked = typeof s === 'string' ? false : s.completed;
                                const parts = textStr.includes(':') ? textStr.split(':') : [textStr, ''];
                                return `
                                <div class="step-item ${isChecked ? 'checked' : ''}" onclick="toggleRoadmapStep(${index}, ${i}, ${si})" style="cursor: pointer;">
                                    <div class="step-check"><i class="fa-solid fa-check"></i></div>
                                    <div class="step-content">
                                        <span class="step-title">${parts[0].trim()}</span>
                                        ${parts[1] ? `<p class="step-desc">${parts[1].trim()}</p>` : ''}
                                    </div>
                                </div>`;
                            }).join('')}
                        </div>
                    </div>
                    <div class="phase-recommend-col">
                        ${phase.course_recommendation ? `
                            <div class="course-v2-card">
                                <div class="course-v2-content">
                                    <span class="course-v2-label">RECOMMENDED COURSE</span>
                                    <h4 class="course-v2-name">${phase.course_recommendation.name}</h4>
                                    <a href="${phase.course_recommendation.link}" target="_blank" class="course-v2-btn">
                                        Open <i class="fa-solid fa-up-right-from-square"></i>
                                    </a>
                                </div>
                            </div>
                        ` : `
                            <div class="course-v2-placeholder">
                                <i class="fa-solid fa-graduation-cap"></i>
                                <p>Preparation recommended for this phase.</p>
                            </div>
                        `}
                    </div>
                </div>
            </div>
        </div>`;
    }).join('');
    
    updateGlobalProgress(index);

    // Update factor lists
    const factorList = document.getElementById('factorList');
    if (factorList) {
        let factors = (DB_MATCHING_FACTORS && DB_MATCHING_FACTORS[index]) ? DB_MATCHING_FACTORS[index] : null;
        if (factors && Array.isArray(factors)) {
            factorList.innerHTML = factors.map(point => `
                <div class="logic-card">
                    <div class="logic-icon"><i class="fa-solid fa-star"></i></div>
                    <p class="logic-text">${point}</p>
                </div>
            `).join('');
        } else {
            factorList.innerHTML = '<div class="logic-card" style="grid-column: 1/-1"><p style="color: var(--text-secondary);">Strong profile alignment detected.</p></div>';
        }
    }
}

function switchCareer(index) {
    activeCareerIndex = index;
    const listItems = document.querySelectorAll('.career-list-item');
    listItems.forEach((item, i) => {
        item.classList.toggle('active', i === index);
        const btn = item.querySelector('.career-choose-btn');
        if (btn) {
            btn.classList.toggle('active', i === index);
            btn.textContent = i === index ? 'Selected' : 'Choose';
        }
    });

    const activeItem = document.querySelector(`.career-list-item[data-career-index="${index}"]`);
    const selectedName = activeItem ? activeItem.querySelector('.career-list-name').textContent.trim() : '';
    
    const featuredName = document.getElementById('featuredCareerName');
    if (featuredName) featuredName.textContent = selectedName;

    const featuredChip = document.getElementById('featuredRankChip');
    if (featuredChip) {
        featuredChip.innerHTML = index === 0 ? '<i class="fa-solid fa-star"></i> BEST MATCH' : '<i class="fa-solid fa-bullseye"></i> ALTERNATIVE';
    }

    const titleEl = document.getElementById('whyCareerTitle');
    if (titleEl) {
        titleEl.style.opacity = 0;
        setTimeout(() => { titleEl.textContent = `Why ${selectedName}?`; titleEl.style.opacity = 1; }, 150);
    }

    document.querySelectorAll('.career-course-set').forEach((set, i) => {
        set.classList.toggle('active', i === index);
    });

    renderRoadmap(selectedName, index);
}

function updateGlobalProgress(careerIndex) {
    if (!DB_SPECIFIC_ROADMAPS || !DB_SPECIFIC_ROADMAPS[careerIndex]) return;
    const phases = DB_SPECIFIC_ROADMAPS[careerIndex].phases;
    let total = 0, done = 0;
    phases.forEach(p => p.steps.forEach(s => { total++; if (s.completed) done++; }));
    
    const percent = total > 0 ? Math.round((done / total) * 100) : 0;
    const circle = document.getElementById('progressCircle');
    const text = document.getElementById('progressPercent');
    if (circle && text) {
        const circum = 2 * Math.PI * 40;
        circle.style.strokeDasharray = circum;
        circle.style.strokeDashoffset = circum - (percent / 100) * circum;
        text.textContent = `${percent}%`;
    }
}

async function toggleRoadmapStep(careerIndex, phaseIndex, stepIndex) {
    if (!DB_SPECIFIC_ROADMAPS || !DB_SPECIFIC_ROADMAPS[careerIndex]) return;
    let step = DB_SPECIFIC_ROADMAPS[careerIndex].phases[phaseIndex].steps[stepIndex];
    if (typeof step === 'string') step = DB_SPECIFIC_ROADMAPS[careerIndex].phases[phaseIndex].steps[stepIndex] = { text: step, completed: false };
    
    step.completed = !step.completed;
    const currentName = document.getElementById('featuredCareerName').textContent;
    renderRoadmap(currentName, careerIndex, true);

    const reportId = store.dataset.reportId;
    try {
        await fetch(`/reports/${reportId}/roadmap-progress`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ roadmap: DB_SPECIFIC_ROADMAPS })
        });
    } catch (err) { console.error("Sync failed", err); }
}

// --- SECRET DELETE DROPDOWN LOGIC ---
const secretDropdown = document.getElementById('secretDropdown');
const dropdownInitial = document.getElementById('dropdownInitialState');
const dropdownConfirm = document.getElementById('dropdownConfirmState');

function toggleSecretDropdown() {
    if (!secretDropdown) return;
    secretDropdown.classList.toggle('active');
    // Always reset to initial state when toggling
    hideDeleteConfirm();
}

function showDeleteConfirm() {
    if (!dropdownInitial || !dropdownConfirm) return;
    dropdownInitial.style.display = 'none';
    dropdownConfirm.style.display = 'block';
}

function hideDeleteConfirm() {
    if (!dropdownInitial || !dropdownConfirm) return;
    dropdownInitial.style.display = 'block';
    dropdownConfirm.style.display = 'none';
}

async function executeReportDelete() {
    // Corrected data retrieval from the globally defined 'store' element
    const reportId = store ? store.dataset.reportId : null;
    
    if (!reportId) {
        console.error('Delete failed: Missing report ID in store');
        alert('Internal Error: Could not find report ID.');
        return;
    }

    try {
        const btn = document.querySelector('.btn-confirm-yes');
        btn.disabled = true;
        btn.textContent = 'Deleting...';

        const response = await fetch(`/reports/${reportId}`, {
            method: 'DELETE',
        });

        if (response.ok) {
            // Success - Redirect back to reports list
            window.location.href = '/reports?msg=deleted';
        } else {
            let errorText = 'Delete failed';
            try {
                const err = await response.json();
                errorText = err.detail || errorText;
            } catch (e) {
                errorText = `HTTP Error ${response.status}`;
            }
            alert(errorText);
            btn.disabled = false;
            btn.textContent = 'Yes, Delete';
        }
    } catch (error) {
        console.error('Delete error:', error);
        alert('Network Error: Could not reach server.');
        const btn = document.querySelector('.btn-confirm-yes');
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Yes, Delete';
        }
    }
}

// Close dropdown when clicking outside
document.addEventListener('click', function(e) {
    const container = document.querySelector('.secret-actions-container');
    if (container && !container.contains(e.target)) {
        secretDropdown.classList.remove('active');
    }
});

// 5. Initialize
document.addEventListener('DOMContentLoaded', () => {
    initAlignmentRadar();
    switchCareer(0);
});
