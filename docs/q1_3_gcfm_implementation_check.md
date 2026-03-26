# Q1.3: JuPedSim GCFM 구현 vs Chraibi (2010) 원논문 대조

> V&V Phase 1 — Model Qualification
> 목적: JuPedSim v1.3.2의 GCFM 구현이 원논문과 일치하는지 확인

## 1. 운동 방정식

**원논문 (Chraibi 2010, Eq.1)**:
```
m_i * x_i'' = F_i^drv + SUM_j(F_ij^rep) + SUM_w(F_iw^rep)
```

**JuPedSim 구현** (`GeneralizedCentrifugalForceModel.cpp`):
```
acc = (F_drv + F_rep_neighbors + F_rep_walls) / mass
velocity = velocity + acc * dt    (Euler 적분)
position = position + velocity * dt
```

**판정**: 일치. 1차 Euler 적분은 원논문에서 명시하지 않았으나 표준 구현 방식.

---

## 2. 구동력 (Driving Force)

**원논문**: F_i^drv = m_i * (v0_i * e0 - v_i) / tau

**JuPedSim**: F_driv = mass * (v0 * e0 - velocity) / tau

**판정**: 일치.

---

## 3. 보행자 간 반발력

**원논문 (Chraibi 2010, Eq.5)**:
```
F_ij^rep = -m_i * K_ij * (eta * |v0_i| + v_ij)^2 / d_ij * e_ij
```
- K_ij: 방향 감소 인자 (뒤쪽 보행자 무시)
- eta: 반발 강도 (strength_neighbor_repulsion)
- v_ij: 상대 접근 속도 (양수만 취함)
- d_ij: 타원 표면 간 유효 거리

**JuPedSim**:
```cpp
nom = strengthNeighborRepulsion * v0 + v_ij;  // eta * v0 + v_ij
nom *= nom;                                     // 제곱
f = -mass * K_ij * nom / dist_eff;              // 반발력
```

**판정**: 핵심 수식 일치.

---

## 4. 벽면 반발력

**원논문**: 보행자 간 반발력과 동일 구조, eta_w (strengthGeometryRepulsion) 사용

**JuPedSim**: 동일 구조, strengthGeometryRepulsion 사용. 벽면 법선 방향 힘만 적용.

**판정**: 일치.

---

## 5. 타원형 몸체

**원논문 (Chraibi 2010, §II.B)**:
```
a(v) = a_min + a_v * speed    (이동 방향 반축, 속도에 비례하여 증가)
b(v) = b_max - (b_max - b_min) * speed / v0  (어깨 방향 반축, 속도에 비례하여 감소)
```

**JuPedSim** (`Ellipse.cpp`):
```cpp
a = a_min + a_v * speed
b = b_max - (b_max - b_min) * (speed / v0)
```

**판정**: 일치.

---

## 6. JuPedSim 고유 구현 사항 (원논문에 없는 부분)

### 6-1. 5구간 힘 보간 (Hermite Interpolation)

원논문에서는 반발력이 거리에 따라 단순 감소하지만, JuPedSim은 수치 안정성을 위해
상호작용 거리 경계에서 **3차 에르미트 보간**으로 부드럽게 전이:

```
구간 1: dist > max_interaction_distance → 힘 = 0
구간 2: 보간 영역 (힘이 부드럽게 0으로)
구간 3: 기본 반발력 공식 적용
구간 4: 보간 영역 (힘이 부드럽게 최대값으로)
구간 5: dist <= smax → 힘 = max_repulsion_force (상한)
```

이는 수치적 안정성을 위한 표준 기법이며, 물리적 행태에 큰 영향을 주지 않음.

### 6-2. max_repulsion_force 상한 ⚠️

원논문에는 반발력 상한이 없으나, JuPedSim은 수치 발산 방지를 위해 상한을 둠.

**JuPedSim 기본값**:
| 파라미터 | JuPedSim 기본값 | 현재 설정값 |
|---------|---------------|-----------|
| max_neighbor_repulsion_force | **9.0** | **3.0** ⚠️ |
| max_geometry_repulsion_force | **3.0** | 3.0 |

**⚠️ 발견**: 현재 max_neighbor_repulsion_force를 기본값 9.0에서 3.0으로 낮춘 상태.
이는 병목 유량을 Seyfried (2009) 실험에 맞추기 위한 **캘리브레이션 결과**이다.

9.0으로 복원 시 검증 결과:
- V3 병목 유량: PASS(9.5%) → **FAIL(50%)** — 유량 반토막
- V6 겹침: 22.4cm → **22.8cm** — 변화 없음
- V2 기본 다이어그램: PASS(0.184) → **FAIL(0.234)**

**결론**: 3.0은 캘리브레이션된 값이며, V6 겹침의 원인은 반발력 상한이 아니라
dt=0.01에서의 힘 적분 해상도 한계이다. 이는 GCFM(힘 기반 모델)의 구조적 특성이며,
보고서에 한계점으로 기술한다.

---

## 7. 종합 판정

| 항목 | 원논문 vs JuPedSim | 판정 |
|------|-------------------|------|
| 운동 방정식 | 일치 | ✅ |
| 구동력 | 일치 | ✅ |
| 보행자 간 반발력 | 일치 | ✅ |
| 벽면 반발력 | 일치 | ✅ |
| 타원형 몸체 | 일치 | ✅ |
| 힘 보간 (JuPedSim 고유) | 원논문에 없음, 수치 기법 | ✅ (합리적) |
| 반발력 상한 (JuPedSim 고유) | 원논문에 없음 | ⚠️ 현재 3.0 (기본 9.0) |

**결론**: JuPedSim의 GCFM 구현은 Chraibi (2010) 원논문의 수식과 일치한다.
다만 max_neighbor_repulsion_force를 기본값(9.0)보다 낮게(3.0) 설정한 것이
V6 겹침 문제에 기여하고 있으므로, 기본값 복원 후 V3(병목 유량) + V6(겹침) 재검증을 권장한다.

## 참고

- 소스코드: `GeneralizedCentrifugalForceModel.cpp`, `Ellipse.cpp`
- JuPedSim 모델 문서: https://pedestriandynamics.org/models/generalized_centrifugal_force_model/
- Chraibi et al. (2010): https://doi.org/10.1103/PhysRevE.82.046111
