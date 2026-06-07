# SPiDR 재현 — 파라메트릭 스텐실 빌드 스크립트 (Fusion 360)
# 사용: Fusion 360 → 유틸리티 → ADD-INS → 스크립트, 또는 MCP fusion_mcp_execute(featureType="script").
# 핸드오프(Fusion360_MCP_모델링_핸드오프.md) 규칙 준수: cm 단위, 예외 미포착, 인덱스 식별,
#   modelToSketchSpace, 각진 평면 라디얼 컷, 매 단계 부피·바디수 검산.
#
# 형상: Ø28mm 외경 실린더, Ø17mm 내부 캐비티(16mm 트랜스듀서 끼움, 바닥 개방),
#       높이 20mm(상단 3mm 솔리드), 측벽에 20개 라디얼 홀(Ø2mm)을
#       sim/stencil_design.npz 최적화 결과 (angle, height)로 배치.
# 검증값: base 12.315 / cavity 제거 3.859 / 홀 제거 ~0.341 cm³, 바디 1개, 원통면 22.

import adsk.core, adsk.fusion, math

# (angle_deg, height_mm) — sim/design_stencil.py 출력. 새로 최적화하면 이 표만 교체.
TUBES = [(223.2,9.5),(201.8,2.5),(358.9,13.4),(217.3,3.7),(313.8,12.0),(263.2,9.7),
         (339.5,16.3),(246.7,14.3),(177.5,14.0),(104.1,10.7),(332.8,10.5),(19.7,14.9),
         (304.7,13.8),(317.8,7.7),(124.2,7.5),(51.8,6.8),(329.1,10.5),(337.8,5.8),
         (108.8,12.9),(40.2,7.7)]
OUTER_R, CAV_R, HEIGHT, TOP_SOLID, HOLE_R = 1.4, 0.85, 2.0, 0.3, 0.1  # cm


def run(_context):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent
    VI, P3 = adsk.core.ValueInput, adsk.core.Point3D
    ex = root.features.extrudeFeatures

    # 1) 외경 실린더
    sk = root.sketches.add(root.xYConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(P3.create(0, 0, 0), OUTER_R)
    base = ex.addSimple(sk.profiles.item(0), VI.createByReal(HEIGHT),
                        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    body = base.bodies.item(0); body.name = 'SPiDR_Stencil'

    # 2) 내부 캐비티 (바닥 개방, 상단 TOP_SOLID 남김)
    sk2 = root.sketches.add(root.xYConstructionPlane)
    sk2.sketchCurves.sketchCircles.addByCenterRadius(P3.create(0, 0, 0), CAV_R)
    ci = ex.createInput(sk2.profiles.item(0), adsk.fusion.FeatureOperations.CutFeatureOperation)
    ci.setDistanceExtent(False, VI.createByReal(HEIGHT - TOP_SOLID))
    ci.participantBodies = [body]; ex.add(ci)

    # 3) 20개 라디얼 홀 (각진 평면 + modelToSketchSpace + 한 방향 라디얼 컷)
    for ang, hmm in TUBES:
        pin = root.constructionPlanes.createInput()
        pin.setByAngle(root.zConstructionAxis, VI.createByString('%f deg' % ang),
                       root.yZConstructionPlane)
        pl = root.constructionPlanes.add(pin)
        skh = root.sketches.add(pl)
        p = skh.modelToSketchSpace(P3.create(0, 0, hmm / 10.0))
        skh.sketchCurves.sketchCircles.addByCenterRadius(P3.create(p.x, p.y, 0), HOLE_R)
        h = ex.createInput(skh.profiles.item(0), adsk.fusion.FeatureOperations.CutFeatureOperation)
        h.setDistanceExtent(False, VI.createByReal(1.5))
        h.participantBodies = [body]; ex.add(h)

    ST = adsk.core.SurfaceTypes
    ncyl = sum(1 for f in body.faces if f.geometry.surfaceType == ST.CylinderSurfaceType)
    print('bodies=%d vol=%.3f cyl_faces=%d' % (root.bRepBodies.count, body.volume, ncyl))

    # 4) STL/F3D 익스포트 (ASCII 경로 — 한글경로 export 실패 회피)
    em = des.exportManager
    b = r'C:\Users\sssbj\AppData\Local\Temp\spidr_stencil'
    o = em.createSTLExportOptions(body, b + '.stl')
    o.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
    em.execute(o)
    em.execute(em.createFusionArchiveExportOptions(b + '.f3d'))
    print('exported to', b, '(*.stl,*.f3d) — models 폴더로 이동')
