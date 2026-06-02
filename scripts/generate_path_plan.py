import io
from datetime import datetime
import numpy as np
import mysql.connector

from one import (
    oum, ouc, osso, ossop,
    ocm, khi_rs007l, or_2fg7, omppc, ompp
)

from db_config import DB_CONFIG
from paths import BUNNY_MESH_PATH

def log(message: str):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {message}", flush=True)

def blob_to_ndarray(blob: bytes) -> np.ndarray:
    return np.load(io.BytesIO(blob))

def ndarray_to_blob(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.save(buf, arr)
    return buf.getvalue()

def main():
    log("connecting to database")
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    # IKが成功していて、かつ経路がまだ計算されていないデータを取得
    cur.execute("""
        SELECT 
            pgik.placement_grasp_ik_id, 
            pgik.goal_joint_values,
            p.world_pos, 
            p.world_rotmat,
            g.jaw_width
        FROM placement_grasp_ik pgik
        JOIN placement p ON pgik.placement_id = p.placement_id
        JOIN grasp g ON pgik.grasp_id = g.grasp_id
        WHERE pgik.ik_success = 1 AND pgik.path_joint_values IS NULL
    """)
    targets = cur.fetchall()
    log(f"Targets to plan: {len(targets)}")

    if not targets:
        log("No targets left to plan. Exiting.")
        cur.close()
        conn.close()
        return

    log("initializing robot, gripper, and scene")
    robot = khi_rs007l.RS007L()
    gripper = or_2fg7.OR2FG7()
    robot.engage(gripper)

    bunny = osso.SceneObject.from_file(
        str(BUNNY_MESH_PATH),
        collision_type=ouc.CollisionType.MESH,
    )
    ground = ossop.plane(pos=(0, 0, 0.01))

    log("compiling MuJoCo collider and PRM Planner")
    mjc = ocm.MJCollider()
    mjc.append(robot)
    mjc.append(gripper)
    mjc.append(bunny)
    mjc.append(ground)
    mjc.actors = [robot]
    mjc.compile(margin=0.0)

    pln_ctx = omppc.PlanningContext(collider=mjc)
    planner = ompp.LazyPRMPlanner(pln_ctx=pln_ctx)

    home_qs = robot.qs.copy()
    success_count = 0
    fail_count = 0

    for i, row in enumerate(targets, start=1):
        pgik_id = row['placement_grasp_ik_id']
        goal_qs = blob_to_ndarray(row['goal_joint_values'])
        bunny.pos = blob_to_ndarray(row['world_pos'])
        bunny.rotmat = blob_to_ndarray(row['world_rotmat'])
        jaw_width = float(row['jaw_width'])

        # グリッパの開き具合をプランナーにセット (先生のコード準拠)
        aux_qs = (jaw_width / 2, jaw_width / 2)
        pln_ctx.set_aux_mecbas(gripper, aux_qs)

        # 経路探索の実行
        path = planner.solve(start=home_qs, goal=goal_qs)

        if path:
            path_arr = np.asarray(path, dtype=np.float64)
            cur.execute("""
                UPDATE placement_grasp_ik 
                SET path_joint_values = %s 
                WHERE placement_grasp_ik_id = %s
            """, (ndarray_to_blob(path_arr), pgik_id))
            conn.commit()
            success_count += 1
            log(f"[{i}/{len(targets)}] Plan Success for pgik_id={pgik_id}")
        else:
            fail_count += 1
            log(f"[{i}/{len(targets)}] Plan Failed for pgik_id={pgik_id}")

    cur.close()
    conn.close()
    log(f"Planning complete. Success: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    main()