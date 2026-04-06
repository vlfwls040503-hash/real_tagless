"""
시나리오 비교 분석: 기본(0% 태그리스) vs 전면 태그리스(100%)
- 계단 병목 유량 (Staircase bottleneck flow)
- 게이트 처리량 (Gate throughput)
- 첨두/비첨두 구분 (Peak / Off-peak periods)
- 통행비용 비교 (Travel cost comparison)

주의: 소프트웨어 큐 구조상 에이전트는 게이트 전(moving/queue)과 후(passed)에서
      서로 다른 JuPedSim ID를 가짐. 분석은 단계별로 분리해서 처리.
"""

import csv
import pathlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from collections import defaultdict

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

OUTPUT_DIR = pathlib.Path(__file__).parent.parent / "output"

# ─── 열차 도착 파라미터 ────────────────────────────────────────────────────────
FIRST_TRAIN_TIME = 5.0
TRAIN_INTERVAL   = 180.0
SIM_TIME         = 720.0
N_TRAINS         = 4  # t = 5, 185, 365, 545 s

# 첨두 정의: 열차 도착 후 [+20, +110] 초 구간
PEAK_OFFSET_START = 20.0
PEAK_OFFSET_END   = 110.0

TRAIN_TIMES  = [FIRST_TRAIN_TIME + i * TRAIN_INTERVAL for i in range(N_TRAINS)]
PEAK_WINDOWS = [(t + PEAK_OFFSET_START, t + PEAK_OFFSET_END) for t in TRAIN_TIMES]


def is_peak(t):
    return any(lo <= t <= hi for lo, hi in PEAK_WINDOWS)


# =============================================================================
# 데이터 로드 & 분리
# =============================================================================
def load_scenario(csv_path):
    """
    에이전트를 게이트 통과 전(pre-gate)과 후(post-gate)로 분리.

    pre-gate  : state = 'moving' 또는 'queue'  (게이트 도달 전)
    post-gate : state = 'passed'               (게이트 통과 후, 새 ID 부여)

    ID가 'passed' 레코드를 가지면 post-gate 에이전트,
    그렇지 않으면 pre-gate 에이전트로 분류.
    """
    rows = defaultdict(list)
    with open(csv_path) as f:
        for r in csv.DictReader(f):
            rows[r['agent_id']].append({
                't':     float(r['time']),
                'x':     float(r['x']),
                'y':     float(r['y']),
                'state': r['state'],
                'gate':  int(r['gate_idx']),
            })

    pre_gate  = {}   # 게이트 전 에이전트: arrival_t, wait_t, approach_dur, gate
    post_gate = {}   # 게이트 후 에이전트: gate_pass_t, exit_dur

    for aid, records in rows.items():
        records.sort(key=lambda r: r['t'])
        has_passed = any(r['state'] == 'passed' for r in records)

        if has_passed:
            # ── post-gate ──
            pass_recs = [r for r in records if r['state'] == 'passed']
            gate_pass_t = pass_recs[0]['t']
            exit_dur    = pass_recs[-1]['t'] - pass_recs[0]['t']
            gate_idx    = pass_recs[-1]['gate']
            post_gate[aid] = {
                'gate_pass_t': gate_pass_t,
                'exit_dur':    exit_dur,
                'gate':        gate_idx,
                'peak':        is_peak(gate_pass_t),
            }
        else:
            # ── pre-gate ──
            arrival_t    = records[0]['t']
            move_recs    = [r for r in records if r['state'] == 'moving']
            queue_recs   = [r for r in records if r['state'] == 'queue']
            approach_dur = (move_recs[-1]['t'] - move_recs[0]['t']) if len(move_recs) >= 2 else 0.0
            if len(queue_recs) >= 2:
                wait_t = queue_recs[-1]['t'] - queue_recs[0]['t']
            else:
                wait_t = 0.0
            gate_idx = queue_recs[-1]['gate'] if queue_recs else (move_recs[-1]['gate'] if move_recs else -1)
            pre_gate[aid] = {
                'arrival_t':    arrival_t,
                'approach_dur': approach_dur,
                'wait_t':       wait_t,
                'gate':         gate_idx,
                'peak':         is_peak(arrival_t),
            }

    return pre_gate, post_gate


# =============================================================================
# 유량 시계열 계산
# =============================================================================
def flow_series(times, bin_size=30.0, t_max=SIM_TIME):
    bins    = np.arange(0, t_max + bin_size, bin_size)
    counts, _ = np.histogram(times, bins=bins)
    centers = (bins[:-1] + bins[1:]) / 2
    return centers, counts


# =============================================================================
# 분석 & 출력
# =============================================================================
def analyze(pre_gate, post_gate, label):
    n_pre  = len(pre_gate)
    n_post = len(post_gate)
    total  = n_pre + n_post   # 총 에이전트 수 (pre + post, 대략 전체 × 2)

    arrival_ts  = [a['arrival_t']    for a in pre_gate.values()]
    wait_times  = [a['wait_t']       for a in pre_gate.values()]
    approach_ds = [a['approach_dur'] for a in pre_gate.values()]

    pass_ts   = [a['gate_pass_t'] for a in post_gate.values()]
    exit_durs = [a['exit_dur']    for a in post_gate.values()]

    peak_wait    = [a['wait_t'] for a in pre_gate.values() if a['peak']]
    offpeak_wait = [a['wait_t'] for a in pre_gate.values() if not a['peak']]

    # 통과 인원 = post-gate 에이전트 수 (pre와 1:1 대응)
    pass_rate = n_post / (n_pre + n_post) * 2 * 100  # 전체의 %

    print(f"\n{'='*58}")
    print(f"  시나리오: {label}")
    print(f"  전처리: pre-gate={n_pre}명, post-gate(통과)={n_post}명")
    print(f"{'='*58}")
    print(f"  통과율          : {n_post/(n_pre+n_post if n_pre+n_post else 1)*200:.1f}%  (약 {n_post}명 통과)")
    print(f"  평균 접근시간   : {np.mean(approach_ds):.1f}s  (계단→게이트 전까지)")
    print(f"  평균 대기시간   : {np.mean(wait_times):.1f}s  (큐 내 대기)")
    print(f"  평균 퇴장시간   : {np.mean(exit_durs):.1f}s  (게이트→출구)")
    est_total = np.mean(approach_ds) + np.mean(wait_times) + np.mean(exit_durs)
    print(f"  추정 총 통행시간: {est_total:.1f}s")
    total_cost_hrs = (sum(approach_ds) + sum(wait_times) + sum(exit_durs)) / 3600
    print(f"  총 통행비용     : {total_cost_hrs:.2f} 인시")
    print(f"\n  첨두 대기시간: {len(peak_wait)}명  평균 {np.mean(peak_wait) if peak_wait else 0:.1f}s  "
          f"최대 {np.max(peak_wait) if peak_wait else 0:.1f}s")
    print(f"  비첨두 대기시간: {len(offpeak_wait)}명  평균 {np.mean(offpeak_wait) if offpeak_wait else 0:.1f}s  "
          f"최대 {np.max(offpeak_wait) if offpeak_wait else 0:.1f}s")

    return {
        'label': label,
        'n_pre': n_pre, 'n_post': n_post,
        'arrival_ts': arrival_ts, 'pass_ts': pass_ts,
        'wait_times': wait_times, 'exit_durs': exit_durs,
        'approach_ds': approach_ds,
        'peak_wait': peak_wait, 'offpeak_wait': offpeak_wait,
        'est_total_t': np.mean(approach_ds) + np.mean(wait_times) + np.mean(exit_durs),
        'total_cost_hrs': total_cost_hrs,
    }


# =============================================================================
# 요약 표
# =============================================================================
def print_summary_table(rb, rt):
    def d(a, b):
        return (b - a) / a * 100 if a else 0

    print("\n" + "=" * 70)
    print(f"  {'지표':<26} {'기본(0%)':>10} {'태그리스(100%)':>14} {'변화':>8}")
    print("=" * 70)
    print(f"  {'통과 인원 (명)':<26} {rb['n_post']:>10} {rt['n_post']:>14}")
    print(f"  {'총 통행비용 (인시)':<26} {rb['total_cost_hrs']:>10.2f} {rt['total_cost_hrs']:>14.2f} "
          f"{d(rb['total_cost_hrs'], rt['total_cost_hrs']):>+7.1f}%")
    print(f"  {'추정 총 통행시간 (s)':<26} {rb['est_total_t']:>10.1f} {rt['est_total_t']:>14.1f} "
          f"{d(rb['est_total_t'], rt['est_total_t']):>+7.1f}%")
    print(f"  {'평균 접근시간 (s)':<26} {np.mean(rb['approach_ds']):>10.1f} "
          f"{np.mean(rt['approach_ds']):>14.1f} "
          f"{d(np.mean(rb['approach_ds']), np.mean(rt['approach_ds'])):>+7.1f}%")
    print(f"  {'평균 대기시간 (s)':<26} {np.mean(rb['wait_times']):>10.1f} "
          f"{np.mean(rt['wait_times']):>14.1f} "
          f"{d(np.mean(rb['wait_times']), np.mean(rt['wait_times'])):>+7.1f}%")
    print(f"  {'첨두 대기시간 (s)':<26} "
          f"{np.mean(rb['peak_wait']) if rb['peak_wait'] else 0:>10.1f} "
          f"{np.mean(rt['peak_wait']) if rt['peak_wait'] else 0:>14.1f} "
          f"{d(np.mean(rb['peak_wait']) if rb['peak_wait'] else 1, np.mean(rt['peak_wait']) if rt['peak_wait'] else 0):>+7.1f}%")
    print(f"  {'비첨두 대기시간 (s)':<26} "
          f"{np.mean(rb['offpeak_wait']) if rb['offpeak_wait'] else 0:>10.1f} "
          f"{np.mean(rt['offpeak_wait']) if rt['offpeak_wait'] else 0:>14.1f}")
    print("=" * 70)

    # 병목 분석
    print("\n[계단-게이트 병목 분석]")
    stair_cap     = 3.7 * 1.25       # Weidmann (1993): ped/s
    gate_base_cap = 7 / 2.0          # 7 gates, avg service 2.0s
    gate_tag_cap  = 7 / 1.2          # 7 gates, avg service 1.2s
    print(f"  계단 용량              : {stair_cap:.2f} ped/s  ({stair_cap*60:.0f} ped/min)")
    print(f"  게이트 용량 기본(T=2s) : {gate_base_cap:.2f} ped/s  ({gate_base_cap*60:.0f} ped/min)")
    print(f"  게이트 용량 태그(T=1.2s): {gate_tag_cap:.2f} ped/s  ({gate_tag_cap*60:.0f} ped/min)")
    print(f"  -> 기본:     계단({stair_cap:.1f}) > 게이트({gate_base_cap:.1f}) -> 게이트 병목")
    print(f"  -> 태그리스: 게이트({gate_tag_cap:.1f}) > 계단({stair_cap:.1f}) -> 계단 병목 (병목 전이!)")


# =============================================================================
# 시각화
# =============================================================================
def plot_comparison(rb, rt):
    fig, axes = plt.subplots(3, 2, figsize=(16, 14))
    fig.suptitle('시나리오 비교: 기본(0%) vs 전면 태그리스(100%)',
                 fontsize=14, fontweight='bold', y=0.98)

    BIN  = 30.0
    CB   = '#1565C0'   # 기본 (blue)
    CT   = '#00BFA5'   # 태그리스 (teal)

    # ── [0,0] 계단 도착 유량 ─────────────────────────────────────────────────
    ax = axes[0, 0]
    tc, cc = flow_series(rb['arrival_ts'], BIN)
    ax.bar(tc, cc, width=BIN * 0.88, color=CB, alpha=0.7, label='도착 유량 (공통)')
    for tt in TRAIN_TIMES:
        ax.axvline(tt, color='red', lw=1.5, ls='--', alpha=0.7)
    for lo, hi in PEAK_WINDOWS:
        ax.axvspan(lo, hi, color='#FFCDD2', alpha=0.25)
    ax.set_title('계단 도착 유량 (30s 빈)')
    ax.set_xlabel('시간 (s)'); ax.set_ylabel('도착 (명/30s)')
    ax.text(0.97, 0.93, '빨간선=열차, 분홍=첨두', transform=ax.transAxes,
            ha='right', fontsize=8, color='gray')
    ax.legend(fontsize=9)

    # ── [0,1] 게이트 처리 유량 ───────────────────────────────────────────────
    ax = axes[0, 1]
    tb_b, cb_b = flow_series(rb['pass_ts'], BIN)
    tb_t, cb_t = flow_series(rt['pass_ts'], BIN)
    ax.step(tb_b, cb_b, where='mid', color=CB, lw=2, label='기본 (0%)')
    ax.step(tb_t, cb_t, where='mid', color=CT, lw=2, label='태그리스 (100%)')
    # 계단 용량선
    stair_cap = 3.7 * 1.25 * BIN
    ax.axhline(stair_cap, color='gray', ls=':', lw=1.5, alpha=0.7, label=f'계단 최대 ({stair_cap:.0f}/30s)')
    for tt in TRAIN_TIMES:
        ax.axvline(tt, color='red', lw=1.5, ls='--', alpha=0.5)
    for lo, hi in PEAK_WINDOWS:
        ax.axvspan(lo, hi, color='#FFCDD2', alpha=0.2)
    ax.set_title('게이트 처리 유량 (30s 빈)')
    ax.set_xlabel('시간 (s)'); ax.set_ylabel('처리 (명/30s)')
    ax.legend(fontsize=9)

    # ── [1,0] 대기시간 분포 ─────────────────────────────────────────────────
    ax = axes[1, 0]
    wt_max = max(max(rb['wait_times']) if rb['wait_times'] else 0,
                 max(rt['wait_times']) if rt['wait_times'] else 0) + 10
    bins_wt = np.arange(0, wt_max, 5)
    ax.hist(rb['wait_times'], bins=bins_wt, color=CB, alpha=0.55,
            label=f"기본 (평균 {np.mean(rb['wait_times']):.1f}s)", density=True)
    ax.hist(rt['wait_times'], bins=bins_wt, color=CT, alpha=0.55,
            label=f"태그리스 (평균 {np.mean(rt['wait_times']):.1f}s)", density=True)
    ax.axvline(np.mean(rb['wait_times']), color=CB, lw=2, ls='--')
    ax.axvline(np.mean(rt['wait_times']), color=CT, lw=2, ls='--')
    ax.set_title('대기시간 분포 (큐 내)')
    ax.set_xlabel('대기시간 (s)'); ax.set_ylabel('밀도')
    ax.legend(fontsize=9)

    # ── [1,1] 첨두/비첨두 대기시간 박스플롯 ─────────────────────────────────
    ax = axes[1, 1]
    peak_b = rb['peak_wait'] or [0]
    off_b  = rb['offpeak_wait'] or [0]
    peak_t = rt['peak_wait'] or [0]
    off_t  = rt['offpeak_wait'] or [0]
    data = [peak_b, off_b, peak_t, off_t]
    bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                    medianprops=dict(color='white', lw=2))
    box_cols = [CB, CB, CT, CT]
    for patch, c, a in zip(bp['boxes'], box_cols, [0.9, 0.5, 0.9, 0.5]):
        patch.set_facecolor(c); patch.set_alpha(a)
    ax.set_xticks([1, 2, 3, 4])
    ax.set_xticklabels(['기본\n첨두', '기본\n비첨두', '태그\n첨두', '태그\n비첨두'], fontsize=9)
    ax.set_title('첨두/비첨두별 대기시간')
    ax.set_ylabel('대기시간 (s)')
    for i, d in enumerate(data, 1):
        ax.text(i, np.mean(d) + 1, f'{np.mean(d):.0f}s', ha='center',
                fontsize=8, fontweight='bold')
    ax.grid(True, axis='y', alpha=0.3)

    # ── [2,0] 누적 처리 인원 (throughput) ───────────────────────────────────
    ax = axes[2, 0]
    pass_b_sorted = sorted(rb['pass_ts'])
    pass_t_sorted = sorted(rt['pass_ts'])
    ax.plot(pass_b_sorted, np.arange(1, len(pass_b_sorted) + 1),
            color=CB, lw=2, label=f"기본 ({rb['n_post']}명)")
    ax.plot(pass_t_sorted, np.arange(1, len(pass_t_sorted) + 1),
            color=CT, lw=2, label=f"태그리스 ({rt['n_post']}명)")
    for tt in TRAIN_TIMES:
        ax.axvline(tt, color='red', lw=1, ls='--', alpha=0.4)
    ax.set_title('누적 게이트 통과 인원')
    ax.set_xlabel('시간 (s)'); ax.set_ylabel('누적 통과 (명)')
    ax.legend(fontsize=9); ax.grid(True, alpha=0.3)

    # ── [2,1] 병목 분석 - 용량 비교 막대 ───────────────────────────────────
    ax = axes[2, 1]
    stair_c    = 3.7 * 1.25 * 60   # ped/min
    base_gate  = 7 / 2.0 * 60
    tag_gate   = 7 / 1.2 * 60
    categories = ['계단 용량', '게이트(기본\nT=2.0s)', '게이트(태그\nT=1.2s)']
    values     = [stair_c, base_gate, tag_gate]
    bar_cols   = ['#78909C', CB, CT]
    bars = ax.bar(categories, values, color=bar_cols, edgecolor='white', linewidth=1.2)
    ax.axhline(stair_c, color='#78909C', ls='--', lw=1.5, alpha=0.7)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 3,
                f'{val:.0f}\nped/min', ha='center', va='bottom', fontsize=9, fontweight='bold')
    ax.set_title('계단-게이트 용량 비교\n(병목 전이 분석)')
    ax.set_ylabel('용량 (ped/min)')
    ax.set_ylim(0, max(values) * 1.3)
    # 병목 주석
    ax.annotate('게이트 병목\n(기본 시나리오)', xy=(1, base_gate),
                xytext=(1.3, base_gate + 50), fontsize=8, color=CB,
                arrowprops=dict(arrowstyle='->', color=CB))
    ax.annotate('병목 전이\n→ 계단 병목', xy=(2, stair_c),
                xytext=(1.8, stair_c + 80), fontsize=8, color='red',
                arrowprops=dict(arrowstyle='->', color='red'))

    plt.tight_layout()
    out = OUTPUT_DIR / "scenario_comparison.png"
    fig.savefig(out, dpi=150, bbox_inches='tight')
    print(f"\n  저장: {out}")
    plt.close(fig)


# =============================================================================
# 메인
# =============================================================================
if __name__ == '__main__':
    base_path = OUTPUT_DIR / "baseline" / "trajectories_baseline.csv"
    tag_path  = OUTPUT_DIR / "trajectories.csv"

    print("데이터 로드 중...")
    base_pre, base_post = load_scenario(base_path)
    tag_pre,  tag_post  = load_scenario(tag_path)

    rb = analyze(base_pre, base_post, "기본 (0% 태그리스, T=2.0s)")
    rt = analyze(tag_pre,  tag_post,  "전면 태그리스 (100%, T=1.2s)")

    print_summary_table(rb, rt)
    plot_comparison(rb, rt)
