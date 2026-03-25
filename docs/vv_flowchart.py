"""
V&V (Verification & Validation) Flow Chart
Based on NIST Technical Note 1822 (Ronchi et al., 2013)
Adapted for: Tagless Gate Pedestrian Simulation (JuPedSim GCFM)

Reference:
  - Ronchi, E., Kuligowski, E.D., Reneke, P.A., Peacock, R.D., Nilsson, D. (2013)
    "The Process of Verification and Validation of Building Fire Evacuation Models"
    NIST TN 1822. https://doi.org/10.6028/NIST.TN.1822
  - ISO 20414:2020 (formalized from NIST TN 1822)
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pathlib

OUTPUT_DIR = pathlib.Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def draw_box(ax, x, y, w, h, text, color, fontsize=9, bold=False, text_color='black'):
    """Draw a rounded rectangle with centered text."""
    box = mpatches.FancyBboxPatch(
        (x - w/2, y - h/2), w, h,
        boxstyle="round,pad=0.15",
        facecolor=color, edgecolor='#333333', linewidth=1.5
    )
    ax.add_patch(box)
    weight = 'bold' if bold else 'normal'
    ax.text(x, y, text, ha='center', va='center', fontsize=fontsize,
            fontweight=weight, color=text_color, wrap=True,
            multialignment='center')


def draw_diamond(ax, x, y, w, h, text, color='#FFF3CD', fontsize=8):
    """Draw a diamond (decision) shape."""
    diamond = plt.Polygon([
        (x, y + h/2), (x + w/2, y), (x, y - h/2), (x - w/2, y)
    ], facecolor=color, edgecolor='#333333', linewidth=1.5, closed=True)
    ax.add_patch(diamond)
    ax.text(x, y, text, ha='center', va='center', fontsize=fontsize,
            fontweight='bold', multialignment='center')


def draw_arrow(ax, x1, y1, x2, y2, label='', color='#333333'):
    """Draw arrow from (x1,y1) to (x2,y2)."""
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=1.5))
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx + 0.15, my, label, fontsize=7, color='#666666', ha='left', va='center')


def draw_bracket_text(ax, x, y, lines, fontsize=7.5, color='#555555'):
    """Draw small annotation text."""
    text = '\n'.join(lines)
    ax.text(x, y, text, fontsize=fontsize, color=color, va='top',
            fontfamily='monospace', linespacing=1.4)


def create_flowchart():
    fig, ax = plt.subplots(figsize=(18, 26))
    ax.set_xlim(-1, 17)
    ax.set_ylim(-1, 27)
    ax.axis('off')
    ax.set_aspect('equal')

    # Title
    ax.text(8, 26.3, 'V&V Framework for Pedestrian Simulation',
            fontsize=16, fontweight='bold', ha='center', va='center')
    ax.text(8, 25.8, 'Based on NIST TN 1822 (Ronchi et al., 2013) — Adapted for Tagless Gate Study',
            fontsize=10, ha='center', va='center', color='#666666')

    # =========================================================================
    # PHASE 0: Model Selection
    # =========================================================================
    y0 = 24.5
    draw_box(ax, 8, y0, 5.5, 0.9,
             'Phase 0: Model Selection\nGCFM (Chraibi et al., 2010)',
             '#E8F5E9', fontsize=10, bold=True)

    draw_bracket_text(ax, 11.5, y0 + 0.2, [
        'Selection criteria:',
        '  - Force-based: natural queuing',
        '  - Elliptical body: directional',
        '  - Gate bottleneck suitability',
    ])

    draw_arrow(ax, 8, y0 - 0.45, 8, y0 - 1.05)

    # =========================================================================
    # PHASE 1: VERIFICATION (Core)
    # =========================================================================
    y1_top = 23.0
    # Phase header
    draw_box(ax, 8, y1_top, 14, 0.8,
             'Phase 1: VERIFICATION  —  "Is the model implemented correctly?"',
             '#1565C0', fontsize=11, bold=True, text_color='white')

    # --- 1A: Analytical Verification (AN_VERIF) ---
    y_an = 21.5
    draw_box(ax, 4.5, y_an, 6.5, 0.7,
             '1A. Analytical Verification (AN_VERIF)',
             '#BBDEFB', fontsize=9, bold=True)

    # AN_VERIF tests
    tests_an = [
        ('Verif.2.1', 'Free-flow speed\nin corridor', '#E3F2FD', 'DONE'),
        ('Verif.2.2', 'Speed on\nstairs', '#E3F2FD', 'N/A'),
        ('Verif.2.4', 'Demographic\nspeed dist.', '#E3F2FD', 'TODO'),
        ('Verif.5.2', 'Max flow rate\nat bottleneck', '#E3F2FD', 'DONE'),
        ('Verif.3.1', 'Exit/gate\nallocation', '#E3F2FD', 'TODO'),
    ]

    y_tests = 20.2
    for i, (tid, desc, color, status) in enumerate(tests_an):
        tx = 1.5 + i * 2.8
        if status == 'DONE':
            c = '#C8E6C9'
        elif status == 'N/A':
            c = '#E0E0E0'
        else:
            c = '#FFF9C4'
        draw_box(ax, tx, y_tests, 2.4, 1.2, f'{tid}\n{desc}\n[{status}]', c, fontsize=7)

    draw_arrow(ax, 4.5, y_an - 0.35, 4.5, y_tests + 0.65)

    # --- 1B: Emergent Behaviour Verification (EB_VERIF) ---
    y_eb = 21.5
    draw_box(ax, 12.5, y_eb, 6.5, 0.7,
             '1B. Emergent Behaviour Verification (EB_VERIF)',
             '#BBDEFB', fontsize=9, bold=True)

    tests_eb = [
        ('Verif.2.5', 'Counterflow\nlane formation', '#E3F2FD', 'TODO'),
        ('Verif.5.1', 'Congestion\n& queuing', '#E3F2FD', 'TODO'),
        ('Verif.1.1', 'Pre-evac time\ndistribution', '#E3F2FD', 'N/A'),
    ]

    for i, (tid, desc, color, status) in enumerate(tests_eb):
        tx = 10.5 + i * 2.8
        if status == 'DONE':
            c = '#C8E6C9'
        elif status == 'N/A':
            c = '#E0E0E0'
        else:
            c = '#FFF9C4'
        draw_box(ax, tx, y_tests, 2.4, 1.2, f'{tid}\n{desc}\n[{status}]', c, fontsize=7)

    draw_arrow(ax, 12.5, y_eb - 0.35, 12.5, y_tests + 0.65)

    # Fundamental Diagram (special — spans both)
    y_fd = 18.5
    draw_box(ax, 8, y_fd, 6, 1.0,
             'Fundamental Diagram Verification\ndensity vs. speed (Weidmann 1993)\n[DONE]',
             '#C8E6C9', fontsize=9, bold=True)

    draw_arrow(ax, 4.5, y_tests - 0.65, 4.5, y_fd + 0.5)
    draw_arrow(ax, 12.5, y_tests - 0.65, 12.5, y_fd + 0.5)

    # Decision: Verification Pass?
    y_dec1 = 17.0
    draw_diamond(ax, 8, y_dec1, 3.5, 1.2, 'All Verification\nTests PASS?')

    draw_arrow(ax, 8, y_fd - 0.5, 8, y_dec1 + 0.6)

    # Fail path
    ax.annotate('', xy=(14, y_dec1), xytext=(9.75, y_dec1),
                arrowprops=dict(arrowstyle='->', color='red', lw=1.5))
    ax.text(11, y_dec1 + 0.25, 'FAIL', fontsize=8, color='red', fontweight='bold')

    draw_box(ax, 15.5, y_dec1, 2.5, 0.8,
             'Adjust GCFM\nparameters', '#FFCDD2', fontsize=8)
    # Loop back arrow
    ax.annotate('', xy=(15.5, y_an + 0.35), xytext=(15.5, y_dec1 + 0.4),
                arrowprops=dict(arrowstyle='->', color='red', lw=1.2,
                                connectionstyle='arc3,rad=0'))

    # Pass path
    ax.text(7.5, y_dec1 - 0.85, 'PASS', fontsize=8, color='green', fontweight='bold')

    # =========================================================================
    # PHASE 2: CALIBRATION
    # =========================================================================
    y2_top = 15.0
    draw_box(ax, 8, y2_top, 14, 0.8,
             'Phase 2: CALIBRATION  —  "Fit parameters to field data"',
             '#E65100', fontsize=11, bold=True, text_color='white')

    draw_arrow(ax, 8, y_dec1 - 0.6, 8, y2_top + 0.4)

    # Calibration steps
    y_cal = 13.7
    draw_box(ax, 3.5, y_cal, 4.5, 1.2,
             'Field Survey\n(Ui-Sinseol Line)\n- Gate service time\n- Walking speed\n- Arrival rate',
             '#FFF3E0', fontsize=8)

    draw_box(ax, 8, y_cal, 3.5, 1.2,
             'Parameter\nOptimization\n(manual / GA / PSO)',
             '#FFF3E0', fontsize=8)

    draw_box(ax, 12.5, y_cal, 4.5, 1.2,
             'Target Metrics\n- Flow rate (P/s)\n- Queue length\n- Passage time dist.',
             '#FFF3E0', fontsize=8)

    draw_arrow(ax, 3.5, y2_top - 0.4, 3.5, y_cal + 0.6)
    draw_arrow(ax, 8, y2_top - 0.4, 8, y_cal + 0.6)
    draw_arrow(ax, 12.5, y2_top - 0.4, 12.5, y_cal + 0.6)
    draw_arrow(ax, 5.75, y_cal, 6.25, y_cal)
    draw_arrow(ax, 9.75, y_cal, 10.25, y_cal)

    # =========================================================================
    # PHASE 3: VALIDATION
    # =========================================================================
    y3_top = 12.0
    draw_box(ax, 8, y3_top, 14, 0.8,
             'Phase 3: VALIDATION  —  "Does the model represent reality?"',
             '#2E7D32', fontsize=11, bold=True, text_color='white')

    draw_arrow(ax, 8, y_cal - 0.6, 8, y3_top + 0.4)

    y_val = 10.7
    draw_box(ax, 3.5, y_val, 4.5, 1.2,
             'Independent Dataset\n(NOT used in calibration)\n- Different time period\n- Different station',
             '#E8F5E9', fontsize=8)

    draw_box(ax, 8, y_val, 3.5, 1.2,
             'Comparison\nMetrics\nRMSE, MAPE,\nKS test, ERD/EPC',
             '#E8F5E9', fontsize=8)

    draw_box(ax, 12.5, y_val, 4.5, 1.2,
             'Seyfried et al. (2009)\nBottleneck flow data\n+ Field observation',
             '#E8F5E9', fontsize=8)

    draw_arrow(ax, 3.5, y3_top - 0.4, 3.5, y_val + 0.6)
    draw_arrow(ax, 8, y3_top - 0.4, 8, y_val + 0.6)
    draw_arrow(ax, 12.5, y3_top - 0.4, 12.5, y_val + 0.6)
    draw_arrow(ax, 5.75, y_val, 6.25, y_val)
    draw_arrow(ax, 9.75, y_val, 10.25, y_val)

    # Decision: Validation Pass?
    y_dec2 = 9.0
    draw_diamond(ax, 8, y_dec2, 3.5, 1.2, 'Validation\nAcceptable?')
    draw_arrow(ax, 8, y_val - 0.6, 8, y_dec2 + 0.6)

    # Fail path
    ax.annotate('', xy=(14, y_dec2), xytext=(9.75, y_dec2),
                arrowprops=dict(arrowstyle='->', color='red', lw=1.5))
    ax.text(11, y_dec2 + 0.25, 'FAIL', fontsize=8, color='red', fontweight='bold')
    draw_box(ax, 15.5, y_dec2, 2.5, 0.8,
             'Re-calibrate\nor revise model', '#FFCDD2', fontsize=8)
    ax.annotate('', xy=(15.5, y2_top + 0.4), xytext=(15.5, y_dec2 + 0.4),
                arrowprops=dict(arrowstyle='->', color='red', lw=1.2))

    ax.text(7.5, y_dec2 - 0.85, 'PASS', fontsize=8, color='green', fontweight='bold')

    # =========================================================================
    # PHASE 4: UNCERTAINTY ANALYSIS
    # =========================================================================
    y4_top = 7.2
    draw_box(ax, 8, y4_top, 14, 0.8,
             'Phase 4: UNCERTAINTY ANALYSIS  —  "How many runs are needed?"',
             '#4A148C', fontsize=11, bold=True, text_color='white')

    draw_arrow(ax, 8, y_dec2 - 0.6, 8, y4_top + 0.4)

    y_ua = 5.9
    draw_box(ax, 4, y_ua, 5, 1.2,
             'Behavioural Uncertainty\nStochastic variables:\n- Desired speed dist.\n- Personality type ratio\n- Arrival pattern',
             '#F3E5F5', fontsize=8)

    draw_box(ax, 12, y_ua, 5, 1.2,
             'Functional Analysis\nConvergence Criteria\n(ERD & EPC metrics)\nDetermine min. N runs\nfor stable results',
             '#F3E5F5', fontsize=8)

    draw_arrow(ax, 4, y4_top - 0.4, 4, y_ua + 0.6)
    draw_arrow(ax, 12, y4_top - 0.4, 12, y_ua + 0.6)
    draw_arrow(ax, 6.5, y_ua, 9.5, y_ua)

    # =========================================================================
    # PHASE 5: SCENARIO ANALYSIS
    # =========================================================================
    y5_top = 4.2
    draw_box(ax, 8, y5_top, 14, 0.8,
             'Phase 5: SCENARIO ANALYSIS  —  "Apply to research question"',
             '#B71C1C', fontsize=11, bold=True, text_color='white')

    draw_arrow(ax, 8, y_ua - 0.6, 8, y5_top + 0.4)

    y_sc = 2.8
    draw_box(ax, 3, y_sc, 4, 1.3,
             'Baseline\nCurrent mixed gates\n(tag + tagless)',
             '#FFEBEE', fontsize=8, bold=True)

    draw_box(ax, 8, y_sc, 4, 1.3,
             'Scenario A\nSeparated tagless\ngates (various configs)',
             '#FFEBEE', fontsize=8, bold=True)

    draw_box(ax, 13, y_sc, 4, 1.3,
             'Compare\nTravel cost savings\nQueue reduction\nLevel of Service',
             '#FFEBEE', fontsize=8, bold=True)

    draw_arrow(ax, 3, y5_top - 0.4, 3, y_sc + 0.65)
    draw_arrow(ax, 8, y5_top - 0.4, 8, y_sc + 0.65)
    draw_arrow(ax, 13, y5_top - 0.4, 13, y_sc + 0.65)
    draw_arrow(ax, 5, y_sc, 6, y_sc)
    draw_arrow(ax, 10, y_sc, 11, y_sc)

    # Final output
    y_final = 1.2
    draw_box(ax, 8, y_final, 6, 0.8,
             'Results & Conclusions\nOptimal tagless gate placement',
             '#263238', fontsize=10, bold=True, text_color='white')
    draw_arrow(ax, 8, y_sc - 0.65, 8, y_final + 0.4)

    # =========================================================================
    # Legend
    # =========================================================================
    legend_y = 0.0
    legend_items = [
        ('#C8E6C9', 'DONE'),
        ('#FFF9C4', 'TODO'),
        ('#E0E0E0', 'N/A (not applicable)'),
        ('#FFCDD2', 'Fail / Re-do'),
    ]
    for i, (c, label) in enumerate(legend_items):
        lx = 2.5 + i * 3.5
        box = mpatches.FancyBboxPatch(
            (lx - 0.3, legend_y - 0.15), 0.6, 0.3,
            boxstyle="round,pad=0.05", facecolor=c, edgecolor='#333333', linewidth=1
        )
        ax.add_patch(box)
        ax.text(lx + 0.5, legend_y, label, fontsize=8, va='center')

    # Reference
    ax.text(8, -0.7,
            'Reference: Ronchi et al. (2013) NIST TN 1822; ISO 20414:2020; Chraibi et al. (2010)',
            fontsize=8, ha='center', color='#999999')

    fig.savefig(OUTPUT_DIR / 'vv_flowchart.png', dpi=200, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    print(f"Saved: {OUTPUT_DIR / 'vv_flowchart.png'}")


if __name__ == '__main__':
    create_flowchart()
