# SPiDR 재현 — 가변 경로길이 위상캡 v2 빌드 스크립트 (Fusion 360)
# Codex(gpt-5.5) 리뷰 반영: 동일길이 라디얼 홀(control)은 위상 다양성 부족 →
#   "가변 경로길이"가 핵심. v2는 중앙 기둥(column)으로 소리를 올린 뒤,
#   서로 다른 높이의 라디얼 홀로 빼내 채널마다 경로길이를 다르게 한다(=Owlet 메커니즘).
# 검증값(빌드 시): 바디 1, vol≈22.81cm³, 경로길이 12~35mm(스프레드 23mm≈2.7λ), 원통면 20.
# 형상: Ø30 OD × 40mm. 바닥 Ø16.7 캐비티(16mm 트랜스듀서, 12mm) + 시팅 레지.
#   중앙 Ø10 기둥(12→38mm). 측벽 16개 Ø2.3 라디얼 홀(높이 14~37mm).
# 빈 부품 문서에서 실행(스크립트 or MCP fusion_mcp_execute).

import adsk.core, adsk.fusion, math

OUTER_R, CAV_R, COL_R, H, CAV_H = 1.5, 0.835, 0.5, 4.0, 1.2   # cm
HOLE_R = 0.115                                                  # Ø2.3mm
EXIT_HEIGHTS = [1.4,3.0,1.9,3.5,2.3,3.7,1.6,2.8,2.0,3.3,1.5,3.6,2.5,3.1,1.7,2.7]  # cm


def run(_context):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent
    VI, P3 = adsk.core.ValueInput, adsk.core.Point3D
    ex = root.features.extrudeFeatures

    # 1) base Ø30 x 40
    sk = root.sketches.add(root.xYConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(P3.create(0, 0, 0), OUTER_R)
    base = ex.addSimple(sk.profiles.item(0), VI.createByReal(H),
                        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    body = base.bodies.item(0); body.name = 'SPiDR_PhaseCap_v2'

    def cut_circle(plane_z, radius, dist, r0=0.0):
        pin = root.constructionPlanes.createInput()
        pin.setByOffset(root.xYConstructionPlane, VI.createByReal(plane_z))
        pl = root.constructionPlanes.add(pin)
        s = root.sketches.add(pl)
        s.sketchCurves.sketchCircles.addByCenterRadius(P3.create(0, 0, 0), radius)
        ci = ex.createInput(s.profiles.item(0), adsk.fusion.FeatureOperations.CutFeatureOperation)
        ci.setDistanceExtent(False, VI.createByReal(dist)); ci.participantBodies = [body]; ex.add(ci)

    # 2) 트랜스듀서 캐비티 Ø16.7 (0->1.2, 바닥 개방) + 3) 중앙 기둥 Ø10 (1.2->3.8)
    cut_circle(0.0, CAV_R, CAV_H)
    cut_circle(CAV_H, COL_R, 2.6)

    # 4) 16개 라디얼 배출 홀 (높이별 = 경로길이별)
    for i in range(16):
        ang, h = i * 22.5, EXIT_HEIGHTS[i]
        pin = root.constructionPlanes.createInput()
        pin.setByAngle(root.zConstructionAxis, VI.createByString('%f deg' % ang),
                       root.yZConstructionPlane)
        pl = root.constructionPlanes.add(pin)
        skh = root.sketches.add(pl)
        p = skh.modelToSketchSpace(P3.create(0, 0, h))
        skh.sketchCurves.sketchCircles.addByCenterRadius(P3.create(p.x, p.y, 0), HOLE_R)
        hi = ex.createInput(skh.profiles.item(0), adsk.fusion.FeatureOperations.CutFeatureOperation)
        hi.setDistanceExtent(False, VI.createByReal(1.6)); hi.participantBodies = [body]; ex.add(hi)

    ST = adsk.core.SurfaceTypes
    ncyl = sum(1 for f in body.faces if f.geometry.surfaceType == ST.CylinderSurfaceType)
    print('bodies=%d vol=%.3f cyl_faces=%d' % (root.bRepBodies.count, body.volume, ncyl))

    em = des.exportManager
    b = r'C:\Users\sssbj\AppData\Local\Temp\spidr_phasecap_v2'
    o = em.createSTLExportOptions(body, b + '.stl')
    o.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
    em.execute(o)
    em.execute(em.createFusionArchiveExportOptions(b + '.f3d'))
    print('exported to', b, '(*.stl in mm, *.f3d)')
